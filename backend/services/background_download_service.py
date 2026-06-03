import threading
import queue
from typing import Optional, Dict, Any

from models.image_model import (
    get_image_by_id,
    get_image_by_task_id,
    get_task,
    update_task,
    update_image,
)


def _resolve_base_dir():
    import os
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BackgroundDownloadService:
    """
    后台图片下载服务

    功能描述：
        异步下载远程图片到本地并生成缩略图，不阻塞 TaskProcessor 主循环。
        TaskProcessor 检测到任务成功后，立即将远程 URL 写入 DB，
        同时将下载任务加入本服务的队列。本服务在后台线程中完成下载和缩略图生成，
        完成后用本地 URL 替换远程 URL。

    实现逻辑：
        1. 使用 queue.Queue 接收下载任务
        2. 单个守护线程消费队列中的任务
        3. 在 Flask 应用上下文中执行下载和数据库更新
        4. 下载成功：更新 images 表的 url/local_path/thumbnail/thumbnail_path
        5. 下载失败：保留远程 URL，记录 download_error 到 tasks.data
        6. 支持启动、停止、队列状态查询
    """

    def __init__(self, app, max_workers: int = 2):
        """
        初始化后台下载服务

        参数：
            app: Flask 应用实例，用于获取应用上下文
            max_workers: 下载工作线程数
        """
        self._app = app
        self._max_workers = max_workers
        self._running = False
        self._task_queue: queue.Queue = queue.Queue()
        self._threads = []

    def start(self):
        """
        启动后台下载服务
        """
        if self._running:
            print("[BackgroundDownload] Already running")
            return

        self._running = True

        for i in range(self._max_workers):
            thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"bg-download-{i}"
            )
            thread.start()
            self._threads.append(thread)

        print(f"[BackgroundDownload] Started with {self._max_workers} worker(s)")

    def stop(self):
        """
        停止后台下载服务
        """
        self._running = False
        # 向队列放入 None 作为停止信号，确保工作线程能退出
        for _ in self._threads:
            try:
                self._task_queue.put_nowait(None)
            except queue.Full:
                pass

        for thread in self._threads:
            thread.join(timeout=10)
        self._threads.clear()
        print("[BackgroundDownload] Stopped")

    def enqueue_download(self, task: Dict[str, Any]):
        """
        将下载任务加入队列

        参数：
            task: 下载任务字典，包含以下字段：
                - image_id (str): images 表主键
                - image_url (str): 远程图片 URL
                - image_type (str): 'generation' 或 'edit'
                - folder_path (str, 可选): 编辑图片的文件夹路径
                - task_id (str, 可选): 关联的 tasks 表 ID，用于更新 download_error
        """
        if not self._running:
            print("[BackgroundDownload] Service not running, cannot enqueue task")
            return

        try:
            self._task_queue.put_nowait(task)
            queue_size = self._task_queue.qsize()
            print(f"[BackgroundDownload] Enqueued download for image_id={task.get('image_id')}, queue_size={queue_size}")
        except queue.Full:
            print(f"[BackgroundDownload] Queue full, dropping download task for image_id={task.get('image_id')}")

    @property
    def queue_size(self) -> int:
        """当前队列中的待下载任务数"""
        return self._task_queue.qsize()

    def _worker_loop(self):
        """
        工作线程主循环

        实现逻辑：
            1. 从队列中阻塞获取下载任务
            2. 在 Flask 应用上下文中执行下载
            3. 任务为 None 时退出循环
            4. 下载异常不中断循环，记录错误后继续处理下一个任务
        """
        while self._running:
            try:
                task = self._task_queue.get(timeout=5)
            except queue.Empty:
                continue

            if task is None:
                break

            try:
                self._process_download_task(task)
            except Exception as e:
                print(f"[BackgroundDownload] Unexpected error in download worker: {e}")
            finally:
                self._task_queue.task_done()

    def _process_download_task(self, task: Dict[str, Any]):
        """
        处理单个下载任务

        实现逻辑：
            1. 从数据库获取当前图片记录
            2. 根据 image_type 调用对应的资产准备函数
            3. 下载成功后更新 images 表
            4. 下载失败时记录错误到 tasks.data
        """
        image_id = task.get('image_id')
        image_url = task.get('image_url')
        image_type = task.get('image_type', 'generation')
        folder_path = task.get('folder_path')
        task_id = task.get('task_id')

        if not image_url:
            print(f"[BackgroundDownload] No image_url for image_id={image_id}, skipping download")
            return

        with self._app.app_context():
            current_image = get_image_by_id(image_id)
            if not current_image:
                print(f"[BackgroundDownload] Image {image_id} not found in DB, skipping download")
                return

            print(f"[BackgroundDownload] Starting download for image_id={image_id}, url={image_url[:80]}...")

            download_error = ''
            try:
                if image_type == 'edit':
                    # 编辑图片使用 save_edit_result_directly 保存到 edit_folders 根目录
                    # 并自动生成缩略图到 edit_thumbnails
                    from services.edit_asset_service import save_edit_result_directly
                    asset_result = save_edit_result_directly(image_url, getattr(current_image, 'prompt', ''))
                else:
                    from routes.images import prepare_generation_assets
                    asset_result = prepare_generation_assets(image_url, current_image.local_path)

                current_image.url = asset_result.get('display_url') or asset_result.get('url') or image_url
                current_image.thumbnail = asset_result.get('thumbnail', '')
                current_image.local_path = asset_result.get('local_path')
                current_image.thumbnail_path = asset_result.get('thumbnail_path')
                download_error = asset_result.get('error', '')

                update_image(current_image)
                print(f"[BackgroundDownload] Download succeeded for image_id={image_id}, local_path={current_image.local_path}")

            except Exception as err:
                download_error = str(err)
                # 下载失败时保留远程 URL，前端仍可展示
                if not current_image.url:
                    current_image.url = image_url
                    update_image(current_image)
                print(f"[BackgroundDownload] Download failed for image_id={image_id}: {download_error}")

            # 更新 tasks.data 中的 download_error
            if task_id and download_error:
                current_task = get_task(task_id)
                if current_task:
                    task_data = current_task.get('data', {})
                    if isinstance(task_data, str):
                        import json
                        try:
                            task_data = json.loads(task_data)
                        except Exception:
                            task_data = {}
                    if isinstance(task_data, dict):
                        task_data['download_error'] = download_error
                    update_task(task_id, data=task_data)


_background_download_service: Optional[BackgroundDownloadService] = None


def get_background_download_service() -> BackgroundDownloadService:
    """
    获取全局后台下载服务实例
    """
    global _background_download_service
    if _background_download_service is None:
        raise RuntimeError('BackgroundDownloadService not initialized. Call start_background_download_service(app) first.')
    return _background_download_service


def start_background_download_service(app, max_workers: int = 2):
    """
    启动全局后台下载服务

    参数：
        app: Flask 应用实例
        max_workers: 下载工作线程数
    """
    global _background_download_service
    _background_download_service = BackgroundDownloadService(app, max_workers)
    _background_download_service.start()


def stop_background_download_service():
    """
    停止全局后台下载服务
    """
    global _background_download_service
    if _background_download_service:
        _background_download_service.stop()
        _background_download_service = None


def enqueue_image_download(
    image_id: str,
    image_url: str,
    image_type: str = 'generation',
    folder_path: str = None,
    task_id: str = None
):
    """
    便捷函数：将图片下载任务加入后台队列

    功能描述：
        供 TaskProcessor 等模块调用，将远程图片下载任务提交到后台队列。
        下载完成后自动更新 images 表。

    参数：
        image_id: images 表主键
        image_url: 远程图片 URL
        image_type: 图片类型（'generation' 或 'edit'）
        folder_path: 编辑图片的文件夹路径（仅 image_type='edit' 时需要）
        task_id: 关联的 tasks 表 ID（用于记录下载错误）
    """
    if _background_download_service is None:
        print("[BackgroundDownload] Service not initialized, performing sync download...")
        # 兜底：如果服务未启动，fallback 到同步下载
        try:
            from routes.images import prepare_image_assets
            from models.image_model import get_image_by_id, update_image
            current_image = get_image_by_id(image_id)
            if current_image:
                asset_result = prepare_image_assets(image_url, current_image.local_path)
                current_image.url = asset_result.get('display_url') or asset_result.get('url') or image_url
                current_image.thumbnail = asset_result.get('thumbnail', '')
                current_image.local_path = asset_result.get('local_path')
                current_image.thumbnail_path = asset_result.get('thumbnail_path')
                update_image(current_image)
                print(f"[BackgroundDownload] Sync fallback download succeeded for image_id={image_id}")
        except Exception as e:
            print(f"[BackgroundDownload] Sync fallback download failed for image_id={image_id}: {e}")
        return

    _background_download_service.enqueue_download({
        'image_id': image_id,
        'image_url': image_url,
        'image_type': image_type,
        'folder_path': folder_path,
        'task_id': task_id
    })
