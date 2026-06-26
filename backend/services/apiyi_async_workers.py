# APIYI 异步任务 worker 共享逻辑
#
# 功能描述：
#     把 _handle_apiyi_generation / _handle_apiyi_edit 内部的 worker 闭包
#     抽成模块级函数，让初次提交和 /apiyi/retry 都能复用同一份执行逻辑。
#     worker 仅负责「在 app context 内跑同步 APIYI 调用 + 落库 + 状态更新 + 清理 temp」
#     这几件事，参数由调用方提供；与路由层完全解耦。
#
# 实现逻辑：
#     1. run_apiyi_generation_worker：参数化 gen 执行（has_ref_images 决定 text_to_image / image_edit）
#     2. run_apiyi_edit_worker：参数化 edit 执行（恒走 image_edit）
#     3. 两者都遵循：仅 SUCCESS 时清理 temp 文件；FAILURE 保留 temp 供 retry 复用
#     4. 同步缩略图生成、b64 解码、URL 入队都按原 _worker 实现
#
# 异常处理：
#     - 所有异常统一捕获并 update_task(FAILURE)
#     - 静默子异常（如缩略图、update FAILURE）走 print 兜底
import os
from typing import Any, Dict, List, Optional

from services.thumbnail_service import create_thumbnail_from_local
from models.image_model import update_image_by_id, update_task
# 复用 TaskProcessor 的幂等判断，避免 URL 模式下重复入队
from services.task_processor import _should_skip_enqueue


# 文生图 / 带参考图的"伪生图"共用 worker
# 功能描述：
#     根据 has_ref_images 决定调用 image_edit 或 text_to_image；解析 data[0]
#     后写 image 记录并把 task 状态写为 SUCCESS；FAILURE 时仅记录原因
# 实现逻辑：
#     1. 在 app context 内获取 ImageDataProcessor（按需 import 避免循环）
#     2. b64_json：strip 前缀 → save_b64_image → 写 image 记录 + 缩略图
#     3. url：先写 url 让前端可见，再丢到后台下载队列
#     4. 异常统一捕获，update_task 失败时仅 print 不抛
# 异常处理：所有异常静默入 task.fail_reason；finally 块决定是否清 temp
def run_apiyi_generation_worker(
    app_obj: Any,
    service: Any,
    task_id: str,
    image: Any,
    image_paths: Optional[List[str]],
    prompt: str,
    size: str,
    response_format: str,
    has_ref_images: bool,
    model: str = 'gpt-image-2-vip',
    request_params: Optional[Dict[str, Any]] = None,
) -> None:
    succeeded = False
    with app_obj.app_context():
        try:
            creator_value = getattr(image, 'creator', '') or ''
            api_model = (model or 'gpt-image-2-vip').replace('apiyi/', '')
            if api_model == 'gpt-image-2':
                from services.apiyi_gpt_image2_service import ApiyiGptImage2Service
                gpt_image2_service = ApiyiGptImage2Service(
                    api_key=service.api_key,
                    base_url=service.base_url,
                )
                if has_ref_images and image_paths:
                    print(f"[apiyi_worker] gen task {task_id}: POST {gpt_image2_service.base_url}/v1/images/edits (gpt-image-2, {len(image_paths)} ref images)")
                    result = gpt_image2_service.image_edit(
                        prompt=prompt,
                        image_paths=image_paths,
                        size=size,
                        model=api_model,
                        params=request_params,
                    )
                else:
                    print(f"[apiyi_worker] gen task {task_id}: POST {gpt_image2_service.base_url}/v1/images/generations (gpt-image-2)")
                    result = gpt_image2_service.text_to_image(
                        prompt=prompt,
                        size=size,
                        model=api_model,
                        params=request_params,
                    )
            elif has_ref_images and image_paths:
                print(f"[apiyi_worker] gen task {task_id}: POST {service.base_url}/v1/images/edits (with {len(image_paths)} ref images)")
                result = service.image_edit(
                    prompt=prompt,
                    image_paths=image_paths,
                    size=size,
                    model=api_model,
                    response_format=response_format,
                )
            else:
                print(f"[apiyi_worker] gen task {task_id}: POST {service.base_url}/v1/images/generations")
                result = service.text_to_image(
                    prompt=prompt,
                    size=size,
                    model=api_model,
                    response_format=response_format,
                )
            if 'error' in result:
                raise RuntimeError(result.get('error', 'APIYI 调用失败'))

            data_list = result.get('data', [])
            if not data_list:
                raise RuntimeError('APIYI 响应无 data 字段')

            first = data_list[0] if isinstance(data_list[0], dict) else {}
            b64_json = first.get('b64_json', '')
            image_url = first.get('url', '')

            if b64_json:
                from services.image_processor import ImageDataProcessor
                cleaned_b64 = ImageDataProcessor.strip_b64_prefix(b64_json)
                output_dir = ImageDataProcessor.get_output_dir()
                from services.creator_storage import creator_storage_dir
                output_dir = creator_storage_dir(output_dir, creator_value)
                # 从 request_params 中读取用户选择的输出格式（png/jpeg/webp），
                # 让 save_b64_image 用对应扩展名落盘，避免“内容是 JPEG、文件名却是 .png”
                output_format = ''
                if isinstance(request_params, dict):
                    output_format = request_params.get('output_format') or request_params.get('outputFormat') or ''
                local_path, static_url, b64_err = ImageDataProcessor.save_b64_image(
                    cleaned_b64, output_dir, f'apiyi_gen_{task_id[:8]}', output_format
                )
                if b64_err:
                    raise RuntimeError(f'APIYI b64_json 保存失败: {b64_err}')
                thumb_result = create_thumbnail_from_local(local_path)
                update_image_by_id(image.id, {
                    'url': static_url,
                    'local_path': local_path,
                    'thumbnail': thumb_result.get('thumbnail_url', ''),
                    'thumbnail_path': thumb_result.get('thumbnail_path')
                })
            elif image_url:
                from services.background_download_service import enqueue_image_download
                update_image_by_id(image.id, {'url': image_url})
                if not _should_skip_enqueue(image.id):
                    enqueue_image_download(
                        image_id=image.id,
                        image_url=image_url,
                        image_type='generation',
                        folder_path=None,
                        task_id=task_id
                    )
            else:
                raise RuntimeError('APIYI 响应既无 url 也无 b64_json')

            update_task(task_id, status='SUCCESS', fail_reason='')
            succeeded = True
            print(f"[apiyi_worker] gen task {task_id} SUCCESS")
        except Exception as err:
            print(f"[apiyi_worker] gen task {task_id} FAILED: {err}")
            try:
                update_task(task_id, status='FAILURE', fail_reason=str(err))
            except Exception as update_err:
                print(f"[apiyi_worker] gen task {task_id} update FAILURE failed: {update_err}")
        finally:
            if succeeded and image_paths:
                for p in image_paths:
                    try:
                        if p and os.path.exists(p):
                            os.remove(p)
                    except OSError:
                        pass


# 图片编辑 worker
# 功能描述：
#     调用 service.image_edit，解析响应后走 save_edit_result_directly（编辑图专用目录）
#     b64 模式：本地写盘 → save_edit_result_directly（生成缩略图、走 edit_folders）
#     url 模式：save_edit_result_directly（内含下载）；失败则走后台下载队列兜底
# 实现逻辑：
#     1. b64 解析失败时回退到静态 URL 直写 + 同步缩略图
#     2. url 解析失败时入 enqueue_image_download 兜底
#     3. 异常统一捕获并 update_task(FAILURE)
# 异常处理：所有异常静默入 fail_reason；finally 决定是否清 temp
def run_apiyi_edit_worker(
    app_obj: Any,
    service: Any,
    task_id: str,
    image: Any,
    image_paths: List[str],
    prompt: str,
    size: str,
    response_format: str,
    model: str = 'gpt-image-2-vip',
    request_params: Optional[Dict[str, Any]] = None,
    mask_path: Optional[str] = None,
) -> None:
    succeeded = False
    with app_obj.app_context():
        try:
            creator_value = getattr(image, 'creator', '') or ''
            api_model = (model or 'gpt-image-2-vip').replace('apiyi/', '')
            if api_model == 'gpt-image-2':
                from services.apiyi_gpt_image2_service import ApiyiGptImage2Service
                gpt_image2_service = ApiyiGptImage2Service(
                    api_key=service.api_key,
                    base_url=service.base_url,
                )
                print(f"[apiyi_worker] edit task {task_id}: POST {gpt_image2_service.base_url}/v1/images/edits (gpt-image-2)")
                result = gpt_image2_service.image_edit(
                    prompt=prompt,
                    image_paths=image_paths,
                    mask_path=mask_path,
                    size=size,
                    model=api_model,
                    params=request_params,
                )
            else:
                print(f"[apiyi_worker] edit task {task_id}: POST {service.base_url}/v1/images/edits")
                result = service.image_edit(
                    prompt=prompt,
                    image_paths=image_paths,
                    size=size,
                    model=api_model,
                    response_format=response_format,
                )
            if 'error' in result:
                raise RuntimeError(result.get('error', 'APIYI 编辑调用失败'))

            data_list = result.get('data', [])
            if not data_list:
                raise RuntimeError('APIYI 响应无 data 字段')

            first = data_list[0] if isinstance(data_list[0], dict) else {}
            b64_json = first.get('b64_json', '')
            image_url = first.get('url', '')

            if b64_json:
                from services.image_processor import ImageDataProcessor
                # 延迟导入避免模块顶层循环依赖（edit_asset_service 内部用到 image_processor）
                from services.edit_asset_service import save_edit_result_directly
                cleaned_b64 = ImageDataProcessor.strip_b64_prefix(b64_json)
                output_dir = ImageDataProcessor.get_output_dir()
                from services.creator_storage import creator_storage_dir
                output_dir = creator_storage_dir(output_dir, creator_value)
                # 从 request_params 中读取用户选择的输出格式（png/jpeg/webp），
                # 让 save_b64_image 用对应扩展名落盘，避免“内容是 JPEG、文件名却是 .png”
                output_format = ''
                if isinstance(request_params, dict):
                    output_format = request_params.get('output_format') or request_params.get('outputFormat') or ''
                local_path, static_url, b64_err = ImageDataProcessor.save_b64_image(
                    cleaned_b64, output_dir, f'apiyi_edit_{task_id[:8]}', output_format
                )
                if b64_err:
                    raise RuntimeError(f'APIYI b64_json 保存失败: {b64_err}')
                try:
                    asset_result = save_edit_result_directly(static_url, prompt, size, creator=creator_value)
                    update_image_by_id(image.id, {
                        'url': asset_result.get('display_url') or static_url,
                        'local_path': asset_result.get('local_path') or local_path,
                        'thumbnail': asset_result.get('thumbnail', ''),
                        'thumbnail_path': asset_result.get('thumbnail_path')
                    })
                except Exception as asset_err:
                    print(f"[apiyi_worker] edit task {task_id} save_edit_result_directly failed: {asset_err}, fallback")
                    thumb_result = create_thumbnail_from_local(local_path)
                    update_image_by_id(image.id, {
                        'url': static_url,
                        'local_path': local_path,
                        'thumbnail': thumb_result.get('thumbnail_url', ''),
                        'thumbnail_path': thumb_result.get('thumbnail_path')
                    })
            elif image_url:
                from services.edit_asset_service import save_edit_result_directly
                from services.background_download_service import enqueue_image_download
                try:
                    asset_result = save_edit_result_directly(image_url, prompt, size, creator=creator_value)
                    update_image_by_id(image.id, {
                        'url': asset_result.get('display_url') or image_url,
                        'local_path': asset_result.get('local_path'),
                        'thumbnail': asset_result.get('thumbnail', ''),
                        'thumbnail_path': asset_result.get('thumbnail_path')
                    })
                except Exception as asset_err:
                    print(f"[apiyi_worker] edit task {task_id} download fallback: {asset_err}")
                    update_image_by_id(image.id, {'url': image_url})
                    if not _should_skip_enqueue(image.id):
                        enqueue_image_download(
                            image_id=image.id,
                            image_url=image_url,
                            image_type='edit',
                            folder_path=getattr(image, 'folder_path', ''),
                            task_id=task_id
                        )
            else:
                raise RuntimeError('APIYI 编辑响应既无 url 也无 b64_json')

            update_task(task_id, status='SUCCESS', fail_reason='')
            succeeded = True
            print(f"[apiyi_worker] edit task {task_id} SUCCESS")
        except Exception as err:
            print(f"[apiyi_worker] edit task {task_id} FAILED: {err}")
            try:
                update_task(task_id, status='FAILURE', fail_reason=str(err))
            except Exception as update_err:
                print(f"[apiyi_worker] edit task {task_id} update FAILURE failed: {update_err}")
        finally:
            if succeeded:
                cleanup_paths = list(image_paths or [])
                if mask_path:
                    cleanup_paths.append(mask_path)
                for p in cleanup_paths:
                    try:
                        if p and os.path.exists(p):
                            os.remove(p)
                    except OSError:
                        pass
