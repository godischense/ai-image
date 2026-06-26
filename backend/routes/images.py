import os
import json
import base64
import mimetypes
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import requests as requests_lib
from flask import Blueprint, request, jsonify, current_app
from services.image_service import ImageService
from services.fal_image_service import FalImageService
from services.gptsapi_image_service import GptsApiImageService
from services.apiyi_image_service import ApiyiImageService
from services.file_upload_service import FileUploadService
from services.download_service import download_image_to_local, delete_local_file
from services.thumbnail_service import create_thumbnail_from_local
from services.edit_asset_service import (
    EDIT_THUMBNAIL_STATIC_PREFIX,
    save_edit_result_directly
)
from models.image_model import (
    load_images,
    add_image,
    add_task,
    delete_image,
    get_image_by_id,
    get_image_by_task_id,
    get_task,
    rename_image,
    update_image,
    update_task,
    add_edit_relation,
    get_image_edits,
    get_edit_relation_by_image_id,
    update_image_folder_path,
    build_static_url_from_local_path,
    repair_image_file_reference
)
from services.folder_service import (
    rename_edit_folder
)
from models.config_model import get_single_config as get_db_single_config
from services.auth_service import current_creator, current_user_is_admin, scoped_creator
# APIYI 后台线程下载时复用 TaskProcessor 的幂等判断（已下载完成则跳过入队）
from services.task_processor import _should_skip_enqueue

images_bp = Blueprint('images', __name__)
FINAL_TASK_STATUSES = {'SUCCESS', 'FAILURE'}
THUMBNAIL_STATIC_PREFIX = '/api/static/generated_thumbnails/'

# APIYI 异步任务专用 ThreadPoolExecutor
# 功能描述：
#     把 APIYI gpt-image-2-vip 同步请求（典型 90-150s）丢进后台线程执行，
#     路由层立即返回 task_id 给前端，由 worker 在后台完成结果落库。
# 实现逻辑：
#     1. 模块级单例 executor，避免每次请求都新建池子
#     2. max_workers=4 与 gptsapi 处理能力对齐，叠加 APIYI 出图较慢
#     3. thread_name_prefix 便于日志定位
# 异常处理：
#     worker 内部 try/except 全部异常，标记 task FAILURE；
#     executor 自身不抛错（任务失败通过返回值/异常体现）
_apiyi_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='apiyi-async')


def _safe_delete_file(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        os.remove(path)
        return True
    except OSError as err:
        print(f"[images] Warning: failed to delete old thumbnail {path}: {err}")
        return False


def _old_thumbnail_path_for_image(image_item) -> str:
    image_type = getattr(image_item, 'image_type', 'generation') or 'generation'
    if image_type == 'edit':
        thumbnail_path = (getattr(image_item, 'thumbnail_path', None) or '').strip()
        if thumbnail_path:
            return thumbnail_path

        thumbnail = (getattr(image_item, 'thumbnail', None) or '').strip()
        if thumbnail.startswith(EDIT_THUMBNAIL_STATIC_PREFIX):
            from services.edit_asset_service import EDIT_THUMBNAILS_DIR
            filename = thumbnail.replace(EDIT_THUMBNAIL_STATIC_PREFIX, '', 1)
            return os.path.join(EDIT_THUMBNAILS_DIR, filename)
        return ''

    return get_generated_thumbnail_file_path(image_item)


def _repair_one_image_thumbnail_to_jpg(image_item) -> dict:
    source_path = (getattr(image_item, 'local_path', None) or '').strip()
    if not source_path or not os.path.isfile(source_path):
        repair_image_file_reference(image_item)
        source_path = (getattr(image_item, 'local_path', None) or '').strip()

    if not source_path or not os.path.isfile(source_path):
        return {'success': False, 'error': 'source image missing'}

    old_thumbnail_path = _old_thumbnail_path_for_image(image_item)
    image_type = getattr(image_item, 'image_type', 'generation') or 'generation'

    if image_type == 'edit':
        from services.edit_asset_service import create_edit_thumbnail_from_local
        result = create_edit_thumbnail_from_local(source_path, getattr(image_item, 'folder_path', '') or '')
    else:
        result = create_thumbnail_from_local(source_path)

    new_thumbnail_url = result.get('thumbnail_url', '')
    new_thumbnail_path = result.get('thumbnail_path', '')
    if not new_thumbnail_url or not new_thumbnail_path:
        return {'success': False, 'error': 'thumbnail generation returned empty result'}

    image_item.thumbnail = new_thumbnail_url
    image_item.thumbnail_path = new_thumbnail_path
    update_image(image_item)

    if old_thumbnail_path and os.path.abspath(old_thumbnail_path) != os.path.abspath(new_thumbnail_path):
        _safe_delete_file(old_thumbnail_path)

    return {'success': True, 'thumbnail': new_thumbnail_url}


def _repair_material_thumbnails_to_jpg() -> dict:
    from services.material_service import MATERIAL_DIR, is_image_file
    from services.material_thumbnail_service import create_material_thumbnail

    processed = 0
    succeeded = 0
    failed = 0

    if not os.path.isdir(MATERIAL_DIR):
        return {'processed': 0, 'succeeded': 0, 'failed': 0}

    for root, _, files in os.walk(MATERIAL_DIR):
        for filename in files:
            if not is_image_file(filename):
                continue
            processed += 1
            source_path = os.path.join(root, filename)
            try:
                result = create_material_thumbnail(source_path)
                if result.get('success') and str(result.get('filename', '')).lower().endswith('.jpg'):
                    succeeded += 1
                else:
                    failed += 1
            except Exception as err:
                failed += 1
                print(f"[images] Warning: failed to repair material thumbnail {source_path}: {err}")

    return {'processed': processed, 'succeeded': succeeded, 'failed': failed}


def get_generated_thumbnail_file_path(image_item) -> str:
    """
    解析普通生图缩略图本地路径

    功能描述：
        将数据库中的 thumbnail_path 或 thumbnail URL 统一转换为本地文件路径，用于判断缩略图文件是否仍然存在。

    实现逻辑：
        1. 优先使用已落库的 thumbnail_path
        2. 当 thumbnail_path 缺失时，尝试从缩略图 URL 反推文件路径
        3. 仅处理普通生图 generated_thumbnails 目录，其他类型返回空字符串
    """
    thumbnail_path = (getattr(image_item, 'thumbnail_path', None) or '').strip()
    if thumbnail_path:
        return thumbnail_path

    thumbnail_url = (getattr(image_item, 'thumbnail', None) or '').strip()
    if not thumbnail_url.startswith(THUMBNAIL_STATIC_PREFIX):
        return ''

    thumbnail_filename = thumbnail_url.replace(THUMBNAIL_STATIC_PREFIX, '', 1)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, 'generated_thumbnails', thumbnail_filename)


def serialize_image(image_item):
    """
    序列化图片对象

    功能描述：
        为前端统一补充 display_url、imageType 等兼容字段，避免各页面自行拼装。
    """
    if not image_item:
        return None

    repair_image_file_reference(image_item)
    payload = dict(image_item.__dict__)
    resolved_url = image_item.url or ''
    local_static_url = build_static_url_from_local_path(getattr(image_item, 'local_path', None))
    if local_static_url and local_static_url != resolved_url:
        payload['url'] = local_static_url
        resolved_url = local_static_url

    payload['display_url'] = resolved_url
    payload['imageType'] = image_item.image_type or 'generation'
    payload['taskId'] = image_item.task_id
    # api_source: prefer stored source, with model-prefix fallback for older rows.
    model_name = getattr(image_item, 'model', '') or ''
    stored_api_source = (getattr(image_item, 'api_source', None) or '').strip().lower()
    if stored_api_source in {'fal', 'gptsapi', 'apiyi', 'openai', 't8'}:
        payload['apiSource'] = 'openai' if stored_api_source == 't8' else stored_api_source
    elif model_name.startswith('openai/'):
        payload['apiSource'] = 'fal'
    elif model_name.startswith('gptsapi/'):
        payload['apiSource'] = 'gptsapi'
    elif model_name.startswith('apiyi/'):
        payload['apiSource'] = 'apiyi'
    else:
        payload['apiSource'] = 'openai'
    # 确保 created_at 字段存在，用于排序
    if 'created_at' not in payload:
        payload['created_at'] = datetime.now().isoformat()
    # 将 JSON 字符串格式的 size（如 {"width": 1280, "height": 720}）转回 "1280x720"
    size_raw = payload.get('size', '')
    payload['size'] = _normalize_display_size(size_raw)
    return payload


def get_inherited_poster_copy(parent_id):
    if not parent_id:
        return ''
    parent_image = get_image_by_id(parent_id)
    return (getattr(parent_image, 'poster_copy', '') or '') if parent_image else ''


# 继承父图的制作人字段，用于编辑链路（未显式传入 creator 时回退到父图）
# 当 parent_id 不存在或父图未找到时返回空字符串
def get_inherited_creator(parent_id):
    if not parent_id:
        return ''
    parent_image = get_image_by_id(parent_id)
    return (getattr(parent_image, 'creator', '') or '') if parent_image else ''


def build_edit_prompt_history(base_prompt, edit_prompt):
    base_prompt = (base_prompt or '').strip()
    edit_prompt = (edit_prompt or '').strip()
    existing_counts = [int(match) for match in re.findall(r'编辑(\d+)次', base_prompt)]
    next_count = (max(existing_counts) + 1) if existing_counts else 1
    parts = []
    if base_prompt:
        parts.append(base_prompt)
    parts.append(f'编辑{next_count}次')
    if edit_prompt:
        parts.append(edit_prompt)
    return ' | '.join(parts)


def build_edit_saved_prompt(parent_id, edit_prompt):
    parent_image = get_image_by_id(parent_id) if parent_id else None
    base_prompt = getattr(parent_image, 'prompt', '') if parent_image else ''
    return build_edit_prompt_history(base_prompt, edit_prompt)


def build_edit_tree_node(image_item, parent_id=None, depth=0):
    """
    构建编辑树节点

    功能描述：
        将后端图片对象统一映射为编辑页使用的树节点结构。
    """
    repair_image_file_reference(image_item)
    resolved_url = image_item.url or ''
    local_static_url = build_static_url_from_local_path(getattr(image_item, 'local_path', None))
    if local_static_url:
        resolved_url = local_static_url

    return {
        'id': image_item.id,
        'parentId': parent_id,
        'imageUrl': resolved_url,
        'displayUrl': resolved_url,
        'thumbnail': image_item.thumbnail or '',
        'prompt': image_item.prompt or '',
        'title': image_item.title,
        'generating': image_item.generating,
        'taskId': image_item.task_id,
        'error': image_item.download_error or image_item.fail_reason or '',
        'size': _normalize_display_size(getattr(image_item, 'size', '')),
        'folderPath': image_item.folder_path,
        'imageType': image_item.image_type or 'generation',
        'depth': depth
    }


def find_nested_value(payload, key):
    """
    递归查找嵌套字段值

    功能描述：
        在第三方接口的多层响应结构中递归提取目标字段，兼容状态不在固定层级的情况

    实现逻辑：
        1. 字典优先读取当前层
        2. 当前层不存在时继续递归子项
        3. 列表会逐项递归查找
        4. 未找到时返回 None，避免误判为终态
    """
    if isinstance(payload, dict):
        if key in payload and payload.get(key) not in (None, ''):
            return payload.get(key)

        for value in payload.values():
            found_value = find_nested_value(value, key)
            if found_value not in (None, ''):
                return found_value

    if isinstance(payload, list):
        for item in payload:
            found_value = find_nested_value(item, key)
            if found_value not in (None, ''):
                return found_value

    return None


def find_first_image_data(payload):
    """
    递归提取首个图片结果对象

    功能描述：
        在第三方查询结果中查找包含图片 URL 的第一个图片对象，兼容层级变化

    实现逻辑：
        1. 如果当前是带 url 的字典，直接返回
        2. 如果是字典，优先递归其 value
        3. 如果是列表，顺序查找首个匹配项
        4. 未找到时返回空字典，交由上层兜底
    """
    if isinstance(payload, dict):
        if payload.get('url'):
            return payload

        for value in payload.values():
            found_image = find_first_image_data(value)
            if found_image:
                return found_image

    if isinstance(payload, list):
        for item in payload:
            found_image = find_first_image_data(item)
            if found_image:
                return found_image

    return {}


def extract_async_task_id(result):
    """
    提取异步任务 ID

    功能描述：
        兼容第三方接口不同返回格式，优先提取真实 task_id

    实现逻辑：
        1. 优先读取显式 task_id 字段
        2. 兼容文档中的 data 字段直接返回 task_id 字符串
        3. 最后兜底读取历史代码使用过的 id 字段
    """
    task_id = result.get('task_id')
    if task_id:
        return task_id

    data = result.get('data')
    if isinstance(data, str) and data:
        return data

    return result.get('id')


# 将第三方 API 返回的各种状态值统一映射为标准状态
# 功能描述：
#   第三方 API 可能返回各种状态变体（大小写不同、拼写不同），
#   需要统一映射到后端和前端约定的标准状态值，避免状态不匹配导致任务卡死。
# 实现逻辑：
#   1. 终态映射：succeeded/completed/done 等 → SUCCESS，failed/error 等 → FAILURE
#   2. 进行中映射：in_progress/processing/running/not_start 等 → IN_PROGRESS
#   3. 如果已有状态在 PENDING_TASK_STATUSES 中，保留原值
#   4. 无法识别的状态也映射到 IN_PROGRESS（保守策略：只要第三方 API 还在返回数据就继续轮询）
# 异常处理：
#   - 空值/None 返回 'UNKNOWN'
#   - 无法识别的状态返回 'IN_PROGRESS'（让 TaskProcessor 继续轮询，避免任务消失）
def normalize_task_status(raw_status: str) -> str:
    if not raw_status:
        return 'UNKNOWN'

    status_lower = str(raw_status).strip().lower()

    # 终态 → SUCCESS
    success_variants = {
        'succeeded', 'success', 'completed', 'complete',
        'done', 'finished', 'ready', 'ok'
    }
    if status_lower in success_variants:
        return 'SUCCESS'

    # 终态 → FAILURE
    failure_variants = {
        'failed', 'failure', 'fail', 'error', 'cancelled',
        'canceled', 'timeout', 'expired', 'aborted'
    }
    if status_lower in failure_variants:
        return 'FAILURE'

    # 明确的进行中状态 → IN_PROGRESS
    progress_variants = {
        'in_progress', 'inprogress', 'processing', 'running',
        'not_start', 'notstart', 'not_started', 'notstarted',
        'pending', 'queued', 'waiting', '未启动'
    }
    if status_lower in progress_variants:
        return 'IN_PROGRESS'

    # 如果原始状态已经在已知的 PENDING 集合中，保持原样
    if raw_status in ('PENDING', 'IN_PROGRESS', '未启动', 'QUEUED', 'NOT_STARTED', 'NOT_START', 'WAITING'):
        return raw_status

    if raw_status in ('SUCCESS', 'FAILURE'):
        return raw_status

    # 无法识别的状态，兜底返回 IN_PROGRESS
    # 原因：只要第三方 API 还在返回数据，TaskProcessor 就应继续轮询
    # 如果返回 UNKNOWN，会走 UNKNOWN 兜底逻辑保留上一次的状态
    # 但如果上一次也不是标准状态，任务就会进入"死区"
    # 所以这里返回 IN_PROGRESS 保证任务持续被轮询
    print(f"[images] Unknown task status from API: '{raw_status}', treating as IN_PROGRESS for safety")
    return 'IN_PROGRESS'


def parse_task_query_result(result):
    """
    解析异步任务查询结果

    功能描述：
        将第三方任务查询结果统一转换为后端可落库、前端可消费的标准结构

    实现逻辑：
        1. 优先按文档读取 data.status 等嵌套字段
        2. 兼容历史接口可能存在的顶层字段
        3. 提取首张图片 URL、b64_json 数据和所有图片列表
        4. 提取修订后的提示词和时间元数据
        5. 保留完整原始结果，便于失败时排查问题
    """
    task_payload = result.get('data') if isinstance(result.get('data'), dict) else {}
    first_image = find_first_image_data(task_payload) or find_first_image_data(result)

    # 提取所有图片数据项，支持 url 和 b64_json 两种格式
    all_data_items = []
    data_list = task_payload.get('data', []) if isinstance(task_payload, dict) else []
    if not data_list:
        data_list = result.get('data', [])
    if isinstance(data_list, list):
        all_data_items = data_list
    elif isinstance(data_list, dict) and data_list:
        all_data_items = [data_list]

    return {
        'status': find_nested_value(task_payload, 'status') or result.get('status') or 'UNKNOWN',
        'platform': find_nested_value(task_payload, 'platform') or result.get('platform') or '',
        'fail_reason': find_nested_value(task_payload, 'fail_reason') or result.get('fail_reason') or '',
        'progress': find_nested_value(task_payload, 'progress') or result.get('progress') or '',
        'submit_time': find_nested_value(task_payload, 'submit_time'),
        'start_time': find_nested_value(task_payload, 'start_time'),
        'finish_time': find_nested_value(task_payload, 'finish_time'),
        'image_url': first_image.get('url', ''),
        'b64_json': first_image.get('b64_json', ''),
        'revised_prompt': first_image.get('revised_prompt', ''),
        'all_data_items': all_data_items,
        'raw_result': result
    }


def is_thumbnail_missing(image_item) -> bool:
    """
    判断图片是否缺少真实缩略图

    功能描述：
        识别未生成缩略图、缩略图为空或错误使用原图地址充当缩略图的情况。
    """
    thumbnail = (image_item.thumbnail or '').strip()
    if not thumbnail:
        return True

    if thumbnail == image_item.url:
        return True

    if not thumbnail.startswith(THUMBNAIL_STATIC_PREFIX):
        return True

    thumbnail_file_path = get_generated_thumbnail_file_path(image_item)
    if not thumbnail_file_path:
        return True

    return not os.path.exists(thumbnail_file_path)


def build_thumbnail_for_local_image(local_path: str) -> str:
    """
    基于本地原图生成缩略图 URL

    功能描述：
        将缩略图生成细节收口到一个辅助函数中，路由层只关心返回的缩略图地址。
    """
    thumbnail_result = create_thumbnail_from_local(local_path)
    return thumbnail_result.get('thumbnail_url', '')


def _creator_from_request(value: str = '') -> str:
    return scoped_creator(value)


def _image_scope_creator():
    return None if current_user_is_admin() else current_creator()


def _get_scoped_image_by_id(image_id: str):
    return get_image_by_id(image_id, creator=_image_scope_creator())


def prepare_generation_assets(image_url: str, existing_local_path: str = None, creator: str = '') -> dict:
    """
    准备普通生图资产

    功能描述：
        统一处理普通生图的原图下载与缩略图生成。
    """
    return prepare_image_assets(image_url, existing_local_path, creator)


def prepare_image_assets(image_url: str, existing_local_path: str = None, creator: str = '') -> dict:
    """
    准备原图与缩略图资产

    功能描述：
        统一处理图片下载、缩略图生成和失败兜底，保证列表与预览使用不同资源。

    实现逻辑：
        1. 优先复用已有本地原图
        2. 本地原图不存在时尝试下载远程原图
        3. 基于本地原图生成缩略图
        4. 下载或缩略图失败时返回错误，由上层决定是否兜底展示
    """
    resolved_url = (image_url or '').strip()
    resolved_local_path = (existing_local_path or '').strip() or None
    original_display_url = resolved_url
    asset_error = ''

    if not resolved_local_path and resolved_url:
        download_result = download_image_to_local(resolved_url, creator=creator)
        resolved_local_path = download_result.get('local_path')
        original_display_url = download_result.get('local_url') or resolved_url
    elif resolved_local_path and os.path.exists(resolved_local_path):
        filename = os.path.basename(resolved_local_path)
        original_display_url = f"/api/static/generated_images/{filename}"

    thumbnail_url = ''
    if resolved_local_path and os.path.exists(resolved_local_path):
        try:
            thumbnail_result = create_thumbnail_from_local(resolved_local_path)
            thumbnail_url = thumbnail_result.get('thumbnail_url', '')
            thumbnail_path = thumbnail_result.get('thumbnail_path')
        except (ValueError, RuntimeError) as err:
            asset_error = str(err)
            thumbnail_path = None
    else:
        thumbnail_path = None

    return {
        'url': original_display_url,
        'thumbnail': thumbnail_url,
        'local_path': resolved_local_path,
        'thumbnail_path': thumbnail_path,
        'error': asset_error
    }


def is_edit_thumbnail_missing(image_item) -> bool:
    """
    判断编辑图片是否缺少真实缩略图

    功能描述：
        检查编辑图片的缩略图是否存在有效文件。
    """
    from services.edit_asset_service import EDIT_THUMBNAIL_STATIC_PREFIX

    thumbnail = (image_item.thumbnail or '').strip()
    if not thumbnail:
        return True

    if thumbnail == image_item.url:
        return True

    if not thumbnail.startswith(EDIT_THUMBNAIL_STATIC_PREFIX):
        return True

    # 从 URL 反推缩略图文件路径
    filename = thumbnail.replace(EDIT_THUMBNAIL_STATIC_PREFIX, '', 1)
    from services.edit_asset_service import EDIT_THUMBNAILS_DIR
    file_path = os.path.join(EDIT_THUMBNAILS_DIR, filename)
    return not os.path.exists(file_path)


def repair_thumbnail_if_needed(image_item) -> bool:
    """
    为已有图片补齐缩略图

    功能描述：
        兼容历史记录中 thumbnail 仍指向原图的情况，读取列表时补生成真实缩略图。
    """
    if image_item.image_type == 'edit':
        return repair_edit_thumbnail_if_needed(image_item)

    if not image_item or not image_item.local_path or not os.path.exists(image_item.local_path):
        return False

    if not is_thumbnail_missing(image_item):
        return False

    thumbnail_result = create_thumbnail_from_local(image_item.local_path)
    thumbnail_url = thumbnail_result.get('thumbnail_url', '')
    image_item.thumbnail = thumbnail_url
    image_item.thumbnail_path = thumbnail_result.get('thumbnail_path')
    if not (image_item.url or '').startswith('/api/static/generated_images/'):
        filename = os.path.basename(image_item.local_path)
        image_item.url = f"/api/static/generated_images/{filename}"
    update_image(image_item)
    return True


def repair_edit_thumbnail_if_needed(image_item) -> bool:
    """
    为编辑图片补齐缩略图

    功能描述：
        编辑图片缩略图缺失时，从 edit_folders 中的原图重新生成缩略图。

    实现逻辑：
        1. 检查缩略图是否缺失
        2. 检查 edit_folders 中是否有对应原图
        3. 有原图则调用 create_edit_thumbnail_from_local 生成缩略图
        4. 更新数据库中的 thumbnail 和 thumbnail_path
    """
    if not image_item:
        return False

    if not is_edit_thumbnail_missing(image_item):
        return False

    # 编辑图片的 url 是 /api/static/edit_images/{filename}，反推本地路径
    image_url = (image_item.url or '').strip()
    from services.edit_asset_service import EDIT_IMAGE_STATIC_PREFIX, EDIT_FOLDERS_DIR, EDIT_THUMBNAILS_DIR, create_edit_thumbnail_from_local

    local_path = (getattr(image_item, 'local_path', None) or '').strip()
    if not local_path or not os.path.exists(local_path):
        # 尝试从 URL 反推本地路径
        if image_url.startswith(EDIT_IMAGE_STATIC_PREFIX):
            filename = image_url.replace(EDIT_IMAGE_STATIC_PREFIX, '', 1)
            local_path = os.path.join(EDIT_FOLDERS_DIR, filename)
        else:
            return False

    if not os.path.exists(local_path):
        return False

    try:
        thumbnail_result = create_edit_thumbnail_from_local(local_path, '')
        if not thumbnail_result.get('thumbnail_url'):
            return False
        image_item.thumbnail = thumbnail_result['thumbnail_url']
        image_item.thumbnail_path = thumbnail_result.get('thumbnail_path')
        update_image(image_item)
        return True
    except (ValueError, RuntimeError, OSError) as err:
        print(f"[images] Warning: Failed to repair edit thumbnail for {image_item.id}: {err}")
        return False


def get_image_service() -> ImageService:
    image_api_config = get_db_single_config('image_api')

    return ImageService(
        api_base_url=image_api_config.get('baseUrl', current_app.config.get('IMAGE_API_BASE_URL')),
        api_key=image_api_config.get('apiKey', current_app.config.get('IMAGE_API_KEY'))
    )


# 获取 FalImageService 实例
# 功能描述：
#     从数据库/应用配置中读取 fal apiKey 和 baseUrl，创建 FalImageService 实例
#     baseUrl 来源：fal_api 配置 → 应用级 FAL_BASE_URL
#     不再硬编码任何兜底值，配置缺失时由 FalImageService 构造时抛错
def get_fal_image_service():
    fal_api_config = get_db_single_config('fal_api')
    api_key = fal_api_config.get('apiKey', '') or current_app.config.get('FAL_API_KEY', '')
    base_url = fal_api_config.get('baseUrl', '') or current_app.config.get('FAL_BASE_URL', '')
    if not api_key:
        raise ValueError('FAL API Key 未配置，请先在设置页面填写')
    return FalImageService(api_key=api_key, base_url=base_url)


def get_gptsapi_image_service():
    gptsapi_config = get_db_single_config('gptsapi_api')
    api_key = gptsapi_config.get('apiKey', '') or current_app.config.get('GPTSAPI_API_KEY', '')
    base_url = gptsapi_config.get('baseUrl', '') or current_app.config.get('GPTSAPI_BASE_URL', 'https://api.gptsapi.net')
    if not api_key:
        raise ValueError('GPTsAPI API Key 未配置，请先在设置页面填写')
    return GptsApiImageService(api_key=api_key, base_url=base_url)


# 获取 ApiyiImageService 实例
# 功能描述：
#     从数据库/应用配置中读取 apiyi apiKey 和 baseUrl，创建 ApiyiImageService 实例
# 实现逻辑：
#     1. 优先从数据库 apiyi_api 配置读取
#     2. 缺失时回退到 app.config（由 config.py update_app_config 同步）
#     3. baseUrl 默认值对齐文档主域名 https://api.apiyi.com
# 异常处理：
#     - apiKey 缺失时抛 ValueError，由上层路由返回 400
def get_apiyi_image_service():
    apiyi_config = get_db_single_config('apiyi_api')
    api_key = apiyi_config.get('apiKey', '') or current_app.config.get('APIYI_API_KEY', '')
    base_url = apiyi_config.get('baseUrl', '') or current_app.config.get('APIYI_BASE_URL', 'https://api.apiyi.com')
    if not api_key:
        raise ValueError('APIYI API Key 未配置，请先在设置页面填写')
    return ApiyiImageService(api_key=api_key, base_url=base_url)


def _normalize_apiyi_model(model: str) -> str:
    raw = (model or 'gpt-image-2-vip').strip()
    return raw.replace('apiyi/', '') or 'gpt-image-2-vip'


def _apiyi_display_model(model: str) -> str:
    return f"apiyi/{_normalize_apiyi_model(model)}"


def _apiyi_gpt_image2_params(source) -> dict:
    output_format = (source.get('output_format') or 'png').strip()
    params = {
        'quality': source.get('quality', 'auto'),
        'output_format': output_format,
        'background': 'auto',
        'moderation': source.get('moderation', 'auto'),
        'n': 1,
    }
    if output_format in {'jpeg', 'webp'}:
        params['output_compression'] = source.get('output_compression', 100)
    return params


# 局部更新 image 记录
# 功能描述：
#     仅更新指定字段，避免重新查整行；
#     用于 APIYI worker 异步场景下，不破坏并发安全。
# 实现逻辑：
#     1. 读取 image 记录（拿当前行作为基础）
#     2. 用 fields 字典覆盖指定字段
#     3. 调用 update_image 写回 DB
# 异常处理：
#     - image 不存在：静默跳过（worker 是后台任务，不应中断主流程）
def update_image_local(image_id, fields: dict):
    from models.image_model import get_image_by_id, update_image
    image = get_image_by_id(image_id)
    if not image:
        print(f"[images] update_image_local: image {image_id} not found, skip")
        return
    for k, v in (fields or {}).items():
        setattr(image, k, v)
    update_image(image)


# 获取 FileUploadService 实例
# 功能描述：
#     从数据库/应用配置中读取 file_upload 的 baseUrl 和 apiKey
#     如果配置不完整（任一缺失），返回 None，调用方应 fallback 到 base64
def get_file_upload_service():
    file_upload_config = get_db_single_config('file_upload')
    base_url = file_upload_config.get('baseUrl', '') or current_app.config.get('FILE_UPLOAD_BASE_URL', '')
    api_key = file_upload_config.get('apiKey', '') or current_app.config.get('FILE_UPLOAD_API_KEY', '')
    if not base_url or not api_key:
        return None
    return FileUploadService(base_url=base_url, api_key=api_key)


# 优先通过文件上传获取图片 URL，失败时 fallback 到 base64
# 功能描述：
#     1. 尝试创建 FileUploadService 并上传图片
#     2. 上传成功 → 返回 URL
#     3. 上传失败 / 无配置 → 返回 None，由调用方 fallback 到 base64
def _upload_image_priority(image_data: bytes, filename: str = "image.png"):
    upload_service = get_file_upload_service()
    if not upload_service:
        return None
    return upload_service.upload(image_data, filename)


# FAL 预设尺寸列表
_FAL_PRESET_SIZES = {"square_hd", "square", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9", "auto"}

# 将尺寸参数转为 fal API 所需的格式
# 功能描述：
#     1. "WxH" 字符串 → {width, height} 对象
#     2. FAL 预设值（如 square_hd）→ 原样返回
#     3. "custom" 模式 → 确保宽高是 16 的倍数
#     4. 其他字符串（如 "auto"）→ 原样返回
def _parse_size_to_image_size(size_str):
    if not size_str:
        return size_str

    # 如果传入的是 dict 格式（如 {"width": 1024, "height": 1024}），
    # 确保宽高是 16 的倍数后返回
    if isinstance(size_str, dict):
        w = size_str.get('width', 1024)
        h = size_str.get('height', 1024)
        try:
            w = int(w)
            h = int(h)
            if w > 0 and h > 0:
                w = (w // 16) * 16
                h = (h // 16) * 16
                return {'width': w, 'height': h}
        except (ValueError, TypeError):
            pass
        return {'width': 1024, 'height': 1024}

    # FAL 预设尺寸（如 square_hd, portrait_4_3 等），原样返回
    if size_str in _FAL_PRESET_SIZES:
        return size_str

    # "custom" 模式：由前端传递 custom_width 和 custom_height，此处不处理
    if size_str == "custom":
        return "custom"

    # "WxH" 格式 → {width, height}，确保为 16 的倍数
    if 'x' in size_str:
        try:
            parts = size_str.lower().split('x')
            if len(parts) == 2:
                w = int(parts[0])
                h = int(parts[1])
                if w > 0 and h > 0:
                    # fal 要求宽高必须是 16 的倍数
                    w = (w // 16) * 16
                    h = (h // 16) * 16
                    return {'width': w, 'height': h}
        except (ValueError, TypeError):
            pass

    return size_str


# 将数据库中可能存储为 JSON 字符串的 size 转为 "WxH" 显示格式
# 功能描述：
#     Fal 模式前端发送的 size 是 {width, height} 对象，存入 SQLite 时转为 JSON 字符串。
#     读取展示时需转回 "1280x720" 格式供前端使用。
# 实现逻辑：
#     1. 如果 size 是 JSON 字符串（以 { 开头），尝试解析取 width 和 height
#     2. 解析失败或非 JSON 格式则原样返回
def _normalize_display_size(size_raw):
    if not size_raw or not isinstance(size_raw, str):
        return size_raw or ''
    trimmed = size_raw.strip()
    if trimmed.startswith('{'):
        try:
            parsed = json.loads(trimmed)
            w = parsed.get('width')
            h = parsed.get('height')
            if w and h:
                return f'{w}x{h}'
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return size_raw


# 将本地静态URL路径映射为对应的本地文件系统路径
# 实现逻辑：
#   1. 计算项目根目录（backend/routes/ → backend/ → 项目根）
#   2. 遍历URL前缀→本地目录的映射表
#   3. 匹配到前缀后，提取相对路径并使用os.path.normpath防止路径穿越
#   4. 拼接为完整的本地文件路径
def _static_url_to_local_path(url):
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    mappings = {
        '/api/static/generated_images/': os.path.join(project_root, 'generated_images'),
        '/api/static/generated_thumbnails/': os.path.join(project_root, 'generated_thumbnails'),
        '/api/static/edit_images/': os.path.join(project_root, 'edit_folders'),
        '/api/static/edit_thumbnails/': os.path.join(project_root, 'edit_thumbnails'),
        '/api/static/material/': os.path.join(project_root, '素材'),
        '/api/static/material_thumbnails/': os.path.join(project_root, '素材缩略图'),
        '/api/static/recycle/': os.path.join(project_root, 'recycle_bin'),
    }

    for prefix, local_dir in mappings.items():
        if url.startswith(prefix):
            relative_path = url[len(prefix):]
            # 防止路径穿越攻击（如 ../../etc/passwd）
            safe_path = os.path.normpath(relative_path).lstrip(os.sep)
            return os.path.join(local_dir, safe_path)

    return ''


# 将单个图片引用转换为base64 Data URL
# 实现逻辑：
#   1. 已是base64 Data URL（以data:开头）→ 直接返回原值
#   2. 本地静态路径（以/api/static/开头）→ 读取本地文件进行base64编码
#   3. HTTP/HTTPS远程URL → 通过requests下载后进行base64编码
#   4. 其他情况 → 返回原值（兜底）
#   5. 任何转换失败 → 返回原值并打印警告日志（兜底，不阻断整个请求）
def _normalize_image_to_base64(image_item):
    if not isinstance(image_item, str):
        return image_item

    # 已是base64 Data URL，无需转换
    if image_item.startswith('data:'):
        return image_item

    try:
        # 本地静态路径 → 读取本地文件
        if image_item.startswith('/api/static/'):
            local_path = _static_url_to_local_path(image_item)
            if local_path and os.path.isfile(local_path):
                with open(local_path, 'rb') as f:
                    image_data = f.read()
                mime_type = mimetypes.guess_type(local_path)[0] or 'image/png'
                b64_data = base64.b64encode(image_data).decode('utf-8')
                print(f"[images] 参考图本地文件转base64成功: {image_item} ({len(image_data)} bytes)")
                return f'data:{mime_type};base64,{b64_data}'
            # 本地文件不存在，返回原值
            print(f"[images] 参考图本地文件不存在: {local_path}")
            return image_item

        # 远程URL → 下载后转换
        if image_item.startswith('http://') or image_item.startswith('https://'):
            response = requests_lib.get(image_item, timeout=30)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', 'image/png')
            b64_data = base64.b64encode(response.content).decode('utf-8')
            print(f"[images] 参考图远程URL转base64成功: {image_item[:100]}... ({len(response.content)} bytes)")
            return f'data:{content_type};base64,{b64_data}'

    except Exception as e:
        print(f"[images] 参考图转换base64失败, url={image_item[:100]}..., error={e}")
        return image_item

    # 其他情况：返回原值
    return image_item


# 批量处理参考图列表：优先文件上传，失败则转 base64
# 实现逻辑：
#   1. 已是 HTTP URL → 保持原样（下载后转 base64 作为 fallback）
#   2. 是 base64 data URL → 优先解码并上传到 /v1/files，失败则保持 base64
#   3. 本地静态路径 → 读取文件后优先上传，失败则转 base64
def _normalize_reference_images(image_list):
    if not isinstance(image_list, list):
        return image_list

    result = []
    for img in image_list:
        if not isinstance(img, str):
            result.append(img)
            continue

        # 已是普通 HTTP URL，保持原样
        if img.startswith('http://') or img.startswith('https://'):
            if img.startswith('data:'):
                # data URL 的情况已经在上面排除，这里不会走到
                pass
            result.append(img)
            continue

        # 尝试文件上传优先
        uploaded_url = None
        if img.startswith('data:'):
            try:
                header, b64_part = img.split(',', 1)
                img_bytes = base64.b64decode(b64_part)
                uploaded_url = _upload_image_priority(img_bytes, "ref.png")
            except Exception as e:
                print(f"[images] Ref image upload failed: {e}")

        if not uploaded_url and img.startswith('/api/static/'):
            local_path = _static_url_to_local_path(img)
            if local_path and os.path.isfile(local_path):
                try:
                    with open(local_path, 'rb') as f:
                        img_bytes = f.read()
                    uploaded_url = _upload_image_priority(img_bytes, os.path.basename(local_path))
                except Exception as e:
                    print(f"[images] Ref local file upload failed: {e}")

        if uploaded_url:
            print(f"[images] Ref image uploaded → {uploaded_url[:60]}...")
            result.append(uploaded_url)
        else:
            # fallback 到 base64
            result.append(_normalize_image_to_base64(img))

    return result


def _size_to_gptsapi_aspect_ratio(size_value, fallback='auto'):
    if isinstance(size_value, dict):
        width = size_value.get('width')
        height = size_value.get('height')
    elif isinstance(size_value, str) and 'x' in size_value.lower():
        parts = size_value.lower().split('x')
        width = parts[0] if len(parts) == 2 else None
        height = parts[1] if len(parts) == 2 else None
    else:
        return fallback

    try:
        width = int(width)
        height = int(height)
    except (TypeError, ValueError):
        return fallback

    if width <= 0 or height <= 0:
        return fallback

    ratio = width / height
    known_ratios = {
        '1:1': 1,
        '16:9': 16 / 9,
        '9:16': 9 / 16,
        '4:3': 4 / 3,
        '3:4': 3 / 4,
    }
    return min(known_ratios, key=lambda item: abs(known_ratios[item] - ratio))


def _extract_image_urls_from_result(result):
    urls = []

    def walk(value):
        if isinstance(value, dict):
            for key in ('url', 'image_url', 'output_url'):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.startswith(('http://', 'https://')):
                    urls.append(candidate)
            for key in ('urls', 'image_urls', 'output_urls', 'outputs'):
                candidate_list = value.get(key)
                if isinstance(candidate_list, list):
                    for item in candidate_list:
                        if isinstance(item, str) and item.startswith(('http://', 'https://')):
                            urls.append(item)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(result)
    deduped = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def _save_gptsapi_generation_result(result, prompt, model, size, quality, poster_copy='', creator=''):
    image_urls = _extract_image_urls_from_result(result)
    if not image_urls:
        return None, [], 'GPTsAPI 未返回图片 URL'

    all_images = []
    first_saved = None
    for idx, image_url in enumerate(image_urls):
        try:
            asset_result = prepare_image_assets(image_url, creator=creator)
        except (ValueError, RuntimeError) as err:
            print(f"[images] Warning: Failed to prepare GPTsAPI generated image [{idx}]: {err}")
            asset_result = {'url': image_url, 'thumbnail': '', 'local_path': None, 'thumbnail_path': None}

        saved_image = add_image(
            url=asset_result.get('url', image_url),
            thumbnail=asset_result.get('thumbnail', ''),
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            local_path=asset_result.get('local_path'),
            thumbnail_path=asset_result.get('thumbnail_path'),
            image_type='generation',
            poster_copy=poster_copy,
            creator=creator
        )
        if first_saved is None:
            first_saved = saved_image
        all_images.append(serialize_image(saved_image))

    return first_saved, all_images, ''


def _enqueue_gptsapi_image_download(saved_image, image_url, image_type='generation', task_id=None):
    try:
        from services.background_download_service import enqueue_image_download
        enqueue_image_download(
            image_id=saved_image.id,
            image_url=image_url,
            image_type=image_type,
            folder_path=getattr(saved_image, 'folder_path', None),
            task_id=task_id
        )
    except Exception as err:
        print(f"[images] Warning: Failed to enqueue GPTsAPI image download: {err}")





def _save_gptsapi_edit_result(result, prompt, model, size, quality, parent_id, creator=''):
    image_urls = _extract_image_urls_from_result(result)
    if not image_urls:
        return None, 'GPTsAPI 未返回图片 URL'

    root_id = None
    depth = 0
    if parent_id:
        parent_relation = get_edit_relation_by_image_id(parent_id)
        if parent_relation:
            root_id = parent_relation.get('root_id')
            depth = parent_relation.get('depth', 0) + 1
        else:
            root_id = parent_id
            depth = 1

    image_url = image_urls[0]
    try:
        asset_result = save_edit_result_directly(image_url, prompt, size, creator=effective_creator)
    except (ValueError, RuntimeError) as err:
        print(f"[images] Warning: Failed to save GPTsAPI edit assets: {err}")
        asset_result = {
            'display_url': image_url,
            'url': image_url,
            'thumbnail': '',
            'local_path': None,
            'thumbnail_path': None
        }

    # 编辑链路优先使用显式传入的 creator，否则从父图继承
    effective_creator = creator or get_inherited_creator(parent_id)

    saved_image = add_image(
        url=asset_result.get('display_url') or asset_result.get('url', image_url),
        thumbnail=asset_result.get('thumbnail', ''),
        prompt=build_edit_saved_prompt(parent_id, prompt),
        model=model,
        size=size,
        quality=quality,
        local_path=asset_result.get('local_path'),
        thumbnail_path=asset_result.get('thumbnail_path'),
        parent_id=parent_id,
        folder_path='',
        image_type='edit',
        poster_copy=get_inherited_poster_copy(parent_id),
        creator=effective_creator
    )

    if parent_id:
        if not root_id:
            root_id = parent_id
        add_edit_relation(
            image_id=saved_image.id,
            parent_id=parent_id,
            root_id=root_id,
            depth=depth
        )

    return saved_image, ''


def _handle_gptsapi_generation(data, prompt, model, size, quality):
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        service = get_gptsapi_image_service()
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

    aspect_ratio = data.get('aspectRatio') or _size_to_gptsapi_aspect_ratio(size, '1:1')
    if aspect_ratio not in ('auto', '1:1', '9:16', '16:9', '4:3', '3:4'):
        aspect_ratio = _size_to_gptsapi_aspect_ratio(size, '1:1')
    resolution = data.get('resolution', '2K')
    local_async = bool(data.get('async', False))
    poster_copy = (data.get('poster_copy') or '').strip()
    # 制作人：仅作为本地元数据，不发送到 API
    creator = _creator_from_request(data.get('creator'))

    image = data.get('image')
    input_urls = []
    if isinstance(image, list):
        input_urls = _normalize_reference_images(image)
        input_urls = [item for item in input_urls if isinstance(item, str) and item.startswith(('http://', 'https://'))]
        if image and not input_urls:
            return jsonify({'error': 'GPTsAPI 参考图必须先上传为可访问 URL，请检查文件上传设置'}), 502

    if local_async:
        import uuid

        # 先调用 GPTsAPI 创建任务，获取 poll_url
        if input_urls:
            create_result = service.create_image_edit(
                prompt=prompt,
                input_urls=input_urls[:16],
                aspect_ratio=aspect_ratio,
                resolution=resolution
            )
        else:
            create_result = service.create_text_to_image(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution
            )

        if 'error' in create_result:
            return jsonify(create_result), 500

        poll_url = create_result.get('poll_url', '')
        if not poll_url:
            return jsonify({'error': 'GPTsAPI 未返回轮询地址', 'raw_response': create_result.get('raw_response', {})}), 502

        task_id = str(uuid.uuid4())
        saved_image = add_image(
            url='',
            thumbnail='',
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            task_id=task_id,
            image_type='generation',
            api_source='gptsapi',
            poster_copy=poster_copy,
            creator=creator
        )

        add_task(
            task_id=task_id,
            image_id=saved_image.id,
            platform='gptsapi',
            status='IN_PROGRESS',
            api_source='gptsapi',
            data={
                'poll_url': poll_url,
                'model': model,
                'prompt': prompt,
                'size': size,
                'aspect_ratio': aspect_ratio,
                'resolution': resolution,
                'quality': quality,
                'raw_create_result': create_result.get('raw_response', {}),
                'creator': creator
            }
        )

        saved_image = get_image_by_id(saved_image.id) or saved_image
        return jsonify({
            'status': 'pending',
            'task_id': task_id,
            'image': serialize_image(saved_image)
        }), 202

    if input_urls:
        result = service.image_edit(
            prompt=prompt,
            input_urls=input_urls[:16],
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )
    else:
        result = service.text_to_image(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )

    if 'error' in result:
        return jsonify(result), 500

    first_saved, all_images, error = _save_gptsapi_generation_result(result, prompt, model, size, quality, poster_copy, creator)
    if error:
        return jsonify({'error': error, 'raw_result': result}), 500

    return jsonify({
        'status': 'success',
        'image': serialize_image(first_saved),
        'images': all_images
    }), 200


# APIYI 异步生图处理
# 功能描述：
#     按文档调用 {base_url}/v1/images/generations 同步接口（gpt-image-2-vip），
#     立即生成 task_id 入库，把同步调用丢进 ThreadPoolExecutor，
#     立即返回 202 + task_id 给前端。前端走统一任务卡轮询。
# 实现逻辑：
#     1. 校验 apiKey；模型固定为 gpt-image-2-vip（强制覆盖前端传入）
#     2. 创建占位 image 记录、task 记录（status=IN_PROGRESS, api_source='apiyi'）
#     3. 提交 _apiyi_executor.submit(worker) 异步执行
#     4. 后台 worker 完成时：解析 b64_json/url → 下载/转存 → 更新 image 与 task
#     5. 不在前端做同步等待，与用户「异步执行=并行发送请求」要求一致
# 异常处理：
#     - 无 apiKey：返回 400，不入 task
#     - 后台执行异常：worker 内部捕获，标记 task FAILURE + 写入 fail_reason
def _handle_apiyi_generation(data, prompt, model, size, quality):
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        service = get_apiyi_image_service()
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

    api_model = _normalize_apiyi_model(model)
    actual_model = _apiyi_display_model(api_model)
    if api_model == 'gpt-image-2':
        actual_size = size or '1024x1024'
        request_params = _apiyi_gpt_image2_params(data)
    else:
        # size 透传：仅当含 'x' 时认为是 30 档之一，否则回退 'auto'（与文档默认值对齐）
        actual_size = size if (not size or 'x' in str(size).lower()) else 'auto'
        request_params = {}
    # 文档默认 response_format=b64_json，避免 url 24h 过期
    response_format = data.get('response_format', 'b64_json')
    poster_copy = (data.get('poster_copy') or '').strip()
    # 制作人：仅作为本地元数据，不发送到 API
    creator = _creator_from_request(data.get('creator'))

    # 提取参考图（已由 generate_image 路由的 _normalize_reference_images 标准化）
    # APIYI 的 /v1/images/generations 文生图端点不支持传入图片，
    # 有参考图时必须改用 /v1/images/edits 编辑端点（multipart 方式上传本地文件）
    ref_images = data.get('image')
    has_ref_images = bool(ref_images and isinstance(ref_images, list) and len(ref_images) > 0)

    # 有参考图时，下载 URL/base64 到临时文件供 multipart 上传
    temp_dir = None
    image_paths = []
    if has_ref_images:
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        try:
            for idx, img_url in enumerate(ref_images):
                if not isinstance(img_url, str):
                    continue
                try:
                    if img_url.startswith('data:'):
                        # base64 Data URL → 直接解码
                        header, b64_part = img_url.split(',', 1)
                        img_bytes = base64.b64decode(b64_part)
                    else:
                        # HTTP/HTTPS URL → 下载
                        resp = requests_lib.get(img_url, timeout=30)
                        resp.raise_for_status()
                        img_bytes = resp.content
                except Exception as e:
                    print(f"[apiyi_gen] 下载参考图 {idx} ({str(img_url)[:80]}) 失败: {e}")
                    continue
                file_path = os.path.join(temp_dir, f'{uuid.uuid4()}_ref_{idx}.png')
                with open(file_path, 'wb') as f:
                    f.write(img_bytes)
                # 长边 3840px 等比缩小（与 _handle_apiyi_edit 对齐，文档建议 ≤1.5MB）
                from services.image_processor import ImageDataProcessor
                downscaled, down_err = ImageDataProcessor.downscale_image(file_path, 3840)
                if down_err:
                    print(f"[apiyi_gen] downscale ref image {idx} warning: {down_err}")
                elif downscaled != file_path:
                    image_paths.append(downscaled)
                else:
                    image_paths.append(file_path)
        except Exception as e:
            for p in image_paths:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            return jsonify({'error': f'参考图下载失败: {e}'}), 500

    task_id = str(uuid.uuid4())
    saved_image = add_image(
        url='',
        thumbnail='',
        prompt=prompt,
        model=actual_model,
        size=actual_size,
        quality=request_params.get('quality', '') if api_model == 'gpt-image-2' else '',
        task_id=task_id,
        image_type='generation',
        api_source='apiyi',
        poster_copy=poster_copy,
        creator=creator
    )

    add_task(
        task_id=task_id,
        image_id=saved_image.id,
        platform='apiyi',
        status='IN_PROGRESS',
        api_source='apiyi',
        data={
            'api_source': 'apiyi',
            'model': api_model,
            'prompt': prompt,
            'size': actual_size,
            'response_format': response_format,
            'request_params': request_params,
            'has_ref_images': has_ref_images,
            'ref_image_count': len(image_paths) if has_ref_images else 0,
            'creator': creator
        }
    )

    # 闭包捕获：worker 在独立线程中运行，需重新获取 application context
    app_obj = current_app._get_current_object()

    # 把原 _worker 闭包逻辑抽到 services.apiyi_async_workers，复用于 retry
    from services.apiyi_async_workers import run_apiyi_generation_worker
    _apiyi_executor.submit(
        run_apiyi_generation_worker,
        app_obj,
        service,
        task_id,
        saved_image,
        image_paths,
        prompt,
        actual_size,
        response_format,
        has_ref_images,
        api_model,
        request_params,
    )

    saved_image = get_image_by_id(saved_image.id) or saved_image
    print(f"[images] APIYI generation async submitted: task_id={task_id}, image_id={saved_image.id}, has_ref_images={has_ref_images}, ref_count={len(image_paths)}")
    return jsonify({
        'status': 'pending',
        'task_id': task_id,
        'image': serialize_image(saved_image)
    }), 202


@images_bp.route('/api/images/generations', methods=['POST'])
def generate_image():
    data = request.get_json()

    prompt = data.get('prompt')
    poster_copy = (data.get('poster_copy') or '').strip()
    # 制作人：仅作为本地元数据，不发送到 API
    creator = _creator_from_request(data.get('creator'))
    model = data.get('model', 'gpt-image-2')
    size = data.get('size', '1024x1024')
    quality = data.get('quality', 'auto')
    async_mode = data.get('async', False)
    n = data.get('n', 1)
    seed = data.get('seed', 0)
    moderation = data.get('moderation', 'auto')
    background = data.get('background', 'auto')
    output_format = data.get('output_format', 'png')
    output_compression = data.get('output_compression', 100)
    response_format = data.get('response_format', 'url')
    image = data.get('image')
    # 将参考图中的HTTP URL统一转换为base64 Data URL，确保第三方API能正确识别
    if image and isinstance(image, list):
        image = _normalize_reference_images(image)
        data['image'] = image  # 将标准化后的参考图写回 data，确保下游 handler 拿到标准化值

    api_provider = data.get('api_provider', 'openai')
    try:
        print(
            "[images] SEND generation request "
            f"api={api_provider} model={model} size={size} quality={quality} "
            f"async={async_mode} prompt_len={len(prompt or '')} "
            f"reference_count={len(image) if isinstance(image, list) else 0}"
        )
    except Exception:
        pass

    # APIYI 异步生图分支（gpt-image-2-vip，按文档走后台线程执行）
    if api_provider == 'apiyi':
        return _handle_apiyi_generation(data, prompt, model, size, quality)

    # Fal API 生图分支
    if api_provider == 'fal':
        return _handle_fal_generation(data, prompt, model, size, quality)

    if api_provider == 'gptsapi':
        return _handle_gptsapi_generation(data, prompt, model, size, quality)

    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    service = get_image_service()
    result = service.generate_image(
        prompt=prompt,
        model=model,
        size=size,
        quality=quality,
        response_format=response_format,
        async_mode=async_mode,
        n=n,
        seed=seed,
        moderation=moderation,
        background=background,
        output_format=output_format,
        output_compression=output_compression,
        image=image
    )

    if 'error' in result:
        return jsonify(result), 500

    if async_mode:
        task_id = extract_async_task_id(result)
        if not task_id:
            return jsonify({
                'error': '异步图片生成接口未返回 task_id，无法继续跟踪任务'
            }), 502

        # 制作人：随生图请求上传到后端，写入 images.creator，保证刷新和 GEO 复制时不会丢
        saved_image = add_image(
            url='',
            thumbnail='',
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            task_id=task_id,
            image_type='generation',
            poster_copy=poster_copy,
            creator=creator
        )

        add_task(
            task_id=task_id,
            image_id=saved_image.id,
            platform=result.get('platform', ''),
            status='IN_PROGRESS',
            data={
                'raw_create_result': result,
                'response_format': response_format,
                'n': n,
                'seed': seed,
                'output_format': output_format,
                'output_compression': output_compression,
                'creator': creator
            }
        )

        saved_image = get_image_by_id(saved_image.id) or saved_image

        return jsonify({
            'status': 'pending',
            'task_id': task_id,
            'image': serialize_image(saved_image)
        }), 202
    else:
        # 同步模式：遍历 data 数组中的所有图片，支持 n > 1 多图返回
        data_items = result.get('data', [])
        if not isinstance(data_items, list):
            data_items = [data_items] if data_items else []

        all_images = []
        first_saved = None

        for idx, image_data in enumerate(data_items):
            if not isinstance(image_data, dict):
                continue

            image_url = image_data.get('url', '')
            revised_prompt = image_data.get('revised_prompt', prompt)
            asset_result = {
                'url': image_url,
                'thumbnail': '',
                'local_path': None
            }

            if image_url:
                try:
                    asset_result = prepare_image_assets(image_url, creator=creator)
                except (ValueError, RuntimeError) as err:
                    print(f"[images] Warning: Failed to prepare assets for generated image [{idx}]: {err}")

            saved_image = add_image(
                url=asset_result.get('url', image_url),
                thumbnail=asset_result.get('thumbnail', ''),
                prompt=revised_prompt,
                model=model,
                size=size,
                quality=quality,
                local_path=asset_result.get('local_path'),
                thumbnail_path=asset_result.get('thumbnail_path'),
                image_type='generation',
                poster_copy=poster_copy,
                creator=creator
            )

            if idx == 0:
                first_saved = saved_image

            all_images.append(serialize_image(saved_image))

        if not first_saved:
            return jsonify({'error': 'No valid images generated'}), 500

        return jsonify({
            'status': 'success',
            'image': serialize_image(first_saved),
            'images': all_images
        }), 200


# Fal API 生图处理
# 功能描述：
#     处理 fal 协议的图像生成请求，支持同步和异步两种模式
#     始终使用 queue 模式提交（sync_mode=False），与 fal 官方文档保持一致
#     同步模式：提交后阻塞轮询 response_url 等待完成
#     异步模式：提交后返回 request_id，由 TaskProcessor 后台轮询
# 实现逻辑：
#     1. 解析 fal 专用参数（image_size, num_images, output_format, seed 等）
#     2. 参考图优先上传到 /v1/files，失败 fallback 到 base64
#     3. 调用 FalImageService.submit_generation(sync_mode=False) 进入队列
#     4. 异步模式：创建任务和图片记录后返回 task_id
#     5. 同步模式：阻塞轮询 response_url 等待 fal 完成，保存图片后返回
#     6. skip_error=True 时，失败不抛错，返回空占位结果
def _handle_fal_generation(data, prompt, model, size, quality):
    try:
        fal_service = get_fal_image_service()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # 提取 fal 专用参数
    is_async = data.get('async', False)
    image_size = _parse_size_to_image_size(data.get('size', '1024x1024'))
    num_images = data.get('num_images', 1)
    output_format = data.get('outputFormat', 'png')
    seed = data.get('seed', 0)
    skip_error = data.get('skip_error', False)
    poster_copy = (data.get('poster_copy') or '').strip()
    # 制作人：仅作为本地元数据，不发送到 fal API
    creator = _creator_from_request(data.get('creator'))

    # 参考图：优先使用前端已上传的 HTTP URL，base64 则尝试上传到 /v1/files
    image_urls = None
    image = data.get('image')
    if image and isinstance(image, list):
        image_urls = []
        for idx, img_str in enumerate(image):
            if not isinstance(img_str, str):
                image_urls.append(img_str)
                continue

            # 前端已上传为 HTTP URL，直接使用
            if img_str.startswith('http://') or img_str.startswith('https://'):
                image_urls.append(img_str)
                print(f"[images] Fal gen ref image {idx+1}: using uploaded URL → {img_str[:60]}...")
                continue

            # base64 data URL：上传到 /v1/files，失败返回错误（不再回退 base64）
            if img_str.startswith('data:'):
                try:
                    header, b64_part = img_str.split(',', 1)
                    img_bytes = base64.b64decode(b64_part)
                    uploaded_url = _upload_image_priority(img_bytes, f"ref_{idx}.png")
                    if uploaded_url:
                        image_urls.append(uploaded_url)
                        print(f"[images] Fal gen ref image {idx+1}: uploaded → {uploaded_url[:60]}...")
                    else:
                        return jsonify({'error': f'参考图 {idx+1} 上传失败，无法继续 FAL 生图'}), 502
                except Exception as e:
                    print(f"[images] Fal gen ref image upload failed: {e}")
                    return jsonify({'error': f'参考图 {idx+1} 处理失败: {str(e)}'}), 500
            else:
                image_urls.append(img_str)

    # 自动切换模型：有参考图时使用 /edit 端点，否则使用基础模型
    # 前端固定传 openai/gpt-image-2，后端根据参考图自动决定是否加 /edit
    if image_urls:
        model = model + '/edit'
        print(f"[images] Fal gen auto-switched to edit model: {model}")

    # 调用 fal 服务提交生图请求
    # 始终使用 queue 模式（sync_mode=False），与 fal 官方文档保持一致
    # 无论前端选择同步还是异步，都先提交到队列获取 request_id 和 response_url，
    # 然后通过轮询 response_url 获取结果（同步模式在本次请求内轮询，异步模式由 TaskProcessor 后台轮询）
    result = fal_service.submit_generation(
        prompt=prompt,
        model=model,
        image_size=image_size,
        quality=quality,
        num_images=num_images,
        output_format=output_format,
        image_urls=image_urls,
        seed=seed,
        sync_mode=False
    )

    if 'error' in result:
        if skip_error:
            return jsonify({'status': 'skipped', 'error': result['error'], 'image': None}), 200
        return jsonify(result), 500

    # 将 image_size 转为字符串用于数据库存储（SQLite 不支持 dict）
    size_for_db = json.dumps(image_size, ensure_ascii=False) if isinstance(image_size, dict) else image_size

    # 检查是否同步模式直接返回了图片（result 中直接包含 images）
    if 'images' in result and result['images']:
        # 同步模式直接返回：遍历所有图片，逐一下载并保存
        result_images = result['images']
        all_images = []
        first_saved = None

        for idx, image_data in enumerate(result_images):
            if not isinstance(image_data, dict):
                continue

            image_url = image_data.get('url', '') or ''
            if not image_url:
                print(f"[images] Fal sync direct result: image[{idx}] has no URL, skipping")
                continue

            asset_result = prepare_image_assets(image_url, creator=creator)
            saved_image = add_image(
                url=asset_result.get('url', image_url),
                thumbnail=asset_result.get('thumbnail', ''),
                prompt=prompt,
                model=model,
                size=size_for_db,
                quality=quality,
                local_path=asset_result.get('local_path'),
                thumbnail_path=asset_result.get('thumbnail_path'),
                image_type='generation',
                poster_copy=poster_copy,
                creator=creator
            )

            if idx == 0:
                first_saved = saved_image

            all_images.append(serialize_image(saved_image))

        if not first_saved:
            if skip_error:
                return jsonify({'status': 'skipped', 'error': 'Fal 同步返回图片 URL 为空', 'image': None}), 200
            return jsonify({'error': 'Fal 同步返回图片 URL 为空'}), 500

        print(f"[images] Fal generation direct sync result: {len(all_images)} image(s), first=image_id={first_saved.id}")
        return jsonify({
            'status': 'success',
            'image': serialize_image(first_saved),
            'images': all_images
        }), 200

    # 从响应中提取 request_id
    request_id = result.get('request_id')
    response_url = result.get('response_url', '')
    if not request_id:
        if skip_error:
            return jsonify({'status': 'skipped', 'error': 'Fal API 未返回 request_id', 'image': None}), 200
        return jsonify({
            'error': 'Fal API 未返回 request_id，无法继续跟踪任务'
        }), 502

    # 异步模式：返回 task_id，由 TaskProcessor 后台轮询
    if is_async:
        # 创建图片记录
        # 制作人：随生图请求上传到后端，写入 images.creator，保证刷新和 GEO 复制时不会丢
        saved_image = add_image(
            url='',
            thumbnail='',
            prompt=prompt,
            model=model,
            size=size_for_db,
            quality=quality,
            task_id=request_id,
            image_type='generation',
            poster_copy=poster_copy,
            creator=creator
        )

        # 创建任务记录，标记 api_source='fal'，存储 model 和 response_url 供后续轮询使用
        # creator 同步写入 data 字典，TaskProcessor 在补建额外图时可直接取用
        add_task(
            task_id=request_id,
            image_id=saved_image.id,
            platform='fal',
            status='IN_PROGRESS',
            data={
                'api_source': 'fal',
                'model': model,
                'response_url': response_url,
                'raw_create_result': result,
                'creator': creator
            }
        )

        saved_image = get_image_by_id(saved_image.id) or saved_image

        print(f"[images] Fal generation submitted (async): request_id={request_id}, image_id={saved_image.id}")
        return jsonify({
            'status': 'pending',
            'task_id': request_id,
            'image': serialize_image(saved_image)
        }), 202

    # 同步模式：阻塞轮询等待 fal 完成
    import time
    max_poll = 300
    poll_interval = 2
    result_data = None
    consecutive_errors = 0

    print(f"[images] Fal generation sync mode: request_id={request_id}, polling for result...")

    for attempt in range(max_poll):
        time.sleep(poll_interval)
        try:
            status_resp = fal_service.query_task_status(model, request_id, response_url)

            # 查询返回 error 时，累加连续错误计数
            if 'error' in status_resp:
                consecutive_errors += 1
                error_msg = str(status_resp['error'])
                print(f"[images] Fal sync poll error (attempt {attempt+1}, consecutive={consecutive_errors}): {error_msg}")
                if consecutive_errors >= 5:
                    print(f"[images] Fal sync task aborted after {consecutive_errors} consecutive errors")
                    if skip_error:
                        return jsonify({'status': 'skipped', 'error': f'Fal 连续 {consecutive_errors} 次查询失败: {error_msg}', 'image': None}), 200
                    return jsonify({'error': f'Fal 连续 {consecutive_errors} 次查询失败: {error_msg}'}), 500
                continue

            # 查询成功，重置连续错误计数
            consecutive_errors = 0
            status = status_resp.get('status', '')
            if status == 'COMPLETED':
                result_data = fal_service.get_task_result(model, request_id, response_url)
                break
            elif status in ('FAILED', 'FAILURE', 'CANCELLED'):
                print(f"[images] Fal sync task failed: {status_resp}")
                if skip_error:
                    return jsonify({'status': 'skipped', 'error': f'Fal 任务失败: {status_resp.get("error", "unknown")}', 'image': None}), 200
                return jsonify({'error': f'Fal 任务失败: {status_resp.get("error", "unknown")}'}), 500
        except Exception as e:
            consecutive_errors += 1
            print(f"[images] Fal sync poll exception (attempt {attempt+1}, consecutive={consecutive_errors}): {e}")
            if consecutive_errors >= 5:
                print(f"[images] Fal sync task aborted after {consecutive_errors} consecutive exceptions")
                if skip_error:
                    return jsonify({'status': 'skipped', 'error': f'Fal 连续 {consecutive_errors} 次异常: {str(e)}', 'image': None}), 200
                return jsonify({'error': f'Fal 连续 {consecutive_errors} 次异常: {str(e)}'}), 500
            continue

    if not result_data:
        print(f"[images] Fal sync task timeout: request_id={request_id}")
        if skip_error:
            return jsonify({'status': 'skipped', 'error': 'Fal 同步生图超时', 'image': None}), 200
        return jsonify({'error': 'Fal 同步生图超时，请稍后重试或切换为异步模式'}), 504

    # 从 result_data 中提取图片 URL，遍历所有图片支持多图返回
    result_images = result_data.get('images', [])
    if not result_images:
        print(f"[images] Fal sync result missing images: {result_data}")
        if skip_error:
            return jsonify({'status': 'skipped', 'error': 'Fal 未返回图片数据', 'image': None}), 200
        return jsonify({'error': 'Fal 未返回图片数据'}), 500

    all_images = []
    first_saved = None

    for idx, image_data in enumerate(result_images):
        if not isinstance(image_data, dict):
            continue

        image_url = image_data.get('url', '') or ''
        if not image_url:
            print(f"[images] Fal sync poll result: image[{idx}] has no URL, skipping")
            continue

        # 与 OpenAI sync 一样：下载到本地，保存记录
        # 制作人：随生图请求上传到后端，写入 images.creator，保证刷新和 GEO 复制时不会丢
        asset_result = prepare_image_assets(image_url, creator=creator)
        saved_image = add_image(
            url=asset_result.get('url', image_url),
            thumbnail=asset_result.get('thumbnail', ''),
            prompt=prompt,
            model=model,
            size=size_for_db,
            quality=quality,
            local_path=asset_result.get('local_path'),
            thumbnail_path=asset_result.get('thumbnail_path'),
            image_type='generation',
            poster_copy=poster_copy,
            creator=creator
        )

        if idx == 0:
            first_saved = saved_image

        all_images.append(serialize_image(saved_image))

    if not first_saved:
        if skip_error:
            return jsonify({'status': 'skipped', 'error': 'Fal 返回的图片 URL 为空', 'image': None}), 200
        return jsonify({'error': 'Fal 返回的图片 URL 为空'}), 500

    print(f"[images] Fal generation sync completed: {len(all_images)} image(s), first=image_id={first_saved.id}")
    return jsonify({
        'status': 'success',
        'image': serialize_image(first_saved),
        'images': all_images
    }), 200


def _handle_gptsapi_edit(request, prompt, image_file, reference_files, model, size, quality, parent_id, async_mode=False, creator=''):
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    if not image_file:
        return jsonify({'error': 'GPTsAPI 编辑需要至少一张输入图片'}), 400

    try:
        service = get_gptsapi_image_service()
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

    def file_to_url(file_obj, prefix):
        raw = file_obj.read()
        uploaded_url = _upload_image_priority(raw, f"{prefix}.png")
        if not uploaded_url:
            raise ValueError(f'{prefix} 图片上传失败，无法继续 GPTsAPI 编辑')
        return uploaded_url

    try:
        input_urls = [file_to_url(image_file, 'main')]
        for idx, ref_file in enumerate(reference_files[:15]):
            input_urls.append(file_to_url(ref_file, f'ref_{idx}'))
    except ValueError as err:
        return jsonify({'error': str(err)}), 502

    aspect_ratio = request.form.get('aspect_ratio') or _size_to_gptsapi_aspect_ratio(size, 'auto')
    if aspect_ratio not in ('auto', '1:1', '9:16', '16:9', '4:3', '3:4'):
        aspect_ratio = _size_to_gptsapi_aspect_ratio(size, 'auto')
    resolution = request.form.get('resolution', '1K')

    # 异步模式：创建任务后立即返回，由 TaskProcessor 后台轮询
    if async_mode:
        import uuid
        create_result = service.create_image_edit(
            prompt=prompt,
            input_urls=input_urls[:16],
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )
        if 'error' in create_result:
            return jsonify(create_result), 500

        poll_url = create_result.get('poll_url', '')
        if not poll_url:
            return jsonify({'error': 'GPTsAPI 未返回轮询地址', 'raw_response': create_result.get('raw_response', {})}), 502

        # 处理编辑关系
        root_id = None
        depth = 0
        if parent_id:
            parent_relation = get_edit_relation_by_image_id(parent_id)
            if parent_relation:
                root_id = parent_relation.get('root_id')
                depth = parent_relation.get('depth', 0) + 1
            else:
                root_id = parent_id
                depth = 1

        task_id = str(uuid.uuid4())

        # 创建占位图片记录（异步任务结果稍后由 TaskProcessor 更新）
        saved_image = add_image(
            url='',
            thumbnail='',
            prompt=build_edit_saved_prompt(parent_id, prompt),
            model=model,
            size=size,
            quality=quality,
            task_id=task_id,
            parent_id=parent_id,
            folder_path='',
            image_type='edit',
            poster_copy=get_inherited_poster_copy(parent_id),
            # 制作人：异步任务占位记录写入 images.creator，TaskProcessor 落盘结果时沿用同一 image_id
            creator=creator
        )

        if parent_id:
            if not root_id:
                root_id = parent_id
            add_edit_relation(
                image_id=saved_image.id,
                parent_id=parent_id,
                root_id=root_id,
                depth=depth
            )

        # 创建任务记录，存储 poll_url 供 TaskProcessor 后台轮询
        add_task(
            task_id=task_id,
            image_id=saved_image.id,
            platform='gptsapi',
            status='IN_PROGRESS',
            api_source='gptsapi',
            data={
                'api_source': 'gptsapi',
                'model': model,
                'poll_url': poll_url,
                'prompt': prompt,
                'size': size,
                'quality': quality,
                'parent_id': parent_id,
                'raw_create_result': create_result.get('raw_response', {}),
                # 制作人：随任务数据透传，TaskProcessor 落盘结果时优先读取此字段
                'creator': creator
            }
        )

        saved_image = get_image_by_id(saved_image.id) or saved_image
        print(f"[images] GPTsAPI edit async submitted: task_id={task_id}, poll_url={poll_url[:60]}...")
        return jsonify({
            'status': 'pending',
            'task_id': task_id,
            'image': serialize_image(saved_image)
        }), 202

    # 同步模式：保持原有逻辑，阻塞等待直到轮询完成
    result = service.image_edit(
        prompt=prompt,
        input_urls=input_urls[:16],
        aspect_ratio=aspect_ratio,
        resolution=resolution
    )

    if 'error' in result:
        return jsonify(result), 500

    saved_image, error = _save_gptsapi_edit_result(result, prompt, model, size, quality, parent_id, creator=creator)
    if error:
        return jsonify({'error': error, 'raw_result': result}), 500

    return jsonify({
        'status': 'success',
        'image': serialize_image(saved_image)
    }), 200


# APIYI 异步图片编辑处理
# 功能描述：
#     按文档调用 {base_url}/v1/images/edits 同步接口（gpt-image-2-vip），
#     立即生成 task_id 入库，把 multipart 上传 + 同步调用丢进 ThreadPoolExecutor，
#     立即返回 202 + task_id 给前端。前端走统一任务卡轮询。
# 实现逻辑：
#     1. 校验 apiKey / prompt / 至少一张输入图
#     2. 将上传文件保存到 temp 目录（统一走 downscale_image 3840px 压缩）
#     3. 创建占位 image 记录（image_type='edit'）、task 记录（api_source='apiyi'）
#     4. 建立 edit_relation（如果 parent_id 存在）
#     5. 提交 _apiyi_executor.submit(worker) 异步执行
#     6. worker 完成后清理 temp 文件，更新 image 与 task
#     7. 默认 size='auto'（文档：编辑场景推荐 auto，跟随 prompt 中点名要修改的图比例）
# 异常处理：
#     - prompt 缺失 / 输入图为空：返回 400，不入 task
#     - apiKey 缺失：返回 400，不入 task
#     - 后台执行异常：worker 内部捕获，标记 task FAILURE + 写入 fail_reason
def _handle_apiyi_edit(request, prompt, image_file, mask_file, reference_files, model, size, quality, parent_id, creator=''):
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400
    if not image_file:
        return jsonify({'error': 'APIYI 编辑需要至少一张输入图片'}), 400

    try:
        service = get_apiyi_image_service()
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

    api_model = _normalize_apiyi_model(model)
    actual_model = _apiyi_display_model(api_model)
    if api_model == 'gpt-image-2':
        actual_size = size or '1024x1024'
        request_params = _apiyi_gpt_image2_params(request.form)
    else:
        # 按旧模型文档；编辑场景 size 推荐 'auto'（跟随 prompt 点名的图比例）
        actual_size = size if (size and 'x' in str(size).lower()) else 'auto'
        request_params = {}
    response_format = request.form.get('response_format', 'b64_json')

    # 临时目录用于存放上传的主图与参考图（与 fal 路径对齐）
    temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    image_path = None
    mask_path = None
    reference_paths = []

    try:
        if image_file:
            image_path = os.path.join(temp_dir, f'{uuid.uuid4()}_image.png')
            image_file.save(image_path)
            # 长边 3840px 等比缩小（与 gptsapi/fal 编辑一致）
            from services.image_processor import ImageDataProcessor
            downscaled, down_err = ImageDataProcessor.downscale_image(image_path, 3840)
            if down_err:
                print(f"[apiyi_edit] downscale main image warning: {down_err}")
            elif downscaled != image_path:
                image_path = downscaled

        if api_model == 'gpt-image-2' and mask_file:
            mask_path = os.path.join(temp_dir, f'{uuid.uuid4()}_mask.png')
            mask_file.save(mask_path)

        for ref in reference_files:
            ref_path = os.path.join(temp_dir, f'{uuid.uuid4()}_ref.png')
            ref.save(ref_path)
            from services.image_processor import ImageDataProcessor
            downscaled_ref, ref_err = ImageDataProcessor.downscale_image(ref_path, 3840)
            if ref_err:
                print(f"[apiyi_edit] downscale ref image warning: {ref_err}")
            elif downscaled_ref != ref_path:
                reference_paths.append(downscaled_ref)
            else:
                reference_paths.append(ref_path)
    except Exception as save_err:
        # 临时文件保存失败时清理已写入文件
        for p in [image_path, mask_path] + reference_paths:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        return jsonify({'error': f'编辑图保存失败: {save_err}'}), 500

    # 按上传顺序拼接 image_paths：主图 + 参考图，对应 prompt 中「图1/图2/...」
    image_paths = []
    if image_path:
        image_paths.append(image_path)
    image_paths.extend(reference_paths)

    # 编辑关系：与 gptsapi edit 一致
    root_id = None
    depth = 0
    if parent_id:
        parent_relation = get_edit_relation_by_image_id(parent_id)
        if parent_relation:
            root_id = parent_relation.get('root_id')
            depth = parent_relation.get('depth', 0) + 1
        else:
            root_id = parent_id
            depth = 1
        # 没指定 size 时继承父图尺寸
        if not size:
            parent_image = get_image_by_id(parent_id)
            if parent_image and parent_image.size:
                actual_size = parent_image.size

    task_id = str(uuid.uuid4())
    saved_image = add_image(
        url='',
        thumbnail='',
        prompt=build_edit_saved_prompt(parent_id, prompt),
        model=actual_model,
        size=actual_size,
        quality=request_params.get('quality', '') if api_model == 'gpt-image-2' else '',
        task_id=task_id,
        parent_id=parent_id,
        folder_path='',
        image_type='edit',
        api_source='apiyi',
        poster_copy=get_inherited_poster_copy(parent_id),
        # 制作人：APIYI 后台 worker 落盘时不会重复设置 creator，
        # 此处写入 images.creator 后，刷新页面时该字段会被返回
        creator=creator
    )

    if parent_id:
        if not root_id:
            root_id = parent_id
        add_edit_relation(
            image_id=saved_image.id,
            parent_id=parent_id,
            root_id=root_id,
            depth=depth
        )

    add_task(
        task_id=task_id,
        image_id=saved_image.id,
        platform='apiyi',
        status='IN_PROGRESS',
        api_source='apiyi',
        data={
            'api_source': 'apiyi',
            'model': api_model,
            'prompt': prompt,
            'size': actual_size,
            'response_format': response_format,
            'request_params': request_params,
            'parent_id': parent_id,
            'image_paths': image_paths,
            'mask_path': mask_path,
            # 制作人：随任务数据透传，run_apiyi_edit_worker 落盘时优先读取此字段
            'creator': creator
        }
    )

    app_obj = current_app._get_current_object()

    # 把原 _worker 闭包逻辑抽到 services.apiyi_async_workers，复用于 retry
    from services.apiyi_async_workers import run_apiyi_edit_worker
    _apiyi_executor.submit(
        run_apiyi_edit_worker,
        app_obj,
        service,
        task_id,
        saved_image,
        image_paths,
        prompt,
        actual_size,
        response_format,
        api_model,
        request_params,
        mask_path,
    )

    saved_image = get_image_by_id(saved_image.id) or saved_image
    print(f"[images] APIYI edit async submitted: task_id={task_id}, image_id={saved_image.id}")
    return jsonify({
        'status': 'pending',
        'task_id': task_id,
        'image': serialize_image(saved_image)
    }), 202


@images_bp.route('/api/images/edits', methods=['POST'])
def edit_image():
    prompt = request.form.get('prompt')
    image_files = request.files.getlist('image')
    image_file = image_files[0] if image_files else None
    reference_files = image_files[1:] if len(image_files) > 1 else []
    mask_file = request.files.get('mask')
    model = request.form.get('model', 'gpt-image-2')
    size = request.form.get('size', 'auto')
    quality = request.form.get('quality', 'auto')
    response_format = request.form.get('response_format', 'url')
    parent_id = request.form.get('parent_id')
    if parent_id and not current_user_is_admin():
        parent_image_for_access = get_image_by_id(parent_id, creator=current_creator())
        if not parent_image_for_access:
            return jsonify({'error': '无权限'}), 403
    async_mode = str(request.args.get('async', '')).lower() == 'true'
    n = int(request.form.get('n', 1))
    seed = int(request.form.get('seed', 0))
    moderation = request.form.get('moderation', 'auto')
    background = request.form.get('background', 'auto')
    output_format = request.form.get('output_format', 'png')
    api_provider = request.form.get('api_provider', 'openai')
    # 制作人：随编辑请求上传到后端，写入 images.creator
    # 与生图链路对齐（参考 routes/images.py 中 generate_image 路由读取 data.get('creator') 的实现）
    # 优先级：表单值 > 父图继承值（保持编辑链路一致，避免每次编辑都丢失制作人）
    raw_creator = (request.form.get('creator') or '').strip()
    creator = _creator_from_request(raw_creator or get_inherited_creator(parent_id))

    # 前端诊断：参考图计数
    diagnostic_ref_count = request.form.get('_diagnostic_ref_count', 'not_sent')
    print(
        f"[images] Received edit request: async={async_mode}, model={model}, "
        f"size={size}, quality={quality}, parent_id={parent_id}, "
        f"n={n}, seed={seed}, output_format={output_format}, "
        f"has_image={bool(image_file)}, has_mask={bool(mask_file)}, "
        f"reference_count={len(reference_files)}, diagnostic_ref_count={diagnostic_ref_count}, "
        f"creator='{creator}'"
    )

    # Fal API 编辑分支
    if api_provider == 'fal':
        return _handle_fal_edit(request, prompt, image_file, mask_file, reference_files, model, size, quality, parent_id, creator)

    if api_provider == 'gptsapi':
        return _handle_gptsapi_edit(request, prompt, image_file, reference_files, model, size, quality, parent_id, async_mode, creator)

    # APIYI 编辑分支（gpt-image-2-vip，走后台线程异步执行）
    if api_provider == 'apiyi':
        return _handle_apiyi_edit(request, prompt, image_file, mask_file, reference_files, model, size, quality, parent_id, creator)

    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    import os
    import uuid
    from services.image_processor import ImageDataProcessor

    temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')
    os.makedirs(temp_dir, exist_ok=True)

    image_path = None
    mask_path = None
    reference_paths = []

    # 图片文件预处理：对超过 3840px 长边的图片进行等比缩小
    if image_file:
        image_path = os.path.join(temp_dir, f'{uuid.uuid4()}_image.png')
        image_file.save(image_path)
        downscaled_path, downscale_err = ImageDataProcessor.downscale_image(image_path, 3840)
        if downscale_err:
            print(f"[images] Warning: image downscale failed: {downscale_err}")
        elif downscaled_path != image_path:
            image_path = downscaled_path

    if mask_file:
        mask_path = os.path.join(temp_dir, f'{uuid.uuid4()}_mask.png')
        mask_file.save(mask_path)

        # 确保 mask 格式与 OpenAI 官方文档完全一致（RGBA + putalpha）
        if image_path and os.path.exists(image_path):
            try:
                from PIL import Image

                with Image.open(image_path) as orig:
                    original_size = orig.size

                with Image.open(mask_path) as mask_img:
                    needs_resize = original_size and mask_img.size != original_size
                    if needs_resize:
                        mask_img = mask_img.resize(original_size, Image.LANCZOS)

                    grayscale = mask_img.convert("L")
                    inverted = grayscale.point(lambda v: 255 - v)
                    mask_rgba = inverted.convert("RGBA")
                    mask_rgba.putalpha(inverted)
                    mask_rgba.save(mask_path, 'PNG')

                    alpha_min, alpha_max = inverted.getextrema()
                    if alpha_min == alpha_max:
                        print(f"[images] WARNING: Mask is uniform (value={alpha_min}), may not have editable regions")
                    print(f"[images] Mask processed: grayscale+RGBA+putalpha, size={mask_rgba.size}, range=[{alpha_min},{alpha_max}]")
            except Exception as e:
                print(f"[images] WARNING: Mask processing failed: {e}, sending as-is")

    for reference_file in reference_files:
        reference_path = os.path.join(temp_dir, f'{uuid.uuid4()}_reference.png')
        reference_file.save(reference_path)
        # 参考图也需要进行缩小预处理
        downscaled_ref, ref_err = ImageDataProcessor.downscale_image(reference_path, 3840)
        if ref_err:
            print(f"[images] Warning: reference image downscale failed: {ref_err}")
        elif downscaled_ref != reference_path:
            reference_paths.append(downscaled_ref)
        else:
            reference_paths.append(reference_path)

    service = get_image_service()
    try:
        result = service.edit_image(
            prompt=prompt,
            image_path=image_path,
            mask_path=mask_path,
            model=model,
            size=size,
            response_format=response_format,
            quality=quality,
            async_mode=async_mode,
            n=n,
            seed=seed,
            moderation=moderation,
            background=background,
            output_format=output_format,
            reference_image_paths=reference_paths
        )
    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        if mask_path and os.path.exists(mask_path):
            os.remove(mask_path)
        for reference_path in reference_paths:
            if os.path.exists(reference_path):
                os.remove(reference_path)

    if 'error' in result:
        print(f"[images] Edit request failed: {result['error']}")
        return jsonify(result), 500

    print(f"[images] Edit request accepted, async={async_mode}")

    root_id = None
    depth = 0

    if parent_id:
        parent_relation = get_edit_relation_by_image_id(parent_id)
        if parent_relation:
            root_id = parent_relation.get('root_id')
            depth = parent_relation.get('depth', 0) + 1
        else:
            root_id = parent_id
            depth = 1

        # 如果没有指定尺寸，继承父图片的尺寸
        if not size:
            parent_image = get_image_by_id(parent_id)
            if parent_image:
                size = parent_image.size or '1024x1024'

    if async_mode:
        task_id = extract_async_task_id(result)
        if not task_id:
            print("[images] Async edit response missing task_id")
            return jsonify({
                'error': '异步图片编辑接口未返回 task_id，无法继续跟踪任务'
            }), 502

        saved_image = add_image(
            url='',
            thumbnail='',
            prompt=build_edit_saved_prompt(parent_id, prompt),
            model=model,
            size=size,
            quality=quality,
            task_id=task_id,
            parent_id=parent_id,
            folder_path='',
            image_type='edit',
            poster_copy=get_inherited_poster_copy(parent_id),
            # 制作人：写入 images.creator，保证编辑画板筛选能命中本张图
            creator=creator
        )

        if parent_id:
            if not root_id:
                root_id = parent_id
            add_edit_relation(
                image_id=saved_image.id,
                parent_id=parent_id,
                root_id=root_id,
                depth=depth
            )

        add_task(
            task_id=task_id,
            image_id=saved_image.id,
            platform=result.get('platform', ''),
            status='IN_PROGRESS',
            data={
                'raw_edit_result': result,
                'response_format': response_format,
                'n': n,
                'seed': seed,
                'output_format': output_format
            }
        )

        saved_image = get_image_by_id(saved_image.id) or saved_image
        print(f"[images] Async edit task created: task_id={task_id}, image_id={saved_image.id}")
        return jsonify({
            'status': 'pending',
            'task_id': task_id,
            'image': serialize_image(saved_image)
        }), 202

    image_data = result.get('data', [{}])[0] if result.get('data') else {}
    image_url = image_data.get('url', '')
    b64_json = image_data.get('b64_json', '')
    revised_prompt = image_data.get('revised_prompt', prompt)

    # 如果有 b64_json 数据，先剥离前缀再保存到本地
    if b64_json:
        from services.image_processor import ImageDataProcessor
        cleaned_b64 = ImageDataProcessor.strip_b64_prefix(b64_json)
        output_dir = ImageDataProcessor.get_output_dir()
        # 把用户选择的 output_format 透传给 save_b64_image，
        # 让落盘扩展名与实际格式一致（避免 JPEG 内容被存成 .png）
        local_path, static_url, b64_err = ImageDataProcessor.save_b64_image(
            cleaned_b64, output_dir, f"edit_sync", output_format
        )
        if b64_err:
            print(f"[images] Sync edit b64_json save failed: {b64_err}")
        else:
            image_url = static_url

    asset_result = {
        'url': image_url,
        'display_url': image_url,
        'thumbnail': '',
        'local_path': None,
        'thumbnail_path': None,
        'error': ''
    }

    if image_url:
        try:
            asset_result = save_edit_result_directly(image_url, prompt, size, creator=creator)
        except (ValueError, RuntimeError) as err:
            print(f"[images] Warning: Failed to save edit assets: {err}")
            asset_result['error'] = str(err)

    saved_image = add_image(
        url=asset_result.get('display_url') or asset_result.get('url', image_url),
        thumbnail=asset_result.get('thumbnail', ''),
        prompt=build_edit_saved_prompt(parent_id, prompt),
        model=model,
        size=size,
        quality=quality,
        local_path=asset_result.get('local_path'),
        thumbnail_path=asset_result.get('thumbnail_path'),
        parent_id=parent_id,
        folder_path='',
        image_type='edit',
        poster_copy=get_inherited_poster_copy(parent_id),
        # 制作人：同步编辑结果写入 images.creator，确保画板筛选可用
        creator=creator
    )

    # 添加编辑关系
    if parent_id:
        if not root_id:
            root_id = parent_id
        add_edit_relation(
            image_id=saved_image.id,
            parent_id=parent_id,
            root_id=root_id,
            depth=depth
        )

    print(f"[images] Sync edit completed: image_id={saved_image.id}, image_url={saved_image.url}")
    return jsonify({
        'status': 'success',
        'image': serialize_image(saved_image)
    }), 200


# Fal API 图片编辑处理
# 功能描述：
#     处理 fal 协议的异步图片编辑请求
#     将上传的图片文件转为 base64 data URL，以 JSON 方式提交到 fal 队列
# 实现逻辑：
#     1. 将上传的图片文件读取并转为二进制
#     2. 优先上传到 /v1/files 获取 URL，失败则 fallback 到 base64
#     3. 调用 FalImageService.submit_edit() 提交 JSON 请求
#     4. 提交后先检查 result 是否直接包含 images（API 同步模式直接返回）
#     5. 异步模式：创建任务和图片记录后返回，存储 response_url 供轮询
#     6. skip_error=True 时，失败不抛错，返回空占位结果
def _handle_fal_edit(request, prompt, image_file, mask_file, reference_files, model, size, quality, parent_id, creator=''):
    try:
        fal_service = get_fal_image_service()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # 提取 fal 专用参数
    num_images = int(request.form.get('num_images', 1))
    output_format = request.form.get('output_format', 'png')
    image_size = _parse_size_to_image_size(size or 'auto')
    seed = request.form.get('seed', 0, type=int)
    skip_error = str(request.form.get('skip_error', 'false')).lower() == 'true'

    print(f"[FalEdit] ===== ENTER _handle_fal_edit =====")
    print(f"[FalEdit] prompt='{prompt[:80] if prompt else 'NONE'}...' image_file={'YES' if image_file else 'NO'}")
    print(f"[FalEdit] reference_files COUNT={len(reference_files)}")
    for i, rf in enumerate(reference_files):
        print(f"[FalEdit]   ref_file[{i}]: filename={rf.filename}, content_type={rf.content_type}")

    # 上传图片到 /v1/files，失败抛出异常（不再回退 base64）
    def file_to_url_strict(file_obj, fallback_prefix="image"):
        raw = file_obj.read()
        print(f"[FalEdit] Uploading {fallback_prefix}... size={len(raw)} bytes")
        uploaded_url = _upload_image_priority(raw, f"{fallback_prefix}.png")
        if not uploaded_url:
            print(f"[FalEdit] ⚠ {fallback_prefix} upload FAILED")
            raise ValueError(f'{fallback_prefix} 图片上传失败，无法继续 FAL 编辑')
        print(f"[FalEdit] {fallback_prefix} upload SUCCESS: {uploaded_url[:80]}...")
        return uploaded_url

    # 主图：优先上传
    try:
        image_urls = [file_to_url_strict(image_file, "main")]

        # 处理参考图（来自 FormData 文件）
        for idx, ref_file in enumerate(reference_files):
            image_urls.append(file_to_url_strict(ref_file, f"ref_{idx}"))

        # 处理遮罩
        mask_image_url = None
        if mask_file:
            mask_image_url = file_to_url_strict(mask_file, "mask")
    except ValueError as e:
        return jsonify({'error': str(e)}), 502

    # 处理参考图（来自 URL，前端 CORS 限制时通过 _ref_image_urls 传递）
    # 直接使用 URL，不重新下载上传（图片已有可访问的 HTTP 地址）
    ref_image_urls_json = request.form.get('_ref_image_urls', '')
    if ref_image_urls_json:
        try:
            import json as _json
            url_refs = _json.loads(ref_image_urls_json)
            for url in url_refs:
                if url and (url.startswith('http://') or url.startswith('https://')):
                    image_urls.append(url)
                    print(f"[FalEdit] URL ref added directly: {url[:100]}...")
                else:
                    print(f"[FalEdit] Invalid ref URL skipped: {str(url)[:80]}...")
        except Exception as e:
            print(f"[FalEdit] Failed to parse _ref_image_urls: {e}")

    print(f"[FalEdit] ===== Submitting to Fal API =====")
    print(f"[FalEdit] image_urls final list ({len(image_urls)} URLs):")
    for i, url in enumerate(image_urls):
        print(f"[FalEdit]   image_urls[{i}]: {url[:100]}...")
    print(f"[FalEdit] mask_image_url={'YES' if mask_image_url else 'NO'}")
    print(f"[FalEdit] model={model}, image_size={image_size}")

    # 模型固定为 openai/gpt-image-2/edit
    model = 'openai/gpt-image-2/edit'

    # 调用 fal 服务提交编辑请求，模型固定为 openai/gpt-image-2/edit
    result = fal_service.submit_edit(
        prompt=prompt,
        image_urls=image_urls,
        model='openai/gpt-image-2/edit',
        mask_image_url=mask_image_url,
        image_size=image_size,
        quality=quality,
        num_images=num_images,
        output_format=output_format,
        seed=seed,
        sync_mode=False
    )

    print(f"[FalEdit] ===== Fal API response =====")
    print(f"[FalEdit] has_images={'images' in result and bool(result['images'])}")
    print(f"[FalEdit] request_id={result.get('request_id', 'N/A')}")
    print(f"[FalEdit] has_error={'error' in result}")
    if 'error' in result:
        print(f"[FalEdit] error={str(result['error'])[:200]}")

    if 'error' in result:
        if skip_error:
            return jsonify({'status': 'skipped', 'error': result['error'], 'image': None}), 200
        return jsonify(result), 500

    # 将 image_size 转为字符串用于数据库存储（SQLite 不支持 dict）
    size_for_db = json.dumps(image_size, ensure_ascii=False) if isinstance(image_size, dict) else image_size

    # 处理编辑关系（提前获取，同步和异步都需要）
    root_id = None
    depth = 0
    if parent_id:
        parent_relation = get_edit_relation_by_image_id(parent_id)
        if parent_relation:
            root_id = parent_relation.get('root_id')
            depth = parent_relation.get('depth', 0) + 1
        else:
            root_id = parent_id
            depth = 1

    # 检查是否同步模式直接返回了图片（result 中直接包含 images）
    if 'images' in result and result['images']:
        result_images = result['images']
        image_url = result_images[0].get('url', '') if isinstance(result_images[0], dict) else ''
        if not image_url:
            if skip_error:
                return jsonify({'status': 'skipped', 'error': 'Fal 编辑同步返回图片 URL 为空', 'image': None}), 200
            return jsonify({'error': 'Fal 编辑同步返回图片 URL 为空'}), 500

        # 同步模式直接返回：保存资产和记录
        asset_result = save_edit_result_directly(image_url, prompt, size, creator=creator)
        saved_image = add_image(
            url=asset_result.get('display_url') or asset_result.get('url', image_url),
            thumbnail=asset_result.get('thumbnail', ''),
            prompt=build_edit_saved_prompt(parent_id, prompt),
            model=model,
            size=size_for_db,
            quality=quality,
            local_path=asset_result.get('local_path'),
            thumbnail_path=asset_result.get('thumbnail_path'),
            parent_id=parent_id,
            folder_path='',
            image_type='edit',
            poster_copy=get_inherited_poster_copy(parent_id),
            # 制作人：同步编辑结果写入 images.creator，确保画板筛选可用
            creator=creator
        )

        if parent_id:
            if not root_id:
                root_id = parent_id
            add_edit_relation(
                image_id=saved_image.id,
                parent_id=parent_id,
                root_id=root_id,
                depth=depth
            )

        print(f"[images] Fal edit direct sync result: image_id={saved_image.id}")
        return jsonify({
            'status': 'success',
            'image': serialize_image(saved_image)
        }), 200

    request_id = result.get('request_id')
    response_url = result.get('response_url', '')
    if not request_id:
        if skip_error:
            return jsonify({'status': 'skipped', 'error': 'Fal API 未返回 request_id', 'image': None}), 200
        return jsonify({
            'error': 'Fal API 未返回 request_id，无法继续跟踪任务'
        }), 502

    # 创建图片记录
    saved_image = add_image(
        url='',
        thumbnail='',
        prompt=build_edit_saved_prompt(parent_id, prompt),
        model=model,
        size=size_for_db,
        quality=quality,
        task_id=request_id,
        parent_id=parent_id,
        folder_path='',
        image_type='edit',
        poster_copy=get_inherited_poster_copy(parent_id),
        # 制作人：异步任务占位记录写入 images.creator，轮询结果会沿用同一 image_id
        creator=creator
    )

    # 添加编辑关系
    if parent_id:
        if not root_id:
            root_id = parent_id
        add_edit_relation(
            image_id=saved_image.id,
            parent_id=parent_id,
            root_id=root_id,
            depth=depth
        )

    # 创建任务记录，存储 response_url 供后续轮询使用
    add_task(
        task_id=request_id,
        image_id=saved_image.id,
        platform='fal',
        status='IN_PROGRESS',
        data={
            'api_source': 'fal',
            'model': model,
            'response_url': response_url,
            'raw_edit_result': result,
            # 制作人：随任务数据透传，TaskProcessor 落盘结果时优先读取此字段
            'creator': creator
        }
    )

    saved_image = get_image_by_id(saved_image.id) or saved_image
    print(f"[images] Fal edit submitted: request_id={request_id}, image_id={saved_image.id}")
    return jsonify({
        'status': 'pending',
        'task_id': request_id,
        'image': serialize_image(saved_image)
    }), 202


@images_bp.route('/api/images/compress', methods=['POST'])
def compress_image():
    data = request.get_json()
    image_url = data.get('image_url')
    quality = data.get('quality', 90)

    if not image_url:
        return jsonify({'error': 'image_url is required'}), 400

    service = get_image_service()
    result = service.compress_image(image_url=image_url, quality=quality)

    return jsonify(result), 200


@images_bp.route('/api/images/tasks/<task_id>', methods=['GET'])
def query_task(task_id):
    """
    查询异步任务状态（纯本地数据库读取）

    功能描述：
        从本地数据库读取任务状态并返回给前端。
        不再查询第三方 API，第三方 API 的查询和状态同步由 TaskProcessor 后台线程负责。

    实现逻辑：
        1. 从本地数据库获取任务和关联图片
        2. 如果任务不存在，返回 404 错误
        3. 直接返回数据库中的当前状态

    异常处理：
        - 任务不存在：返回 404
        - data 字段解析失败：使用空字典兜底
    """
    current_task = get_task(task_id)

    if not current_task:
        return jsonify({
            'error': '任务不存在',
            'task_id': task_id
        }), 404

    current_image = get_image_by_task_id(task_id)

    task_status = current_task.get('status', 'UNKNOWN')
    fail_reason = current_task.get('fail_reason', '')

    # 从 task 的 data 字段中提取额外信息
    task_data = current_task.get('data', {})
    if isinstance(task_data, str):
        try:
            task_data = json.loads(task_data)
        except Exception:
            task_data = {}

    download_error = ''
    raw_result = None
    poll_count = 0
    max_polls = 0
    if isinstance(task_data, dict):
        download_error = task_data.get('download_error', '')
        raw_result = task_data.get('raw_query_result')
        poll_count = task_data.get('poll_count', 0)
        max_polls = task_data.get('max_polls', 0)

    return jsonify({
        'status': 'success',
        'task_id': task_id,
        'task_status': task_status,
        'fail_reason': fail_reason,
        'downloaded': bool(current_image and (getattr(current_image, 'local_path', None) or getattr(current_image, 'url', None))),
        'download_error': download_error,
        'poll_count': poll_count,
        'max_polls': max_polls,
        'image': serialize_image(current_image) if current_image else None,
        'raw_result': raw_result
    }), 200


@images_bp.route('/api/images/upload', methods=['POST'])
def upload_image():
    """
    上传图片到文件服务获取在线 URL

    功能描述：
        接收前端上传的图片文件，上传到配置的文件服务（如 ImgBB、SM.MS 等），
        返回在线 URL 供前端使用，替代 base64 方式。

    实现逻辑：
        1. 检查是否有文件在请求中
        2. 读取 file_upload 配置获取 baseUrl 和 apiKey
        3. 如果配置不完整，返回错误
        4. 使用 FileUploadService 上传图片
        5. 返回上传后的 URL
    """
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': '没有上传文件'}), 400

    file = request.files['image']
    if not file or file.filename == '':
        return jsonify({'status': 'error', 'message': '文件名为空'}), 400

    upload_service = get_file_upload_service()
    if not upload_service:
        return jsonify({'status': 'error', 'message': '文件上传服务未配置，请先在设置中配置 baseUrl 和 apiKey'}), 400

    try:
        filename = file.filename or 'upload.png'
        file_content = file.read()
        uploaded_url = upload_service.upload(file_content, filename)

        if not uploaded_url:
            return jsonify({'status': 'error', 'message': '上传失败，未返回 URL'}), 500

        print(f"[images] 图片上传成功: {uploaded_url[:80]}...")
        return jsonify({
            'status': 'success',
            'url': uploaded_url,
            'filename': filename
        }), 200

    except Exception as e:
        print(f"[images] 图片上传异常: {str(e)}")
        return jsonify({'status': 'error', 'message': f'上传失败: {str(e)}'}), 500


@images_bp.route('/api/images/thumbnails/repair-jpg', methods=['POST'])
def repair_thumbnails_to_jpg():
    processed = 0
    succeeded = 0
    failed = 0
    failures = []

    try:
        for image_type in ('generation', 'edit'):
            for image in load_images(image_type=image_type):
                if getattr(image, 'api_source', '') == 'topaz_gigapixel' or getattr(image, 'image_type', '') == 'gigapixel':
                    continue
                processed += 1
                try:
                    result = _repair_one_image_thumbnail_to_jpg(image)
                    if result.get('success'):
                        succeeded += 1
                    else:
                        failed += 1
                        if len(failures) < 20:
                            failures.append({'id': getattr(image, 'id', ''), 'error': result.get('error', '')})
                except Exception as err:
                    failed += 1
                    if len(failures) < 20:
                        failures.append({'id': getattr(image, 'id', ''), 'error': str(err)})
                    print(f"[images] Warning: failed to repair thumbnail for {getattr(image, 'id', '')}: {err}")

        material_result = _repair_material_thumbnails_to_jpg()
        processed += material_result['processed']
        succeeded += material_result['succeeded']
        failed += material_result['failed']

        return jsonify({
            'success': True,
            'processed': processed,
            'succeeded': succeeded,
            'failed': failed,
            'failures': failures
        }), 200
    except Exception as err:
        print(f"[images] repair jpg thumbnails failed: {err}")
        return jsonify({'success': False, 'error': str(err)}), 500


@images_bp.route('/api/images', methods=['GET'])
def get_images():
    image_type = request.args.get('image_type', 'generation')
    if image_type not in ('generation', 'edit'):
        image_type = 'generation'
    images = load_images(image_type=image_type, creator=_image_scope_creator())
    updated_images = []
    for image in images:
        try:
            repair_thumbnail_if_needed(image)
        except (ValueError, RuntimeError) as err:
            print(f"[images] Warning: Failed to repair thumbnail for {image.id}: {err}")
        refreshed_image = get_image_by_id(image.id, creator=_image_scope_creator())
        updated_images.append(serialize_image(refreshed_image) if refreshed_image else serialize_image(image))

    return jsonify({
        'status': 'success',
        'images': updated_images
    }), 200


@images_bp.route('/api/images/<image_id>', methods=['GET'])
def get_single_image(image_id):
    """
    获取单张图片详情

    功能描述：
        根据 image_id 返回单张图片的完整信息
    """
    image = _get_scoped_image_by_id(image_id)
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    return jsonify({'status': 'success', 'image': serialize_image(image)}), 200


@images_bp.route('/api/images/<image_id>', methods=['DELETE'])
def remove_image(image_id):
    """
    删除图片

    功能描述：
        删除图片记录及其本地文件（如果有）

    实现逻辑：
        1. 删除数据库中的图片记录
        2. 如果存在本地文件，也一并删除

    异常处理：
        - 数据库删除失败：返回 404
        - 本地文件删除失败：记录日志但不影响返回结果
    """
    image = _get_scoped_image_by_id(image_id)
    success, local_path = delete_image(image_id)

    if success:
        # 如果存在本地文件，也删除它
        if local_path:
            try:
                delete_local_file(local_path)
            except Exception as e:
                print(f"[images] Warning: Failed to delete local file: {e}")

        if image and image.thumbnail and image.thumbnail.startswith(THUMBNAIL_STATIC_PREFIX):
            thumbnail_filename = image.thumbnail.replace(THUMBNAIL_STATIC_PREFIX, '', 1)
            thumbnail_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'generated_thumbnails',
                thumbnail_filename
            )
            try:
                delete_local_file(thumbnail_path)
            except Exception as e:
                print(f"[images] Warning: Failed to delete thumbnail file: {e}")

        return jsonify({'status': 'success', 'message': 'Image deleted'}), 200
    else:
        return jsonify({'error': 'Image not found'}), 404


@images_bp.route('/api/images/<image_id>/rename', methods=['PUT'])
def update_image_title(image_id):
    """
    重命名图片

    功能描述：
        更新图片标题，并重命名本地文件和文件夹（如果有）

    请求体：
        {
            "title": "新标题"
        }

    异常处理：
        - 图片不存在：返回 404
        - 重命名失败：返回 500
    """
    data = request.get_json()
    new_title = data.get('title')

    if not new_title:
        return jsonify({'error': 'title is required'}), 400

    # 获取当前图片信息
    current_image = _get_scoped_image_by_id(image_id)
    if not current_image:
        return jsonify({'error': 'Image not found'}), 404

    # 重命名本地文件
    success, updated_image, new_local_path = rename_image(image_id, new_title)

    if success:
        # 如果有文件夹，同步重命名文件夹
        if current_image.folder_path:
            folder_result = rename_edit_folder(current_image.folder_path, new_title)
            if folder_result.get('success') and folder_result.get('new_folder_path') != current_image.folder_path:
                # 更新数据库中的文件夹路径（级联更新）
                update_image_folder_path(image_id, folder_result['new_folder_path'])
                # 重新获取更新后的图片
                updated_image = _get_scoped_image_by_id(image_id)

        response_data = {
            'status': 'success',
            'image': serialize_image(updated_image) if updated_image else None
        }
        if new_local_path:
            response_data['new_local_path'] = new_local_path
        return jsonify(response_data), 200
    else:
        return jsonify({'error': 'Image not found'}), 404


@images_bp.route('/api/images/<image_id>/edits', methods=['GET'])
def get_image_edit_history(image_id):
    """
    获取图片的编辑历史树

    功能描述：
        查询某张图片的完整编辑历史，包括所有子图片

    实现逻辑：
        1. 查询 edit_relations 表获取关系
        2. 关联 images 表获取完整信息
        3. 返回树形结构数据

    异常处理：
        - 图片不存在：返回 404
        - 查询失败：返回 500
    """
    try:
        # 获取图片信息
        image = _get_scoped_image_by_id(image_id)
        if not image:
            return jsonify({'error': 'Image not found'}), 404

        # 查询编辑历史
        edits = get_image_edits(image_id)

        # 构建树形结构
        edit_tree = []
        node_map = {}

        # 首先添加根节点
        root_node = build_edit_tree_node(image, parent_id=None, depth=0)
        root_node['prompt'] = image.prompt or '原图'
        edit_tree.append(root_node)
        node_map[image.id] = root_node

        # 添加编辑节点
        for edit in edits:
            if edit['id'] == image_id:
                continue  # 跳过根节点

            class EditTreeNode:
                pass

            node_item = EditTreeNode()
            node_item.id = edit['id']
            node_item.url = edit.get('url', '')
            node_item.thumbnail = edit.get('thumbnail', '')
            node_item.prompt = edit.get('prompt', '')
            node_item.title = edit.get('title')
            node_item.generating = edit.get('generating', False)
            node_item.task_id = edit.get('task_id')
            node_item.download_error = edit.get('download_error') or ''
            node_item.fail_reason = edit.get('fail_reason') or ''
            node_item.size = edit.get('size', '')
            node_item.local_path = edit.get('local_path')
            node_item.folder_path = edit.get('folder_path')
            node_item.image_type = edit.get('image_type', 'edit')
            node = build_edit_tree_node(node_item, parent_id=edit.get('parent_id'), depth=edit.get('depth', 0))
            edit_tree.append(node)
            node_map[edit['id']] = node

        return jsonify({
            'status': 'success',
            'image_id': image_id,
            'edit_tree': edit_tree
        }), 200

    except Exception as e:
        print(f"[images] Failed to get edit history: {e}")
        return jsonify({'error': 'Failed to get edit history'}), 500


@images_bp.route('/api/images/download', methods=['POST'])
def download_image():
    """
    下载图片到本地存储目录

    功能描述：
        接收图片 URL，下载并保存到本地 generated_images 目录

    请求体：
        {
            "image_url": "https://example.com/image.png"
        }

    响应：
        - 成功：返回本地文件路径和其他元数据
        - 失败：返回错误信息
    """
    data = request.get_json()
    image_url = data.get('image_url')

    if not image_url:
        return jsonify({'error': 'image_url is required'}), 400

    try:
        result = download_image_to_local(image_url, creator=current_creator())
        return jsonify({
            'status': 'success',
            'data': result
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500


@images_bp.route('/api/images/gptsapi/retry', methods=['POST'])
def gptsapi_retry():
    data = request.get_json(silent=True) or {}
    raw_result = data.get('raw_result')
    poll_url = data.get('poll_url')
    prompt = data.get('prompt', '')
    model = data.get('model', 'gptsapi/gpt-image-2')
    size = data.get('size', '')
    aspect_ratio = data.get('aspect_ratio') or data.get('aspectRatio', '')
    resolution = data.get('resolution', '2K')
    image_type = data.get('image_type', 'generation')
    creator = _creator_from_request(data.get('creator'))
    # 从 raw_result 中提取查询 URL
    if not poll_url:
        if isinstance(raw_result, dict):
            data_wrapper = raw_result.get('data') or {}
            urls_wrapper = data_wrapper.get('urls') or {}
            poll_url = urls_wrapper.get('get') or raw_result.get('urls', {}).get('get')
        if not poll_url:
            return jsonify({'error': '缺少 GPTsAPI 查询 URL（poll_url）'}), 400

    try:
        service = get_gptsapi_image_service()
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

    query_result = service.query_result(poll_url)
    if 'error' in query_result:
        return jsonify({'error': f'查询 GPTsAPI 结果失败: {query_result["error"]}'}), 500

    image_urls = _extract_image_urls_from_result(query_result)
    if not image_urls:
        return jsonify({'error': '查询 GPTsAPI 结果中未找到图片 URL', 'raw_query_result': query_result}), 500

    first_url = image_urls[0]
    try:
        asset_result = prepare_image_assets(first_url, creator=creator)
    except (ValueError, RuntimeError) as err:
        print(f"[images] GPTsAPI retry: Failed to prepare assets: {err}")
        asset_result = {'url': first_url, 'thumbnail': '', 'local_path': None, 'thumbnail_path': None}

    saved_image = add_image(
        url=asset_result.get('url', first_url),
        thumbnail=asset_result.get('thumbnail', ''),
        prompt=prompt,
        model=model,
        size=size,
        local_path=asset_result.get('local_path'),
        thumbnail_path=asset_result.get('thumbnail_path'),
                image_type=image_type,
                api_source='gptsapi',
                creator=creator
            )

    if len(image_urls) > 1:
        for extra_url in image_urls[1:]:
            from services.background_download_service import enqueue_image_download
            enqueue_image_download(
                image_id=saved_image.id,
                image_url=extra_url,
                image_type=image_type,
                task_id=getattr(saved_image, 'task_id', None)
            )

    return jsonify({
        'status': 'success',
        'image': serialize_image(saved_image)
    }), 200


# APIYI 失败任务重试路由
# 功能描述：
#     前端在失败任务卡上点「重试」时调用，复用 task.data 中的参数（prompt/size/image_paths）
#     重新提交到 _apiyi_executor；服务内部会先校验 temp 文件是否还在。
# 实现逻辑：
#     1. 接收 { task_id } JSON；缺失返回 400
#     2. 调用 apiyi_retry_service.retry_apiyi_task(task_id, _apiyi_executor)
#     3. 把 service 返回的 ok/error_code 映射为 HTTP 状态码：
#         - ok=True: 202
#         - temp_files_missing: 410 (Gone) - 资源失效，需重新提交
#         - status_not_failure: 409 (Conflict)
#         - 其他: 400
# 异常处理：捕获 service 内未覆盖的异常，兜底返回 500
@images_bp.route('/api/images/apiyi/retry', methods=['POST'])
def apiyi_retry():
    data = request.get_json(silent=True) or {}
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'ok': False, 'error': 'task_id is required'}), 400

    from services.apiyi_retry_service import retry_apiyi_task
    result = retry_apiyi_task(task_id, _apiyi_executor)

    if result.get('ok'):
        return jsonify({
            'ok': True,
            'status': 'pending',
            'task_id': result['task_id'],
            'image_id': result.get('image_id'),
            'retry_count': result.get('retry_count', 1),
        }), 202

    err_code = result.get('error_code', 'unknown')
    err_msg = result.get('error', '重试失败')
    if err_code == 'task_not_found':
        return jsonify({'ok': False, 'error_code': err_code, 'error': err_msg}), 404
    if err_code in ('temp_files_missing', 'image_missing'):
        return jsonify({'ok': False, 'error_code': err_code, 'error': err_msg}), 410
    if err_code == 'status_not_failure':
        return jsonify({'ok': False, 'error_code': err_code, 'error': err_msg}), 409
    return jsonify({'ok': False, 'error_code': err_code, 'error': err_msg}), 400


@images_bp.route('/api/images/<image_id>/refresh', methods=['POST'])
def refresh_image(image_id):
    image = _get_scoped_image_by_id(image_id)

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    data = request.get_json()
    image_url = data.get('image_url', image.url)

    if not image_url:
        return jsonify({'error': 'image_url is required and no URL found in database'}), 400

    try:
        asset_result = prepare_image_assets(image_url, creator=getattr(image, 'creator', '') or current_creator())

        image.url = asset_result.get('url') or image_url
        image.local_path = asset_result.get('local_path')
        image.thumbnail = asset_result.get('thumbnail', '')
        image.thumbnail_path = asset_result.get('thumbnail_path')

        update_image(image)

        return jsonify({
            'status': 'success',
            'image': serialize_image(image),
            'download_result': asset_result
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500
