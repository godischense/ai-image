# APIYI 异步任务重试服务
#
# 功能描述：
#     为 /api/images/apiyi/retry 接口提供任务重试能力。
#     服务内部处理 429 / 5xx 仅能覆盖短时限流；当 APIYI 触发长时限流（小时级/日级）
#     或用户希望重试失败任务时，由该服务接管：校验任务、复用或重建 temp 文件、
#     重置任务状态、重新提交到 _apiyi_executor。
#
# 实现逻辑：
#     1. 校验任务存在 + platform='apiyi' + status='FAILURE'（SUCCESS 不允许重试）
#     2. 读取 task.data 中的 prompt / size / response_format / image_paths / parent_id
#     3. 检查 image_paths 中所有文件仍存在；若缺失则返回明确错误（不尝试重建）
#     4. 校验 image 记录仍存在
#     5. 重置 task.status='IN_PROGRESS'、清空 fail_reason、记录 retry 次数
#     6. 根据 image.image_type 决定走 run_apiyi_generation_worker 还是 run_apiyi_edit_worker
#     7. 把 worker 重新提交到 _apiyi_executor
#
# 异常处理：
#     - 任务不存在 / 平台错误 / 状态非 FAILURE：返回 dict 含 ok=False + 错误码
#     - temp 文件缺失：返回 ok=False + 'temp_files_missing'，让前端提示用户重新提交
#     - image 记录被删除：返回 ok=False + 'image_missing'
#     - 提交到 executor 失败：恢复 task.status='FAILURE'，避免状态丢失
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Tuple

from flask import current_app

from models.image_model import (
    get_image_by_id,
    get_image_by_task_id,
    get_task,
    update_task,
)


# 失败任务重试入口
# 功能描述：
#     把指定 task_id 的失败 APIYI 任务重新提交到 _apiyi_executor 执行
# 实现逻辑：
#     1. validate_retry_task 做完整校验，返回可重试上下文（含 image / image_paths / data）
#     2. 调用 reset_task_for_retry 重置任务状态
#     3. 按 image.image_type 重新走对应的 worker 模块函数
#     4. 返回 ok / status 字段给路由层
# 异常处理：
#     - 校验失败时 ok=False，error_code 可定位问题
#     - executor.submit 失败时回滚任务状态
def retry_apiyi_task(task_id: str, apiyi_executor: ThreadPoolExecutor) -> Dict[str, Any]:
    """
    重试 APIYI 失败任务

    参数：
        task_id: 失败任务的 ID
        apiyi_executor: 路由层传入的 _apiyi_executor（避免循环 import）
    """
    ok, context, err_code, err_msg = validate_retry_task(task_id)
    if not ok:
        return {'ok': False, 'error_code': err_code, 'error': err_msg}

    # 重新提交前先重置任务状态，避免被前端误判为终态
    retry_count = (context['data'].get('retry_count') or 0) + 1
    data_with_count = dict(context['data'])
    data_with_count['retry_count'] = retry_count
    reset_task_for_retry(task_id, data_with_count)

    # 抽到 services.apiyi_async_workers 的 worker，参数化调用
    from services.apiyi_async_workers import run_apiyi_generation_worker, run_apiyi_edit_worker

    image = context['image']
    image_paths = context['image_paths']
    data = context['data']
    app_obj = current_app._get_current_object()
    # service 走单例工厂，避免 retry 路径与原 handler 各自新建导致连接池分散
    from routes.images import get_apiyi_image_service
    try:
        service = get_apiyi_image_service()
    except ValueError as svc_err:
        return {
            'ok': False,
            'error_code': 'service_unavailable',
            'error': f'APIYI 服务初始化失败: {svc_err}',
        }

    try:
        if context['image_type'] == 'edit':
            apiyi_executor.submit(
                run_apiyi_edit_worker,
                app_obj,
                service,
                task_id,
                image,
                image_paths,
                data.get('prompt', ''),
                data.get('size', 'auto'),
                data.get('response_format', 'b64_json'),
                data.get('model', 'gpt-image-2-vip'),
                data.get('request_params') or {},
                data.get('mask_path') or None,
            )
        else:
            has_ref_images = bool(image_paths)
            apiyi_executor.submit(
                run_apiyi_generation_worker,
                app_obj,
                service,
                task_id,
                image,
                image_paths,
                data.get('prompt', ''),
                data.get('size', 'auto'),
                data.get('response_format', 'b64_json'),
                has_ref_images,
                data.get('model', 'gpt-image-2-vip'),
                data.get('request_params') or {},
            )
    except Exception as submit_err:
        try:
            update_task(
                task_id,
                status='FAILURE',
                fail_reason=f'APIYI 重试提交失败: {submit_err}',
            )
        except Exception:
            pass
        return {
            'ok': False,
            'error_code': 'submit_failed',
            'error': f'重试提交到执行器失败: {submit_err}',
        }

    return {
        'ok': True,
        'task_id': task_id,
        'image_id': image.id,
        'retry_count': retry_count,
    }


# 校验任务是否可重试，并组装 worker 所需的全部上下文
# 实现逻辑：
#     1. 读 task 行；不在 → 'task_not_found'
#     2. platform/api_source 不匹配 → 'platform_mismatch'
#     3. status != FAILURE → 'status_not_failure'（SUCCESS 也禁止重试）
#     4. data 字段缺失或非 dict → 'data_invalid'
#     5. image 记录查找：先用 task.image_id；缺失则用 task_id 反查；都没有 → 'image_missing'
#     6. image_paths 若声明则每项必须 os.path.exists；任一缺失 → 'temp_files_missing'
# 异常处理：所有 dict.get 容错；找不到字段时返回明确的 error_code
def validate_retry_task(task_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str, str]:
    task = get_task(task_id)
    if not task:
        return False, None, 'task_not_found', '任务不存在'

    platform = task.get('platform', '')
    api_source = (task.get('data') or {}).get('api_source', '')
    if platform != 'apiyi' or api_source != 'apiyi':
        return False, None, 'platform_mismatch', '该任务不是 APIYI 平台任务'

    status = task.get('status', '')
    if status != 'FAILURE':
        return False, None, 'status_not_failure', f'任务当前状态为 {status}，仅 FAILURE 可重试'

    data = task.get('data')
    if not isinstance(data, dict):
        return False, None, 'data_invalid', '任务数据缺失或格式错误'

    # 查找 image 记录：先按 image_id，找不到再用 task_id 兜底
    image = None
    image_id = task.get('image_id')
    if image_id:
        image = get_image_by_id(image_id)
    if image is None:
        image = get_image_by_task_id(task_id)
    if image is None:
        return False, None, 'image_missing', '图片记录不存在，无法重试'

    # 校验临时文件：FAILURE 时 worker 已不删 temp（仅 SUCCESS 才删）
    image_paths = data.get('image_paths') or []
    if image_paths:
        missing = [p for p in image_paths if not (p and os.path.exists(p))]
        if missing:
            return False, None, 'temp_files_missing', (
                f'临时文件已失效（{len(missing)} 个），请重新提交任务'
            )

    mask_path = data.get('mask_path') or ''
    if mask_path and not os.path.exists(mask_path):
        return False, None, 'temp_files_missing', 'mask 临时文件已失效，请重新提交任务'

    image_type = getattr(image, 'image_type', None) or data.get('image_type') or 'generation'
    context = {
        'image': image,
        'image_paths': image_paths,
        'data': data,
        'image_type': image_type,
    }
    return True, context, '', ''


# 重置任务状态为 IN_PROGRESS 并写入新的 retry_count
# 实现逻辑：
#     1. status='IN_PROGRESS'，fail_reason=''
#     2. data 合并 retry_count 后写回（保留原 prompt / size / image_paths 等）
# 异常处理：update_task 失败时向上抛，由 retry_apiyi_task 捕获并返回 submit_failed
def reset_task_for_retry(task_id: str, data_with_retry_count: Dict[str, Any]) -> None:
    update_task(
        task_id,
        status='IN_PROGRESS',
        fail_reason='',
        data=data_with_retry_count,
    )
