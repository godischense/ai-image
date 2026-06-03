import os
import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from .database import get_db_connection

@dataclass
class ImageItem:
    id: str
    url: str
    thumbnail: str
    prompt: str
    model: str
    size: str
    quality: str
    created_at: str
    task_id: Optional[str] = None
    local_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    title: Optional[str] = None
    updated_at: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[str] = None
    fail_reason: Optional[str] = None
    generating: bool = False
    download_error: Optional[str] = None
    parent_id: Optional[str] = None
    folder_path: Optional[str] = None
    image_type: str = 'generation'
    aspect_ratio: Optional[float] = None
    api_source: Optional[str] = None
    poster_copy: str = ''


PENDING_TASK_STATUSES = {
    'PENDING',
    'IN_PROGRESS',
    '未启动',
    'QUEUED',
    'NOT_STARTED',
    'NOT_START',  # OpenAI GPT 图像 API 使用的状态
    'WAITING'
}
PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GENERATED_IMAGES_DIR = os.path.join(PROJECT_ROOT_DIR, 'generated_images')
EDIT_FOLDERS_DIR = os.path.join(PROJECT_ROOT_DIR, 'edit_folders')
SUPPORTED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def build_static_url_from_local_path(local_path: Optional[str]) -> str:
    """
    基于本地图片路径构建前端静态访问地址

    功能描述：
        将数据库中的本地原图路径统一转换为前端可访问的静态 URL，
        供重命名后的地址同步和历史数据兜底复用。

    实现逻辑：
        1. 为空或无效路径时直接返回空字符串
        2. 命中 generated_images 目录时返回普通生图静态地址
        3. 命中 edit_folders 目录时返回编辑原图静态地址
        4. 其他路径保持空字符串，避免误拼接错误 URL
    """
    if not local_path or not isinstance(local_path, str):
        return ''

    normalized_path = os.path.normpath(local_path.strip())
    if not normalized_path:
        return ''

    if not os.path.isfile(normalized_path):
        return ''

    path_parts = normalized_path.split(os.sep)
    if 'generated_images' in path_parts:
        # 提取 generated_images 之后的所有路径部分，保留子文件夹结构
        idx = path_parts.index('generated_images')
        relative_parts = path_parts[idx + 1:]
        relative_path = '/'.join(relative_parts)
        return f"/api/static/generated_images/{relative_path}"

    if 'edit_folders' in path_parts:
        edit_root = f"{os.sep}edit_folders{os.sep}"
        if edit_root in normalized_path:
            relative_path = normalized_path.split(edit_root, 1)[1].replace(os.sep, '/')
            return f"/api/static/edit_images/{relative_path}"

    return ''


def _find_local_image_by_title(image_item: ImageItem) -> Optional[str]:
    """
    按已保存标题反查本地图片文件

    功能描述：
        当数据库中的 local_path 或 url 已经过期时，
        直接根据前端保存的标题在对应目录中查找同名图片文件，作为兜底修复来源。

    实现逻辑：
        1. 没有标题时直接返回空
        2. 优先在原 local_path 所在目录中查找
        3. 普通生图回退到 generated_images 目录查找
        4. 编辑产物优先在对应 folder_path 目录查找
        5. 标题命中后返回首个同名图片绝对路径
    """
    title = (getattr(image_item, 'title', None) or '').strip()
    if not title:
        return None

    search_dirs = []
    local_path = (getattr(image_item, 'local_path', None) or '').strip()
    if local_path:
        parent_dir = os.path.dirname(os.path.normpath(local_path))
        if parent_dir and os.path.isdir(parent_dir):
            search_dirs.append(parent_dir)

    image_type = getattr(image_item, 'image_type', 'generation') or 'generation'
    folder_path = (getattr(image_item, 'folder_path', None) or '').strip()
    if image_type == 'edit' and folder_path:
        edit_folder_dir = os.path.join(EDIT_FOLDERS_DIR, folder_path)
        if os.path.isdir(edit_folder_dir) and edit_folder_dir not in search_dirs:
            search_dirs.append(edit_folder_dir)

    if image_type != 'edit' and os.path.isdir(GENERATED_IMAGES_DIR):
        search_dirs.append(GENERATED_IMAGES_DIR)

    preferred_extension = os.path.splitext(local_path)[1].lower()
    candidate_filenames = []
    if preferred_extension in SUPPORTED_IMAGE_EXTENSIONS:
        candidate_filenames.append(f"{title}{preferred_extension}")
    for extension in SUPPORTED_IMAGE_EXTENSIONS:
        candidate_filename = f"{title}{extension}"
        if candidate_filename not in candidate_filenames:
            candidate_filenames.append(candidate_filename)

    for search_dir in search_dirs:
        for candidate_filename in candidate_filenames:
            candidate_path = os.path.join(search_dir, candidate_filename)
            if os.path.isfile(candidate_path):
                return candidate_path

        try:
            for entry in os.scandir(search_dir):
                if not entry.is_file():
                    continue
                stem, extension = os.path.splitext(entry.name)
                if stem == title and extension.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                    return entry.path
        except OSError:
            continue

    return None


def repair_image_file_reference(image_item: ImageItem) -> bool:
    """
    修复图片文件引用

    功能描述：
        当图片改名后数据库仍保留旧 local_path 或旧 url 时，
        优先复用真实存在的本地文件；若旧路径失效，则按标题反查同名文件，
        找到后立即将新的 local_path 和 url 回写数据库。

    实现逻辑：
        1. 旧 local_path 存在时直接基于真实文件刷新 url
        2. 旧 local_path 不存在时，按标题在目标目录中反查同名文件
        3. 找到真实文件后同步更新数据库与内存对象
        4. 找不到文件时保持原数据不变，交由上层继续兜底展示
    """
    if not image_item:
        return False

    resolved_local_path = (getattr(image_item, 'local_path', None) or '').strip()
    if not resolved_local_path or not os.path.isfile(resolved_local_path):
        resolved_local_path = _find_local_image_by_title(image_item) or ''

    if not resolved_local_path:
        return False

    resolved_url = build_static_url_from_local_path(resolved_local_path)
    if not resolved_url:
        return False

    updates = {}
    if resolved_local_path != (image_item.local_path or ''):
        updates['local_path'] = resolved_local_path
    if resolved_url != (image_item.url or ''):
        updates['url'] = resolved_url

    if not updates:
        return False

    update_image_by_id(image_item.id, updates)
    image_item.local_path = resolved_local_path
    image_item.url = resolved_url
    return True


def _parse_task_data(task_data: Any) -> Dict[str, Any]:
    """
    解析任务扩展数据

    功能描述：
        将 tasks.data 字段统一解析为字典，供图片列表和轮询结果展示使用

    实现逻辑：
        1. 空值直接返回空字典
        2. 字典直接返回
        3. 字符串尝试按 JSON 解析
        4. 解析失败时兜底返回空字典，避免影响主流程
    """
    if not task_data:
        return {}

    if isinstance(task_data, dict):
        return task_data

    if isinstance(task_data, str):
        try:
            parsed = json.loads(task_data)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    return {}


def _get_row_value(row, key: str, default: Any = None) -> Any:
    """
    安全读取 sqlite3.Row 字段

    功能描述：
        兼容 sqlite3.Row 不支持 dict.get 的行为，统一为可选字段提供安全读取入口。

    实现逻辑：
        1. 先判断目标字段是否存在于查询结果中
        2. 存在时返回原始值
        3. 不存在时返回默认值，避免字段缺失导致接口报错
    """
    return row[key] if key in row.keys() else default


def _row_to_image_item(row) -> ImageItem:
    """
    构建带任务状态的图片对象

    功能描述：
        将图片表和任务表联合查询后的结果转换为前后端共用的图片对象

    实现逻辑：
        1. 读取图片基础字段
        2. 提取任务状态、进度、失败原因和扩展数据
        3. 根据任务状态推导 generating 标记
        4. 将下载失败信息一并挂载，便于前端兜底展示
    """
    task_payload = _parse_task_data(_get_row_value(row, 'task_data'))
    task_status = _get_row_value(row, 'task_status')
    task_fail_reason = _get_row_value(row, 'task_fail_reason')
    task_progress = _get_row_value(row, 'task_progress')

    normalized_task_status = task_status.strip() if isinstance(task_status, str) else task_status

    # 从 size 字段计算宽高比
    # 功能描述：根据图片尺寸字符串（如 "1024x1024"）计算宽高比，供前端展示不同比例的卡片
    # 实现逻辑：解析 "宽x高" 格式的字符串，计算 width/height，处理异常情况返回 None
    raw_size = _get_row_value(row, 'size') or '1024x1024'
    aspect_ratio = None
    if raw_size and isinstance(raw_size, str) and 'x' in raw_size:
        try:
            parts = raw_size.split('x')
            width, height = int(parts[0]), int(parts[1])
            if height > 0:
                aspect_ratio = width / height
        except (ValueError, IndexError):
            pass

    # 从数据库读取 api_source，如果列不存在则返回 None
    # 后续在 serialize_image 中根据 model 名称自动判断
    db_api_source = _get_row_value(row, 'api_source')

    return ImageItem(
        id=row['id'],
        url=row['url'],
        thumbnail=row['thumbnail'],
        prompt=row['prompt'],
        model=row['model'],
        size=raw_size,
        quality=row['quality'],
        created_at=row['created_at'],
        task_id=row['task_id'],
        local_path=row['local_path'],
        thumbnail_path=_get_row_value(row, 'thumbnail_path'),
        title=row['title'],
        updated_at=row['updated_at'],
        status=normalized_task_status,
        progress=task_progress,
        fail_reason=task_fail_reason,
        generating=normalized_task_status in PENDING_TASK_STATUSES,
        download_error=task_payload.get('download_error'),
        parent_id=_get_row_value(row, 'parent_id'),
        folder_path=_get_row_value(row, 'folder_path'),
        image_type=_get_row_value(row, 'image_type', 'generation') or 'generation',
        aspect_ratio=aspect_ratio,
        api_source=db_api_source,
        poster_copy=_get_row_value(row, 'poster_copy', '') or ''
    )

def _ensure_recycle_columns():
    """
    确保回收站相关字段和 api_source 字段存在于 images 表中

    功能描述：
        检查并添加 is_deleted, deleted_at, recycle_path, api_source 字段
        如果字段已存在则不执行任何操作
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(images)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'is_deleted' not in columns:
            cursor.execute('ALTER TABLE images ADD COLUMN is_deleted INTEGER DEFAULT 0')
        if 'deleted_at' not in columns:
            cursor.execute('ALTER TABLE images ADD COLUMN deleted_at TEXT')
        if 'recycle_path' not in columns:
            cursor.execute('ALTER TABLE images ADD COLUMN recycle_path TEXT')
        if 'api_source' not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN api_source TEXT DEFAULT 't8'")
        if 'poster_copy' not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN poster_copy TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def load_images(image_type: Optional[str] = None) -> List[ImageItem]:
    # 确保回收站相关字段存在
    _ensure_recycle_columns()

    conn = get_db_connection()
    cursor = conn.cursor()
    base_query = '''
        SELECT
            images.*,
            tasks.status AS task_status,
            tasks.progress AS task_progress,
            tasks.fail_reason AS task_fail_reason,
            tasks.data AS task_data
        FROM images
        LEFT JOIN tasks ON tasks.id = images.task_id
    '''

    params = []
    if image_type:
        base_query += ' WHERE images.image_type = ? AND images.is_deleted = 0'
        params.append(image_type)
    else:
        base_query += ' WHERE images.is_deleted = 0'

    base_query += ' ORDER BY images.created_at DESC'
    cursor.execute(base_query, params)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_image_item(row) for row in rows]

def save_images(images: List[ImageItem]) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for img in images:
        cursor.execute('''
            INSERT OR REPLACE INTO images (
                id, url, thumbnail, prompt, model, size, quality,
                created_at, task_id, local_path, thumbnail_path, title, updated_at,
                parent_id, folder_path, image_type, poster_copy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            img.id,
            img.url,
            img.thumbnail,
            img.prompt,
            img.model,
            img.size,
            img.quality,
            img.created_at,
            img.task_id,
            img.local_path,
            img.thumbnail_path,
            img.title,
            datetime.now().isoformat(),
            img.parent_id,
            img.folder_path,
            img.image_type,
            img.poster_copy
        ))
    
    conn.commit()
    conn.close()

def add_image(
    url: str,
    thumbnail: str,
    prompt: str,
    model: str,
    size: str,
    quality: str,
    task_id: Optional[str] = None,
    local_path: Optional[str] = None,
    thumbnail_path: Optional[str] = None,
    title: Optional[str] = None,
    parent_id: Optional[str] = None,
    folder_path: Optional[str] = None,
    image_type: str = 'generation',
    api_source: str = 't8',
    poster_copy: str = ''
) -> ImageItem:
    conn = get_db_connection()
    cursor = conn.cursor()

    # 自动根据模型名称判断 api_source（仅在未显式传入或为默认 't8' 时覆盖）
    # openai/* 格式的模型为 fal 接口，gptsapi/* 为 GPTsAPI，其他为 T8。
    if api_source == 't8':
        if model and model.startswith('openai/'):
            api_source = 'fal'
        elif model and model.startswith('gptsapi/'):
            api_source = 'gptsapi'

    if not title and prompt:
        title = prompt[:6]
    
    # 计算 aspect_ratio（宽高比）
    # 用于前端瀑布流布局，根据图片尺寸自适应卡片高度
    aspect_ratio = None
    if size and isinstance(size, str) and 'x' in size:
        try:
            parts = size.split('x')
            if len(parts) == 2:
                width = float(parts[0])
                height = float(parts[1])
                if height > 0:
                    aspect_ratio = width / height
        except (ValueError, ZeroDivisionError):
            pass

    new_image = ImageItem(
        id=str(uuid.uuid4()),
        url=url,
        thumbnail=thumbnail,
        prompt=prompt,
        model=model,
        size=size,
        quality=quality,
        created_at=datetime.now().isoformat(),
        task_id=task_id,
        local_path=local_path,
        thumbnail_path=thumbnail_path,
        title=title,
        updated_at=datetime.now().isoformat(),
        parent_id=parent_id,
        folder_path=folder_path,
        image_type=image_type or 'generation',
        aspect_ratio=aspect_ratio,
        api_source=api_source,
        poster_copy=poster_copy or ''
    )

    cursor.execute('''
        INSERT INTO images (
            id, url, thumbnail, prompt, model, size, quality,
            created_at, task_id, local_path, thumbnail_path, title, updated_at,
            parent_id, folder_path, image_type, aspect_ratio, api_source, poster_copy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        new_image.id,
        new_image.url,
        new_image.thumbnail,
        new_image.prompt,
        new_image.model,
        new_image.size,
        new_image.quality,
        new_image.created_at,
        new_image.task_id,
        new_image.local_path,
        new_image.thumbnail_path,
        new_image.title,
        new_image.updated_at,
        new_image.parent_id,
        new_image.folder_path,
        new_image.image_type,
        new_image.aspect_ratio,
        new_image.api_source,
        new_image.poster_copy
    ))
    
    conn.commit()
    conn.close()
    
    return new_image

def delete_image(image_id: str) -> tuple[bool, Optional[str]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT local_path FROM images WHERE id = ?', (image_id,))
    row = cursor.fetchone()
    local_path = row['local_path'] if row else None
    
    cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted, local_path

def rename_image(image_id: str, new_title: str) -> tuple[bool, Optional[ImageItem], Optional[str]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM images WHERE id = ?', (image_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return False, None, None
    
    new_local_path = None
    if row['local_path'] and os.path.exists(row['local_path']):
        from services.download_service import rename_local_file
        try:
            ext = os.path.splitext(row['local_path'])[1]
            new_filename = f"{new_title}{ext}"
            result = rename_local_file(row['local_path'], new_filename)
            new_local_path = result.get('new_path')
        except Exception as e:
            print(f"[ImageModel] Failed to rename local file: {e}")
            new_local_path = None
    
    update_data = {
        'title': new_title,
        'updated_at': datetime.now().isoformat()
    }
    if new_local_path:
        update_data['local_path'] = new_local_path
        new_url = build_static_url_from_local_path(new_local_path)
        if new_url:
            update_data['url'] = new_url
    
    set_clause = ', '.join(f"{k} = ?" for k in update_data.keys())
    params = list(update_data.values()) + [image_id]
    
    cursor.execute(f'UPDATE images SET {set_clause} WHERE id = ?', params)
    
    cursor.execute('''
        SELECT
            images.*,
            tasks.status AS task_status,
            tasks.progress AS task_progress,
            tasks.fail_reason AS task_fail_reason,
            tasks.data AS task_data
        FROM images
        LEFT JOIN tasks ON tasks.id = images.task_id
        WHERE images.id = ?
    ''', (image_id,))
    updated_row = cursor.fetchone()
    
    conn.commit()
    conn.close()
    
    if updated_row:
        updated_image = _row_to_image_item(updated_row)
        return True, updated_image, new_local_path
    
    return False, None, None

def get_image_by_id(image_id: str) -> Optional[ImageItem]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            images.*,
            tasks.status AS task_status,
            tasks.progress AS task_progress,
            tasks.fail_reason AS task_fail_reason,
            tasks.data AS task_data
        FROM images
        LEFT JOIN tasks ON tasks.id = images.task_id
        WHERE images.id = ?
    ''', (image_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_image_item(row)
    return None

def get_image_by_task_id(task_id: str) -> Optional[ImageItem]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            images.*,
            tasks.status AS task_status,
            tasks.progress AS task_progress,
            tasks.fail_reason AS task_fail_reason,
            tasks.data AS task_data
        FROM images
        LEFT JOIN tasks ON tasks.id = images.task_id
        WHERE images.task_id = ?
    ''', (task_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_image_item(row)
    return None

def update_image(image_item: ImageItem) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE images SET
            url = ?, thumbnail = ?, prompt = ?, model = ?, size = ?, quality = ?,
            task_id = ?, local_path = ?, thumbnail_path = ?, title = ?, updated_at = ?,
            parent_id = ?, folder_path = ?, image_type = ?, poster_copy = ?
        WHERE id = ?
    ''', (
        image_item.url,
        image_item.thumbnail,
        image_item.prompt,
        image_item.model,
        image_item.size,
        image_item.quality,
        image_item.task_id,
        image_item.local_path,
        image_item.thumbnail_path,
        image_item.title,
        datetime.now().isoformat(),
        image_item.parent_id,
        image_item.folder_path,
        image_item.image_type,
        image_item.poster_copy,
        image_item.id
    ))
    
    conn.commit()
    conn.close()

def update_image_by_id(image_id: str, updates: Dict[str, Any]) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates['updated_at'] = datetime.now().isoformat()
    set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
    params = list(updates.values()) + [image_id]
    
    cursor.execute(f'UPDATE images SET {set_clause} WHERE id = ?', params)
    updated = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return updated

def add_task(task_id: str, image_id: str = None, **kwargs):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    data = kwargs.get('data')
    data_json = json.dumps(data, ensure_ascii=False) if data else None
    
    # 获取 api_source，默认为 't8'；历史数据中的 'openai' 仍由读取方兼容。
    # 当使用 fal.ai 创建任务时，由调用方传入 api_source='fal'
    api_source = kwargs.get('api_source', 't8')
    
    cursor.execute('''
        INSERT OR REPLACE INTO tasks (
            id, image_id, platform, status, fail_reason, submit_time,
            start_time, finish_time, progress, data, created_at, updated_at,
            api_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        task_id,
        image_id,
        kwargs.get('platform', ''),
        kwargs.get('status', 'PENDING'),
        kwargs.get('fail_reason', ''),
        kwargs.get('submit_time'),
        kwargs.get('start_time'),
        kwargs.get('finish_time'),
        kwargs.get('progress', ''),
        data_json,
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        api_source
    ))
    
    conn.commit()
    conn.close()

    # 通知 TaskProcessor 有新任务创建，唤醒休眠的后台线程
    from services.task_processor import notify_task_processor
    notify_task_processor()

def get_task(task_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        result = dict(row)
        if result['data']:
            result['data'] = json.loads(result['data'])
        return result
    return None


def update_task(task_id: str, **kwargs) -> bool:
    """
    更新异步任务状态

    功能描述：
        根据 task_id 更新任务表中的状态、进度、失败原因和扩展数据

    实现逻辑：
        1. 仅接收允许更新的任务字段
        2. 对 data 字段进行 JSON 序列化
        3. 自动补充 updated_at
        4. 更新失败时返回 False，避免路由层误判
    """
    allowed_fields = {
        'image_id',
        'platform',
        'status',
        'fail_reason',
        'submit_time',
        'start_time',
        'finish_time',
        'progress',
        'data'
    }

    updates = {}
    for key, value in kwargs.items():
        if key not in allowed_fields:
            continue

        if key == 'data':
            updates[key] = json.dumps(value, ensure_ascii=False) if value is not None else None
        else:
            updates[key] = value

    if not updates:
        return False

    updates['updated_at'] = datetime.now().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    set_clause = ', '.join(f"{field} = ?" for field in updates.keys())
    params = list(updates.values()) + [task_id]
    cursor.execute(f'UPDATE tasks SET {set_clause} WHERE id = ?', params)
    updated = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return updated


def add_edit_relation(image_id: str, parent_id: Optional[str], root_id: str, depth: int = 0) -> bool:
    """
    添加编辑关系记录

    功能描述：
        记录图片之间的编辑关系，便于构建编辑历史树

    实现逻辑：
        1. 生成唯一ID
        2. 插入 edit_relations 表
        3. 失败时返回 False
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO edit_relations (id, image_id, parent_id, root_id, depth, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            image_id,
            parent_id,
            root_id,
            depth,
            datetime.now().isoformat()
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"[ImageModel] Failed to add edit relation: {e}")
        return False
    finally:
        conn.close()


def get_image_edits(image_id: str) -> List[Dict[str, Any]]:
    """
    获取图片的完整编辑历史树

    功能描述：
        查询某张图片作为根节点的所有编辑历史

    实现逻辑：
        1. 先查询该图片的 root_id（如果自己是根，则用自己）
        2. 查询所有关联的 edit_relations
        3. 关联 images 表获取完整信息
        4. 按 depth 和 created_at 排序
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 先确定 root_id
        cursor.execute('''
            SELECT root_id FROM edit_relations WHERE image_id = ?
        ''', (image_id,))
        row = cursor.fetchone()
        root_id = row['root_id'] if row else image_id

        # 查询完整的编辑树
        cursor.execute('''
            SELECT 
                images.*,
                er.parent_id,
                er.depth,
                tasks.status AS task_status,
                tasks.progress AS task_progress,
                tasks.fail_reason AS task_fail_reason,
                tasks.data AS task_data
            FROM edit_relations er
            JOIN images ON images.id = er.image_id
            LEFT JOIN tasks ON tasks.id = images.task_id
            WHERE er.root_id = ?
            ORDER BY er.depth ASC, images.created_at ASC
        ''', (root_id,))

        rows = cursor.fetchall()
        result = []
        for row in rows:
            image_item = _row_to_image_item(row)
            result.append({
                **image_item.__dict__,
                'parent_id': row['parent_id'],
                'depth': row['depth']
            })
        return result
    except Exception as e:
        print(f"[ImageModel] Failed to get image edits: {e}")
        return []
    finally:
        conn.close()


def get_edit_relation_by_image_id(image_id: str) -> Optional[Dict[str, Any]]:
    """
    获取单张图片的编辑关系

    功能描述：
        查询某张图片的父节点和根节点信息
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT * FROM edit_relations WHERE image_id = ?
        ''', (image_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"[ImageModel] Failed to get edit relation: {e}")
        return None
    finally:
        conn.close()


def update_image_folder_path(image_id: str, new_folder_path: str) -> bool:
    """
    更新图片的文件夹路径

    功能描述：
        级联更新图片及其所有子图片的文件夹路径

    实现逻辑：
        1. 更新当前图片的 folder_path
        2. 查询所有子图片
        3. 递归更新子图片的 folder_path（替换前缀）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 获取当前图片的 folder_path
        cursor.execute('SELECT folder_path FROM images WHERE id = ?', (image_id,))
        row = cursor.fetchone()
        old_path = row['folder_path'] if row else None

        if not old_path:
            # 如果没有旧路径，直接更新当前图片
            cursor.execute('''
                UPDATE images SET folder_path = ?, updated_at = ? WHERE id = ?
            ''', (new_folder_path, datetime.now().isoformat(), image_id))
            conn.commit()
            return True

        # 更新当前图片
        cursor.execute('''
            UPDATE images SET folder_path = ?, updated_at = ? WHERE id = ?
        ''', (new_folder_path, datetime.now().isoformat(), image_id))

        # 查询所有以 old_path 为前缀的子图片
        cursor.execute('''
            SELECT id, folder_path FROM images 
            WHERE folder_path LIKE ? AND id != ?
        ''', (f"{old_path}%", image_id))

        child_rows = cursor.fetchall()
        for child_row in child_rows:
            child_id = child_row['id']
            child_old_path = child_row['folder_path']
            # 替换前缀
            child_new_path = child_old_path.replace(old_path, new_folder_path, 1)
            cursor.execute('''
                UPDATE images SET folder_path = ?, updated_at = ? WHERE id = ?
            ''', (child_new_path, datetime.now().isoformat(), child_id))

        conn.commit()
        return True
    except Exception as e:
        print(f"[ImageModel] Failed to update folder path: {e}")
        return False
    finally:
        conn.close()
