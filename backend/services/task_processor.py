import os
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

from models.image_model import (
    get_db_connection,
    get_image_by_task_id,
    get_task,
    update_task,
    update_image,
    PENDING_TASK_STATUSES
)
from services.image_service import ImageService
from services.fal_image_service import FalImageService


class TaskProcessor:
    """
    后台任务处理器

    功能描述：
        在后台定期检查所有 pending 状态的任务，
        自动查询第三方 API 获取任务状态，
        并在任务完成或失败时更新数据库。

    实现逻辑：
        1. 后台线程在有任务时按 poll_interval 间隔轮询
        2. 查询所有 pending 状态的任务
        3. 对每个 pending 任务调用 image_service.query_task
        4. 任务完成时更新 images 和 tasks 表
        5. 没有待处理任务时通过 threading.Event 休眠，有新任务创建时被唤醒
        6. 支持启动、停止控制
    """

    def __init__(self, app, poll_interval: int = 3, max_retries: int = 300):
        """
        初始化任务处理器

        参数：
            app: Flask 应用实例，用于获取应用上下文
            poll_interval: 轮询间隔（秒），仅在有任务时使用
            max_retries: 单个任务最大查询次数
        """
        self._app = app
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._task_attempts: Dict[str, int] = {}
        self._task_errors: Dict[str, str] = {}
        self._task_consecutive_errors: Dict[str, int] = {}
        # 唤醒事件：有新任务创建或需要退出休眠时设置
        self._wake_event = threading.Event()
        # 标记是否已经在休眠模式（用于避免重复打印休眠消息）
        self._in_sleep_mode = False

    def start(self):
        """
        启动后台任务处理器
        """
        if self._running:
            print("[TaskProcessor] Already running")
            return

        self._running = True
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[TaskProcessor] Started with poll_interval={self.poll_interval}s")

    def stop(self):
        """
        停止后台任务处理器
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        print("[TaskProcessor] Stopped")

    def wake_up(self):
        """
        唤醒后台线程

        功能描述：
            由外部调用（如 add_task 创建新任务时），
            唤醒正在休眠的后台线程，使其立即检查新任务。
        """
        self._wake_event.set()

    def _run_loop(self):
        """
        后台轮询主循环

        实现逻辑：
            1. 每次循环尝试处理 pending 任务
            2. 如果有任务被处理，按 poll_interval 正常间隔继续轮询
            3. 如果没有待处理任务，通过 Event.wait 进入休眠模式，
               等待 60 秒或被 wake_up() 唤醒
            4. 被唤醒后立即检查是否有新任务
        """
        while self._running:
            try:
                has_pending = self._process_pending_tasks()
            except Exception as e:
                print(f"[TaskProcessor] Error in processing loop: {e}")
                has_pending = False

            if has_pending:
                # 有任务正在处理，按正常间隔继续轮询
                if self._in_sleep_mode:
                    print("[TaskProcessor] Woke up, found pending tasks")
                    self._in_sleep_mode = False
                time.sleep(self.poll_interval)
            else:
                # 没有待处理任务，进入休眠等待唤醒
                # 最大休眠 10 秒，确保重启时能快速恢复轮询已有任务
                if not self._in_sleep_mode:
                    print("[TaskProcessor] No pending tasks, entering sleep mode (waiting for wake-up)...")
                    self._in_sleep_mode = True
                self._wake_event.wait(timeout=10)
                self._wake_event.clear()

    def _process_pending_tasks(self):
        """
        处理所有 pending 状态的任务

        返回：
            True 表示有待处理任务需要继续轮询，False 表示没有任务可以休眠
        """
        pending_tasks = self._get_pending_tasks()

        if not pending_tasks:
            return False

        print(f"[TaskProcessor] Processing {len(pending_tasks)} pending tasks")

        for task in pending_tasks:
            if not self._running:
                break

            task_id = task['id']
            image_id = task.get('image_id')

            self._task_attempts[task_id] = self._task_attempts.get(task_id, 0) + 1

            try:
                self._process_single_task(task_id, image_id)
            except Exception as e:
                error_msg = str(e)
                print(f"[TaskProcessor] Error processing task {task_id}: {error_msg}")
                self._task_errors[task_id] = error_msg

            attempts = self._task_attempts.get(task_id, 0)
            if attempts >= self.max_retries:
                last_error = self._task_errors.get(task_id, '')
                fail_reason = last_error or f'任务查询超时（已尝试 {attempts} 次）'
                print(f"[TaskProcessor] Task {task_id} exceeded max retries ({attempts}/{self.max_retries}), fail_reason={fail_reason}, marking as failed")
                self._mark_task_failed(task_id, fail_reason)

        return True

    def _get_pending_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有 pending 状态的任务
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            placeholders = ', '.join(['?' for _ in PENDING_TASK_STATUSES])
            cursor.execute(f'''
                SELECT * FROM tasks
                WHERE status IN ({placeholders})
            ''', tuple(PENDING_TASK_STATUSES))

            rows = cursor.fetchall()
            result = []
            for row in rows:
                task = dict(row)
                if task['data']:
                    try:
                        import json
                        task['data'] = json.loads(task['data'])
                    except:
                        task['data'] = {}
                result.append(task)
            return result
        finally:
            conn.close()

    def _process_single_task(self, task_id: str, image_id: Optional[str]):
        """
        处理单个任务
        """
        with self._app.app_context():
            from routes.images import parse_task_query_result, normalize_task_status, get_image_service

            # 获取当前任务信息，用于判断 api_source
            current_task = get_task(task_id)
            # 解析任务 data 字段，获取模型等额外信息
            task_data = (current_task or {}).get('data', {}) or {}
            # 获取 api_source，默认为 't8'；历史任务里的 'openai' 仍按 T8 兼容处理。
            # fal.ai 来源的任务由专门的路由创建时设置 api_source='fal'
            api_source = (current_task or {}).get('api_source', 't8') or 't8'

            if api_source == 'gptsapi':
                # GPTsAPI 异步任务：通过 poll_url 轮询 GPTsAPI 获取结果
                poll_url = task_data.get('poll_url', '')
                if not poll_url:
                    print(f"[TaskProcessor] Task {task_id}: GPTsAPI task missing poll_url, marking as failed")
                    self._mark_task_failed(task_id, 'GPTsAPI 任务缺少 poll_url')
                    return

                try:
                    from services.gptsapi_image_service import GptsApiImageService
                    from models.config_model import get_single_config as get_db_single_config

                    gptsapi_config = get_db_single_config('gptsapi_api')
                    api_key = gptsapi_config.get('apiKey', '') or self._app.config.get('GPTSAPI_API_KEY', '')
                    base_url = gptsapi_config.get('baseUrl', '') or self._app.config.get('GPTSAPI_BASE_URL', 'https://api.gptsapi.net')
                    if not api_key:
                        print(f"[TaskProcessor] Task {task_id}: GPTsAPI API Key not configured")
                        return

                    gptsapi_service = GptsApiImageService(api_key=api_key, base_url=base_url)
                    query_result = gptsapi_service.query_result(poll_url)
                except Exception as e:
                    print(f"[TaskProcessor] Task {task_id}: Failed to create GPTsAPI service: {e}")
                    return

                if 'error' in query_result:
                    error_msg = str(query_result['error'])
                    print(f"[TaskProcessor] Task {task_id} GPTsAPI query error: {error_msg}")
                    consecutive = self._task_consecutive_errors.get(task_id, 0) + 1
                    self._task_consecutive_errors[task_id] = consecutive
                    self._task_errors[task_id] = error_msg
                    if consecutive >= 5:
                        print(f"[TaskProcessor] Task {task_id} GPTsAPI query failed {consecutive} consecutive times, marking as FAILURE")
                        self._mark_task_failed(task_id, f'连续 {consecutive} 次查询失败: {error_msg}')
                    return

                data = query_result.get('data', {}) or {}
                gptsapi_status = data.get('status', '')
                self._task_consecutive_errors.pop(task_id, None)

                if gptsapi_status == 'completed':
                    self._task_attempts.pop(task_id, None)
                    self._task_errors.pop(task_id, None)

                    # 从 GPTsAPI 结果中提取图片 URL
                    outputs = data.get('outputs', []) or []
                    image_urls = []
                    for item in outputs:
                        if isinstance(item, str) and item.startswith(('http://', 'https://')):
                            image_urls.append(item)
                        elif isinstance(item, dict):
                            url = item.get('url', '') or item.get('image_url', '') or ''
                            if url.startswith(('http://', 'https://')):
                                image_urls.append(url)

                    download_error = ''
                    current_image = get_image_by_task_id(task_id)

                    if image_urls and current_image:
                        first_url = image_urls[0]
                        current_image.url = first_url
                        update_image(current_image)

                        # 提交到后台下载队列
                        try:
                            from services.background_download_service import enqueue_image_download
                            enqueue_image_download(
                                image_id=current_image.id,
                                image_url=first_url,
                                image_type=getattr(current_image, 'image_type', 'generation') or 'generation',
                                folder_path=getattr(current_image, 'folder_path', None),
                                task_id=task_id
                            )
                        except Exception as err:
                            download_error = str(err)
                            print(f"[TaskProcessor] Failed to enqueue download for GPTsAPI task {task_id}: {err}")

                        # 额外的图片（多图生成时）
                        extra_urls = image_urls[1:]
                        if extra_urls:
                            print(f"[TaskProcessor] GPTsAPI task {task_id}: saving {len(extra_urls)} extra images")
                            from models.image_model import add_image as add_img_record
                            for idx, extra_url in enumerate(extra_urls):
                                try:
                                    extra_image = add_img_record(
                                        url=extra_url,
                                        thumbnail='',
                                        prompt=getattr(current_image, 'prompt', ''),
                                        model=task_data.get('model', ''),
                                        size=getattr(current_image, 'size', ''),
                                        quality=getattr(current_image, 'quality', 'auto'),
                                        task_id=task_id,
                                        image_type=getattr(current_image, 'image_type', 'generation') or 'generation',
                                        poster_copy=getattr(current_image, 'poster_copy', '') or ''
                                    )
                                    enqueue_image_download(
                                        image_id=extra_image.id,
                                        image_url=extra_url,
                                        image_type=getattr(current_image, 'image_type', 'generation') or 'generation',
                                        folder_path=getattr(current_image, 'folder_path', None),
                                        task_id=task_id
                                    )
                                except Exception as err:
                                    print(f"[TaskProcessor] Failed to save extra GPTsAPI image {idx+2}: {err}")
                    elif not image_urls:
                        download_error = 'GPTsAPI 任务完成但未获取到图片 URL'

                    update_task(
                        task_id,
                        image_id=current_image.id if current_image else None,
                        platform='gptsapi',
                        status='SUCCESS',
                        fail_reason='',
                        data={
                            'raw_query_result': query_result,
                            'image_url': image_urls[0] if image_urls else '',
                            'download_error': download_error,
                            'poll_url': poll_url
                        }
                    )
                    print(f"[TaskProcessor] GPTsAPI task {task_id} completed with {len(image_urls)} image(s)")
                    return

                elif gptsapi_status in ('failed', 'error') or data.get('error'):
                    self._task_attempts.pop(task_id, None)
                    self._task_errors.pop(task_id, None)
                    self._task_consecutive_errors.pop(task_id, None)
                    error_msg = data.get('error') or 'GPTsAPI 处理失败'
                    self._mark_task_failed(task_id, error_msg)
                    return

                # 仍在处理中，继续等待下一次轮询
                print(f"[TaskProcessor] GPTsAPI task {task_id}: status={gptsapi_status}, waiting...")
                return

            # 如果是 fal.ai 来源的任务，使用 FalImageService 查询状态并处理结果
            if api_source == 'fal':
                # 从任务 data 中提取模型名称和 response_url
                model = task_data.get('model', '')
                response_url = task_data.get('response_url', '')
                if not model:
                    print(f"[TaskProcessor] Task {task_id}: fal task missing model in data")
                    return

                # 获取 FAL_API_KEY 配置
                fal_api_key = self._app.config.get('FAL_API_KEY', '')
                if not fal_api_key:
                    print(f"[TaskProcessor] Task {task_id}: FAL_API_KEY not configured")
                    return

                fal_service = FalImageService(fal_api_key)

                # 查询 fal.ai 任务状态（传入 response_url 优先使用 API 返回的地址）
                status_result = fal_service.query_task_status(model, task_id, response_url)
                if 'error' in status_result:
                    error_msg = str(status_result['error'])
                    print(f"[TaskProcessor] Task {task_id} fal query status error: {error_msg}")

                    # 连续错误计数：连续 N 次查询都返回 error 时直接标记失败
                    consecutive = self._task_consecutive_errors.get(task_id, 0) + 1
                    self._task_consecutive_errors[task_id] = consecutive
                    self._task_errors[task_id] = error_msg

                    if consecutive >= 5:
                        print(f"[TaskProcessor] Task {task_id} fal query status failed {consecutive} consecutive times, marking as FAILURE")
                        self._mark_task_failed(task_id, f'连续 {consecutive} 次查询失败: {error_msg}')
                    return

                # 使用现有的 normalize_task_status 将 fal 原始状态映射为标准状态
                # 查询成功（无 error），清除连续错误计数
                self._task_consecutive_errors.pop(task_id, None)
                fal_raw_status = status_result.get('status', 'UNKNOWN')
                normalized_status = normalize_task_status(fal_raw_status)

                # UNKNOWN 兜底：如果标准化后为 UNKNOWN 且数据库中有之前的进行中状态，保留原状态继续轮询
                if normalized_status == 'UNKNOWN' and current_task:
                    previous_status = current_task.get('status')
                    if previous_status and previous_status not in {'SUCCESS', 'FAILURE'}:
                        normalized_status = previous_status

                # 获取当前关联的图片记录
                current_image = get_image_by_task_id(task_id)

                download_error = ''
                image_urls_list = []

                # 任务完成时获取结果图片
                if normalized_status == 'SUCCESS':
                    self._task_attempts.pop(task_id, None)
                    self._task_errors.pop(task_id, None)
                    self._task_consecutive_errors.pop(task_id, None)

                    # 获取 fal.ai 任务结果（传入 response_url 优先使用 API 返回的地址）
                    result_data = fal_service.get_task_result(model, task_id, response_url)
                    if 'error' in result_data:
                        error_msg = str(result_data['error'])
                        print(f"[TaskProcessor] Task {task_id} fal get result error: {error_msg}")

                        # 连续错误计数：连续 N 次获取结果失败时直接标记失败
                        consecutive = self._task_consecutive_errors.get(task_id, 0) + 1
                        self._task_consecutive_errors[task_id] = consecutive
                        self._task_errors[task_id] = error_msg

                        if consecutive >= 5:
                            print(f"[TaskProcessor] Task {task_id} fal get result failed {consecutive} consecutive times, marking as FAILURE")
                            self._mark_task_failed(task_id, f'连续 {consecutive} 次获取结果失败: {error_msg}')
                        return

                    # fal 结果结构为 {"images": [{"url": "...", "width": ..., "height": ...}]}
                    images = result_data.get('images', [])
                    if isinstance(images, list) and len(images) > 0:
                        for img in images:
                            if isinstance(img, dict):
                                img_url = img.get('url', '') or ''
                                if img_url:
                                    image_urls_list.append(img_url)

                    if image_urls_list:
                        # 第一张图片：更新当前关联的 image 记录，前端即可展示
                        first_url = image_urls_list[0]
                        if current_image:
                            current_image.url = first_url
                            update_image(current_image)

                            # 将第一张图片提交到后台下载队列
                            try:
                                from services.background_download_service import enqueue_image_download
                                enqueue_image_download(
                                    image_id=current_image.id,
                                    image_url=first_url,
                                    image_type=current_image.image_type or 'generation',
                                    folder_path=getattr(current_image, 'folder_path', None),
                                    task_id=task_id
                                )
                            except Exception as err:
                                download_error = str(err)
                                print(f"[TaskProcessor] Failed to enqueue download for fal task {task_id}: {err}")

                        # 额外的图片（num_images > 1 时）：创建独立的 image 记录并下载
                        extra_urls = image_urls_list[1:]
                        if extra_urls and current_image:
                            print(f"[TaskProcessor] Fal task {task_id}: downloading {len(extra_urls)} extra images")
                            from models.image_model import add_image
                            for idx, extra_url in enumerate(extra_urls):
                                try:
                                    # 为额外图片创建独立记录
                                    extra_image = add_image(
                                        url=extra_url,
                                        thumbnail='',
                                        prompt=getattr(current_image, 'prompt', ''),
                                        model=model,
                                        size=getattr(current_image, 'size', ''),
                                        quality=getattr(current_image, 'quality', 'auto'),
                                        task_id=task_id,
                                        image_type=getattr(current_image, 'image_type', 'generation') or 'generation',
                                        poster_copy=getattr(current_image, 'poster_copy', '') or ''
                                    )
                                    # 提交到后台下载队列
                                    enqueue_image_download(
                                        image_id=extra_image.id,
                                        image_url=extra_url,
                                        image_type=getattr(current_image, 'image_type', 'generation') or 'generation',
                                        folder_path=getattr(current_image, 'folder_path', None),
                                        task_id=task_id
                                    )
                                    print(f"[TaskProcessor] Fal task {task_id}: extra image {idx+2}/{len(image_urls_list)} saved (id={extra_image.id})")
                                except Exception as err:
                                    print(f"[TaskProcessor] Failed to save extra image {idx+2} for task {task_id}: {err}")
                    else:
                        download_error = 'fal 任务完成但未获取到图片 URL'

                # 取第一张图片 URL 作为主 image_url 存储
                first_image_url = image_urls_list[0] if image_urls_list else ''

                # FAILURE 状态时清理计数器
                if normalized_status == 'FAILURE':
                    self._task_attempts.pop(task_id, None)
                    self._task_errors.pop(task_id, None)
                    self._task_consecutive_errors.pop(task_id, None)

                # 更新任务状态到数据库
                update_task(
                    task_id,
                    image_id=current_image.id if current_image else None,
                    platform='fal',
                    status=normalized_status,
                    fail_reason='' if normalized_status != 'FAILURE' else (status_result.get('error', '') or ''),
                    submit_time=None,
                    start_time=None,
                    finish_time=None,
                    progress=str(status_result.get('queue_position', '')),
                    data={
                        'raw_query_result': status_result,
                        'image_url': first_image_url,
                        'revised_prompt': '',
                        'download_error': download_error
                    }
                )

                print(f"[TaskProcessor] Fal task {task_id} status updated to {normalized_status}")
                return

            service = get_image_service()
            result = service.query_task(task_id)

            if 'error' in result:
                error_msg = str(result['error'])
                print(f"[TaskProcessor] Task {task_id} query error from API: {error_msg}")
                self._task_errors[task_id] = error_msg
                return

            parsed_task = parse_task_query_result(result)
            current_image = get_image_by_task_id(task_id)
            current_task = get_task(task_id)

            # 标准化第三方 API 返回的状态值
            parsed_task['status'] = normalize_task_status(parsed_task['status'])

            # UNKNOWN 兜底：如果标准化后仍为 UNKNOWN 且数据库中有之前的进行中状态，保留原状态继续轮询
            if parsed_task['status'] == 'UNKNOWN' and current_task:
                previous_status = current_task.get('status')
                if previous_status and previous_status not in {'SUCCESS', 'FAILURE'}:
                    parsed_task['status'] = previous_status

            download_result = None
            download_error = ''

            if parsed_task['status'] == 'SUCCESS':
                self._task_attempts.pop(task_id, None)
                self._task_errors.pop(task_id, None)

                if current_image:
                    if parsed_task['revised_prompt']:
                        current_image.prompt = parsed_task['revised_prompt']

                    # 优先处理 b64_json 格式的图片数据
                    b64_data = parsed_task.get('b64_json', '')
                    image_url = parsed_task.get('image_url', '')
                    all_items = parsed_task.get('all_data_items', [])

                    if b64_data or (all_items and any(item.get('b64_json') for item in all_items)):
                        # 有 b64_json 数据：解码并保存到本地文件
                        import base64 as b64_module
                        from io import BytesIO
                        from PIL import Image as PILImage
                        from models.image_model import add_image as add_img_record

                        processed_count = 0
                        local_urls = []
                        items_to_process = all_items if all_items else [{'b64_json': b64_data}]

                        for item in items_to_process:
                            item_b64 = item.get('b64_json', '') if isinstance(item, dict) else ''
                            if not item_b64:
                                continue
                            try:
                                image_data = b64_module.b64decode(item_b64)
                                import uuid as uuid_module
                                filename = f"{uuid_module.uuid4().hex}.png"
                                generated_dir = os.path.join(
                                    os.path.dirname(os.path.dirname(__file__)),
                                    'generated_images'
                                )
                                os.makedirs(generated_dir, exist_ok=True)
                                local_filepath = os.path.join(generated_dir, filename)

                                with open(local_filepath, 'wb') as f:
                                    f.write(image_data)

                                local_url = f"/api/static/generated_images/{filename}"
                                local_urls.append(local_url)

                                if processed_count == 0:
                                    # 第一张图片更新到当前 image 记录
                                    current_image.url = local_url
                                    current_image.local_path = local_filepath
                                    update_image(current_image)
                                    # 生成缩略图
                                    try:
                                        from services.thumbnail_service import create_thumbnail_from_local
                                        create_thumbnail_from_local(local_filepath)
                                    except Exception as thumb_err:
                                        print(f"[TaskProcessor] Failed to create thumbnail for b64 task {task_id}: {thumb_err}")
                                else:
                                    # 额外图片创建独立记录
                                    extra_image = add_img_record(
                                        url=local_url,
                                        thumbnail='',
                                        prompt=getattr(current_image, 'prompt', ''),
                                        model=getattr(current_image, 'model', ''),
                                        size=getattr(current_image, 'size', ''),
                                        quality=getattr(current_image, 'quality', 'auto'),
                                        task_id=task_id,
                                        local_path=local_filepath,
                                        image_type=getattr(current_image, 'image_type', 'generation') or 'generation',
                                        poster_copy=getattr(current_image, 'poster_copy', '') or ''
                                    )
                                    try:
                                        from services.thumbnail_service import create_thumbnail_from_local
                                        thumb_result = create_thumbnail_from_local(local_filepath)
                                        extra_image.thumbnail = thumb_result.get('thumbnail_url', '')
                                        extra_image.thumbnail_path = thumb_result.get('thumbnail_path')
                                        update_image(extra_image)
                                    except Exception:
                                        pass

                                processed_count += 1
                                print(f"[TaskProcessor] Saved b64_json image {processed_count} for task {task_id}: {local_filepath}")

                            except Exception as b64_err:
                                print(f"[TaskProcessor] Failed to decode b64_json for task {task_id}: {b64_err}")
                                if processed_count == 0:
                                    download_error = f'b64_json解码失败: {str(b64_err)}'

                        if not local_urls:
                            download_error = download_error or '任务完成但 b64_json 数据为空'

                        # 使用第一个本地 URL 作为 image_url 写入 task data
                        image_url = local_urls[0] if local_urls else ''

                    elif image_url:
                        # URL 格式：立即写入远程 URL，前端即可展示图片
                        current_image.url = image_url
                        update_image(current_image)

                        # 将下载任务提交到后台下载队列
                        try:
                            from services.background_download_service import enqueue_image_download
                            enqueue_image_download(
                                image_id=current_image.id,
                                image_url=image_url,
                                image_type=current_image.image_type or 'generation',
                                folder_path=getattr(current_image, 'folder_path', None),
                                task_id=task_id
                            )
                        except Exception as err:
                            download_error = str(err)
                            print(f"[TaskProcessor] Failed to enqueue download for task {task_id}: {err}")

                        # 处理额外图片（n > 1 且 response_format=url）
                        if all_items and len(all_items) > 1:
                            from models.image_model import add_image as add_img_record
                            extra_urls = []
                            for item in all_items[1:]:
                                extra_url = item.get('url', '') if isinstance(item, dict) else ''
                                if extra_url:
                                    extra_urls.append(extra_url)
                            if extra_urls:
                                print(f"[TaskProcessor] Task {task_id}: processing {len(extra_urls)} extra images")
                                for idx, extra_url in enumerate(extra_urls):
                                    try:
                                        extra_image = add_img_record(
                                            url=extra_url,
                                            thumbnail='',
                                            prompt=getattr(current_image, 'prompt', ''),
                                            model=getattr(current_image, 'model', ''),
                                            size=getattr(current_image, 'size', ''),
                                            quality=getattr(current_image, 'quality', 'auto'),
                                            task_id=task_id,
                                            image_type=getattr(current_image, 'image_type', 'generation') or 'generation',
                                            poster_copy=getattr(current_image, 'poster_copy', '') or ''
                                        )
                                        enqueue_image_download(
                                            image_id=extra_image.id,
                                            image_url=extra_url,
                                            image_type=getattr(current_image, 'image_type', 'generation') or 'generation',
                                            folder_path=getattr(current_image, 'folder_path', None),
                                            task_id=task_id
                                        )
                                    except Exception as err:
                                        print(f"[TaskProcessor] Failed to save extra image for task {task_id}: {err}")
                    else:
                        download_error = '任务完成但未获取到图片数据（既无 URL 也无 b64_json）'

            # 获取当前轮询次数
            poll_count = self._task_attempts.get(task_id, 0)

            update_task(
                task_id,
                image_id=current_image.id if current_image else None,
                platform=parsed_task['platform'],
                status=parsed_task['status'],
                fail_reason=parsed_task['fail_reason'] if parsed_task['status'] == 'FAILURE' else '',
                submit_time=parsed_task['submit_time'],
                start_time=parsed_task['start_time'],
                finish_time=parsed_task['finish_time'],
                progress=parsed_task['progress'],
                data={
                    'raw_query_result': parsed_task['raw_result'],
                    'image_url': image_url if parsed_task['status'] == 'SUCCESS' else parsed_task['image_url'],
                    'revised_prompt': parsed_task['revised_prompt'],
                    'b64_json': parsed_task.get('b64_json', ''),
                    'download_error': download_error,
                    'poll_count': poll_count,
                    'max_polls': self.max_retries
                }
            )

            print(f"[TaskProcessor] Task {task_id} status updated to {parsed_task['status']} (poll #{poll_count})")

    def _mark_task_failed(self, task_id: str, reason: str):
        """
        将任务标记为失败
        """
        self._task_attempts.pop(task_id, None)
        self._task_errors.pop(task_id, None)
        self._task_consecutive_errors.pop(task_id, None)

        with self._app.app_context():
            update_task(
                task_id,
                status='FAILURE',
                fail_reason=reason
            )


_task_processor: Optional[TaskProcessor] = None


def get_task_processor() -> TaskProcessor:
    """
    获取全局任务处理器实例
    """
    global _task_processor
    if _task_processor is None:
        raise RuntimeError('Task processor not initialized. Call start_task_processor(app) first.')
    return _task_processor


def start_task_processor(app, poll_interval: int = None, max_retries: int = 300):
    """
    启动全局任务处理器

    参数：
        app: Flask 应用实例
        poll_interval: 轮询间隔（秒），如果为 None 则从数据库配置读取
        max_retries: 单个任务最大查询次数
    """
    global _task_processor
    
    # 如果没有指定 poll_interval，从数据库配置中读取
    if poll_interval is None:
        from models.config_model import get_db_config
        try:
            config = get_db_config('server_config')
            if config and 'poll_interval' in config:
                poll_interval = int(config['poll_interval'])
                print(f"[TaskProcessor] Loaded poll_interval from config: {poll_interval}s")
            else:
                poll_interval = 3  # 默认值，与构造函数默认值保持一致
                print(f"[TaskProcessor] No poll_interval in config, using default: {poll_interval}s")
        except Exception as e:
            print(f"[TaskProcessor] Failed to load poll_interval from config: {e}, using default: 3s")
            poll_interval = 3
    
    _task_processor = TaskProcessor(app, poll_interval, max_retries)
    _task_processor.start()


def stop_task_processor():
    """
    停止全局任务处理器
    """
    global _task_processor
    if _task_processor:
        _task_processor.stop()
        _task_processor = None


def notify_task_processor():
    """
    通知任务处理器有新任务创建

    功能描述：
        当 add_task 创建新任务时调用此函数，
        唤醒正在休眠的后台线程，使其立即处理新任务。
        如果 TaskProcessor 未启动则静默忽略。
    """
    if _task_processor:
        _task_processor.wake_up()
