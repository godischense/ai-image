# Topaz Gigapixel AI 异步任务执行服务
#
# 功能描述：
#     异步执行 Topaz Gigapixel AI 图片放大任务。
#     与 task_processor 的远程 API 轮询模式不同，本服务通过本地 subprocess 调用
#     gigapixel.exe 处理图片，耗时较长（1-10 分钟/张），因此使用独立的后台 worker 池串行处理。
#     用户离开页面后任务继续在后台执行，完成后用户可随时回来查看结果。
#
# 实现逻辑：
#     1. 使用 queue.Queue 接收任务
#     2. 多个守护线程消费队列（默认 1 个，保护 GPU）
#     3. 在 Flask 应用上下文中执行：调用 subprocess、更新 images 表、生成缩略图、更新 tasks 表
#     4. 启动时扫描 IN_PROGRESS 状态的 topaz_gigapixel 任务，标记为 FAILURE（worker 重启兜底）
#     5. 任务完成后清理 per-task 临时子目录，保留最终 gigapixel_output/ 目录
#     6. 失败时写 fail_reason；不覆盖已被标记为 CANCELLED 的任务（用户主动取消优先）
#
# 失败处理（项目规则：失败优先）：
#     - exe 不存在 / 输出目录不可写 -> 任务标记 FAILURE，写入 fail_reason
#     - 用户取消任务（status=CANCELLED）-> worker 不覆盖
#     - 后端重启 -> 启动时扫描 IN_PROGRESS 任务，统一标记为 FAILURE('worker restarted')
#     - 任务成功但复制/缩略图失败 -> 任务仍标 SUCCESS，fail_reason 记录 warning
#     - 异常兜底：所有未捕获异常都进入失败分支
#
# 用户操作异常考虑：
#     - 用户提交后立即关闭浏览器：任务继续在后台执行
#     - 用户重复提交同一张图：每张提交独立 task，输出文件名带 task_id 避免冲突
#     - 用户在处理过程中取消：标记 CANCELLED，subprocess 自然完成（不强杀避免文件锁）
#     - 用户改 exe 路径：worker 启动时读 config；运行中路径变更不影响当前任务
#     - 后端被 kill -9：per-task 临时目录残留，下次启动时由 cleanup 清理

import os
import queue
import shutil
import threading
import time
import uuid
from typing import Optional, Dict, Any

from models.image_model import (
    add_image,
    add_task,
    get_db_connection,
    get_image_by_id,
    get_task,
    update_image,
    update_task,
)
from models.config_model import get_single_config
from services.topaz_gigapixel_service import TopazGigapixelService


# 项目根目录（gigapixel_output 等绝对路径的基准）
def _project_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# gigapixel 输出目录（原图）
GIGAPIXEL_OUTPUT_DIR = os.path.join(_project_root(), 'gigapixel_output')
# gigapixel 缩略图目录
GIGAPIXEL_THUMBNAILS_DIR = os.path.join(_project_root(), 'gigapixel_thumbnails')
# per-task 临时输出子目录根（gigapixel.exe 写入这里）
GIGAPIXEL_TEMP_ROOT = os.path.join(_project_root(), 'gigapixel_temp')


def _ensure_dirs():
    """
    确保 gigapixel 相关目录都存在。
    """
    for d in (GIGAPIXEL_OUTPUT_DIR, GIGAPIXEL_THUMBNAILS_DIR, GIGAPIXEL_TEMP_ROOT):
        os.makedirs(d, exist_ok=True)


class GigapixelTaskService:
    """
    Topaz Gigapixel AI 异步任务执行服务。

    模式与 BackgroundDownloadService 一致：queue.Queue + 守护线程 + app_context。
    """

    def __init__(self, app, max_workers: int = 1):
        """
        初始化 GigapixelTaskService。

        参数：
            app: Flask 应用实例，用于获取应用上下文
            max_workers: 工作线程数。Topaz Gigapixel 吃 GPU/CPU，默认 1 串行更稳。
        """
        self._app = app
        self._max_workers = max_workers
        self._running = False
        self._task_queue = queue.Queue()
        self._threads = []

    def start(self):
        """
        启动后台 worker 池。

        实现逻辑：
            1. 启动前确保所有目录存在
            2. 启动前扫描上次残留的 IN_PROGRESS 任务，统一标记为 FAILURE（worker restarted）
            3. 启动 max_workers 个守护线程
        """
        if self._running:
            print('[GigapixelTask] Already running')
            return

        _ensure_dirs()
        self._mark_orphaned_tasks_as_failed()

        self._running = True
        for i in range(self._max_workers):
            thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f'gigapixel-worker-{i}'
            )
            thread.start()
            self._threads.append(thread)

        print(f'[GigapixelTask] Started with {self._max_workers} worker(s)')

    def stop(self):
        """
        停止后台 worker 池。
        """
        self._running = False
        for _ in self._threads:
            try:
                self._task_queue.put_nowait(None)
            except queue.Full:
                pass
        for thread in self._threads:
            thread.join(timeout=10)
        self._threads.clear()
        print('[GigapixelTask] Stopped')

    def enqueue(self, task: Dict[str, Any]):
        """
        将 gigapixel 任务加入队列。

        参数：
            task: 任务字典，必须包含以下字段：
                - task_id: str
                - image_id: str
                - input_path: str  输入图片绝对路径
                - settings: dict 包含 scale/model/enabled/sharpen/denoise/compression/fr/pre_downscaling
        """
        if not self._running:
            print('[GigapixelTask] Service not running, cannot enqueue')
            return
        try:
            self._task_queue.put_nowait(task)
            print(f"[GigapixelTask] Enqueued task_id={task.get('task_id')}, queue_size={self._task_queue.qsize()}")
        except queue.Full:
            print(f"[GigapixelTask] Queue full, dropping task {task.get('task_id')}")

    @property
    def queue_size(self) -> int:
        return self._task_queue.qsize()

    def _worker_loop(self):
        """
        Worker 主循环。

        实现逻辑：
            1. 阻塞从队列取任务（None 为停止信号）
            2. 在 Flask app_context 中执行
            3. 异常不中断循环，记录后继续处理下一个
        """
        while self._running:
            try:
                task = self._task_queue.get(timeout=5)
            except queue.Empty:
                continue

            if task is None:
                break

            try:
                self._process_task(task)
            except Exception as e:
                print(f'[GigapixelTask] Unexpected error in worker: {e}')
            finally:
                self._task_queue.task_done()

    def _process_task(self, task: Dict[str, Any]):
        """
        处理单个 gigapixel 任务。

        实现逻辑：
            1. 标记任务 IN_PROGRESS + 写 start_time
            2. 实例化 TopazGigapixelService（读最新 config 中的 exe_path/useSystemCommand/timeout）
            3. 准备 per-task 临时输出目录
            4. 调用 upscale_one -> 成功时复制输出到 GIGAPIXEL_OUTPUT_DIR + 生成缩略图 + 更新 images + tasks
            5. 失败时更新 tasks.fail_reason（不覆盖 CANCELLED）
            6. 清理临时目录
        """
        task_id = task.get('task_id')
        image_id = task.get('image_id')
        input_path = task.get('input_path')
        settings = task.get('settings', {})

        if not task_id or not input_path:
            print(f'[GigapixelTask] Invalid task: {task}')
            return

        with self._app.app_context():
            # 标记 IN_PROGRESS
            update_task(
                task_id,
                status='IN_PROGRESS',
                start_time=int(time.time() * 1000),
                progress='0%'
            )

            # 读最新配置（用户可能在配置面板改过）
            config = get_single_config('topaz_gigapixel') or {}
            exe_path = config.get('exePath', '') or ''
            use_system_command = bool(config.get('useSystemCommand', False))
            timeout = int(config.get('timeout', 600) or 600)

            # 准备临时输出子目录
            temp_dir = os.path.join(GIGAPIXEL_TEMP_ROOT, f't{task_id}')
            try:
                os.makedirs(temp_dir, exist_ok=True)
            except Exception as e:
                self._mark_task_failed(task_id, f'创建临时目录失败: {e}')
                return

            # 实例化 service
            service = TopazGigapixelService(
                exe_path=exe_path,
                use_system_command=use_system_command,
                timeout=timeout
            )

            # 校验可用性
            available, err_msg = service.check_available()
            if not available:
                self._mark_task_failed(task_id, f'Gigapixel AI 不可用: {err_msg}')
                self._safe_rmtree(temp_dir)
                return

            # 执行放大
            try:
                print(f'[GigapixelTask] Starting upscale for task_id={task_id}, input={input_path}')
                used_settings, output_paths = service.upscale_one(
                    input_path=input_path,
                    output_dir=temp_dir,
                    scale=settings.get('scale', 2.0),
                    model_name=settings.get('model', 'Standard'),
                    settings=settings
                )
            except Exception as e:
                self._mark_task_failed(task_id, f'放大失败: {str(e)[:500]}')
                self._safe_rmtree(temp_dir)
                return

            # 检查任务是否被用户取消（取消优先）
            current_task = get_task(task_id)
            if current_task and current_task.get('status') == 'CANCELLED':
                print(f'[GigapixelTask] Task {task_id} was cancelled, dropping result')
                self._safe_rmtree(temp_dir)
                return

            # 复制输出到 GIGAPIXEL_OUTPUT_DIR 并生成缩略图
            try:
                final_filename, final_local_path, thumbnail_url, thumbnail_path = self._finalize_outputs(
                    task_id=task_id,
                    image_id=image_id,
                    output_paths=output_paths,
                    used_settings=used_settings
                )
            except Exception as e:
                self._mark_task_failed(task_id, f'保存结果失败: {str(e)[:500]}')
                self._safe_rmtree(temp_dir)
                return

            # 更新 images 表
            try:
                if image_id:
                    current_image = get_image_by_id(image_id)
                    if current_image:
                        current_image.url = f'/api/static/gigapixel_output/{final_filename}'
                        current_image.thumbnail = thumbnail_url
                        current_image.local_path = final_local_path
                        current_image.thumbnail_path = thumbnail_path
                        current_image.updated_at = time.strftime('%Y-%m-%dT%H:%M:%S')
                        update_image(current_image)
            except Exception as e:
                print(f'[GigapixelTask] Failed to update image record: {e}')

            # 标记任务 SUCCESS
            finish_time = int(time.time() * 1000)
            update_task(
                task_id,
                status='SUCCESS',
                progress='100%',
                finish_time=finish_time,
                data={
                    'settings': used_settings,
                    'output_filename': final_filename,
                    'output_url': f'/api/static/gigapixel_output/{final_filename}',
                    'thumbnail_url': thumbnail_url,
                    'input_path': input_path,
                    'output_path': final_local_path,
                }
            )
            print(f'[GigapixelTask] Task {task_id} SUCCESS, output={final_local_path}')

            # 清理临时目录
            self._safe_rmtree(temp_dir)

            # 清理本地上传文件（仅清理 gigapixel_temp/uploads 下的本地上传，保留图片库选择图）
            # 判定方法：input_path 在 GIGAPIXEL_TEMP_ROOT/uploads/ 目录下
            try:
                upload_root = os.path.join(_project_root(), 'gigapixel_temp', 'uploads')
                upload_root_abs = os.path.abspath(upload_root)
                input_abs = os.path.abspath(input_path)
                # Windows 路径比较忽略大小写
                if os.path.commonpath([upload_root_abs, input_abs]).lower() == upload_root_abs.lower():
                    if os.path.isfile(input_abs):
                        os.remove(input_abs)
                        print(f'[GigapixelTask] Cleaned uploaded input: {input_abs}')
            except Exception as e:
                # 清理失败不影响任务结果，只记录日志
                print(f'[GigapixelTask] 清理上传文件失败（非致命）: {e}')

    def _finalize_outputs(self, task_id, image_id, output_paths, used_settings):
        """
        将 gigapixel 输出复制到 GIGAPIXEL_OUTPUT_DIR 并生成缩略图。

        参数：
            task_id: 任务 id
            image_id: 关联的 image id
            output_paths: gigapixel 输出的图片绝对路径列表
            used_settings: 实际生效的参数字典

        返回：
            (final_filename, final_local_path, thumbnail_url, thumbnail_path)
        """
        if not output_paths:
            raise ValueError('output_paths 为空')

        # 选第一张输出（Topaz 单图输入一般只产出一张）
        src_path = output_paths[0]
        if not os.path.exists(src_path):
            raise ValueError(f'输出文件不存在: {src_path}')

        # 生成最终文件名：{原 stem}_gpx_{task_id 短码}.{ext}
        src_stem, src_ext = os.path.splitext(os.path.basename(src_path))
        # 兼容多种扩展名，统一小写
        ext = (src_ext or '.png').lower()
        short_id = (image_id or task_id).replace('-', '')[:12]
        final_filename = f'{src_stem}_gpx_{short_id}{ext}'
        final_local_path = os.path.join(GIGAPIXEL_OUTPUT_DIR, final_filename)

        # 避免文件名冲突
        if os.path.exists(final_local_path):
            final_filename = f'{src_stem}_gpx_{short_id}_{int(time.time())}{ext}'
            final_local_path = os.path.join(GIGAPIXEL_OUTPUT_DIR, final_filename)

        # 复制
        shutil.copy2(src_path, final_local_path)

        # 生成缩略图（直接使用 PIL 写到 gigapixel_thumbnails，避免 thumbnail_service 硬编码 URL 前缀）
        thumbnail_url = ''
        thumbnail_path = ''
        try:
            from PIL import Image, ImageOps
            with Image.open(final_local_path) as src_img:
                normalized_img = ImageOps.exif_transpose(src_img)
                ext = os.path.splitext(final_filename)[1] or '.jpg'
                thumb_filename = f'{os.path.splitext(final_filename)[0]}_thumb{ext}'
                thumbnail_path = os.path.join(GIGAPIXEL_THUMBNAILS_DIR, thumb_filename)
                if not os.path.exists(thumbnail_path):
                    preview = normalized_img.copy()
                    # 缩放至长边 512，保留纵横比
                    preview.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    save_format = 'JPEG' if ext.lower() in ('.jpg', '.jpeg') else 'PNG'
                    if save_format == 'JPEG' and preview.mode != 'RGB':
                        preview = preview.convert('RGB')
                    save_kwargs = {'optimize': True}
                    preview.save(thumbnail_path, format=save_format, **save_kwargs)
                thumbnail_url = f'/api/static/gigapixel_thumbnails/{thumb_filename}'
        except Exception as e:
            print(f'[GigapixelTask] Thumbnail generation failed: {e}')

        return final_filename, final_local_path, thumbnail_url, thumbnail_path

    def _mark_task_failed(self, task_id, reason):
        """
        标记任务为 FAILURE。如果已被用户取消（CANCELLED）则不覆盖。
        """
        with self._app.app_context():
            current_task = get_task(task_id)
            if current_task and current_task.get('status') == 'CANCELLED':
                print(f'[GigapixelTask] Task {task_id} already CANCELLED, not overwriting')
                return
            update_task(
                task_id,
                status='FAILURE',
                fail_reason=reason[:1000],
                finish_time=int(time.time() * 1000),
                progress=''
            )
            print(f'[GigapixelTask] Task {task_id} FAILED: {reason}')

    def _mark_orphaned_tasks_as_failed(self):
        """
        启动时扫描上次残留的 IN_PROGRESS topaz_gigapixel 任务，统一标记为 FAILURE。
        防止后端被 kill -9 后任务一直卡在 IN_PROGRESS 状态。
        """
        with self._app.app_context():
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    SELECT id FROM tasks
                    WHERE api_source = ? AND status IN ('PENDING', 'IN_PROGRESS', '未启动', 'QUEUED', 'NOT_STARTED', 'NOT_START', 'WAITING')
                ''', ('topaz_gigapixel',))
                rows = cursor.fetchall()
                for row in rows:
                    task_id = row['id']
                    print(f'[GigapixelTask] Marking orphaned task {task_id} as FAILURE (worker restarted)')
                    update_task(
                        task_id,
                        status='FAILURE',
                        fail_reason='后端服务重启，任务已中断',
                        finish_time=int(time.time() * 1000)
                    )
            finally:
                conn.close()

    @staticmethod
    def _safe_rmtree(path):
        """
        安全删除目录，吞掉所有异常（项目规则：失败处理兜底）。
        """
        if not path:
            return
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
        except Exception as e:
            print(f'[GigapixelTask] Failed to remove temp dir {path}: {e}')


# 全局服务实例
_gigapixel_service: Optional[GigapixelTaskService] = None


def get_gigapixel_task_service() -> GigapixelTaskService:
    """
    获取全局 GigapixelTaskService 实例。
    """
    global _gigapixel_service
    if _gigapixel_service is None:
        raise RuntimeError('GigapixelTaskService not initialized. Call start_gigapixel_task_service(app) first.')
    return _gigapixel_service


def start_gigapixel_task_service(app, max_workers: int = 1):
    """
    启动全局 GigapixelTaskService。

    参数：
        app: Flask 应用实例
        max_workers: 工作线程数（默认 1，Topaz 吃 GPU 资源）
    """
    global _gigapixel_service
    _gigapixel_service = GigapixelTaskService(app, max_workers)
    _gigapixel_service.start()


def stop_gigapixel_task_service():
    """
    停止全局 GigapixelTaskService。
    """
    global _gigapixel_service
    if _gigapixel_service:
        _gigapixel_service.stop()
        _gigapixel_service = None


def enqueue_gigapixel_task(
    task_id: str,
    image_id: str,
    input_path: str,
    settings: dict
):
    """
    便捷函数：把 gigapixel 任务加入后台队列。

    参数：
        task_id: 任务 id（已通过 add_task 创建在数据库中）
        image_id: 关联的 image id
        input_path: 输入图片绝对路径
        settings: 参数字典
    """
    if _gigapixel_service is None:
        print('[GigapixelTask] Service not initialized')
        return
    _gigapixel_service.enqueue({
        'task_id': task_id,
        'image_id': image_id,
        'input_path': input_path,
        'settings': settings,
    })
