# 未分配文件夹服务
#
# 功能描述：
#   提供「未分配」虚拟文件夹的图片列表
#   「未分配」 = 物理上位于 generated_images 根目录下的所有图片文件
#                （不属于任何子文件夹，即原图的"未分类"集合）
#   区别于 folders 表里的真实文件夹，未分配不需要在数据库中创建记录
#
# 实现逻辑：
#   1. 扫描 generated_images 根目录（不递归进入子目录）下的所有图片文件
#   2. 构造静态 URL：/api/static/generated_images/<filename>
#   3. 数据库 images 表按 url 字段匹配，并过滤掉 folder_id 非空的记录
#      （物理位置在根目录、但已被标记归类的图不展示在"未分配"中）
#   4. 数据库没匹配到的孤儿文件构造虚拟图片对象，保证不遗漏
#   5. 合并后按 created_at 降序返回
#
# 边界场景：
#   - generated_images 目录不存在：返回空列表，不抛错
#   - 文件无扩展名或非图片扩展名：跳过
#   - 数据库查询失败：回退到仅返回虚拟记录
#
# 注意：
#   generated_thumbnails 只是缩略图目录，与"未分配"视图无关，
#   本服务只扫描 generated_images 根目录。

import hashlib
import os
from datetime import datetime
from typing import Dict, Any, List
from services.auth_service import current_creator, current_user_is_admin

# 项目根目录定位
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
PROJECT_ROOT_DIR = os.path.dirname(BACKEND_DIR)

# 未分配的物理扫描目录（图片原件根目录）
GENERATED_IMAGES_DIR = os.path.join(PROJECT_ROOT_DIR, 'generated_images')

# 静态 URL 前缀
IMAGES_STATIC_PREFIX = '/api/static/generated_images/'

# 未分配虚拟文件夹的固定标识
UNASSIGNED_FOLDER_ID = 'unassigned'
UNASSIGNED_FOLDER_NAME = '未分配'

# 支持的图片扩展名（小写）
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def _build_virtual_id(filename: str) -> str:
    """
    为虚拟记录构造稳定 ID

    功能描述：
        对未匹配到数据库的孤儿图片构造唯一且稳定的 ID，
        保证同一文件每次扫描得到相同 ID，方便前端做去重和选中状态管理

    实现逻辑：
        1. 取文件名（不含扩展名）作为基础
        2. 加上文件名的 SHA1 前 12 位作为唯一后缀
        3. 最终 ID 形如：unassigned_<name>_<hash>
    """
    base, _ = os.path.splitext(filename)
    safe_base = ''.join(ch if (ch.isalnum() or ch in '_-') else '_' for ch in base)[:40]
    digest = hashlib.sha1(filename.encode('utf-8')).hexdigest()[:12]
    return f"unassigned_{safe_base}_{digest}"


def _build_virtual_image(filename: str, abs_path: str, created_at: str) -> Dict[str, Any]:
    """
    构造一个虚拟图片对象

    功能描述：
        当扫描到的图片在数据库中找不到对应记录时，
        使用文件信息构造一条占位记录，保证前端能看到这张图

    实现逻辑：
        1. 构造静态 URL 与对应的虚拟 ID
        2. prompt/creator/model 等元数据留空，标记为「未入库」
        3. image_type 设为 generation，与前端主列表保持一致
        4. folder_id 留空，title 用文件名（去后缀）方便识别
    """
    virtual_id = _build_virtual_id(filename)
    url = f"{IMAGES_STATIC_PREFIX}{filename}"
    title, _ = os.path.splitext(filename)
    return {
        'id': virtual_id,
        'url': url,
        'thumbnail': url,
        'prompt': '',
        'model': '',
        'size': '',
        'quality': '',
        'aspect_ratio': None,
        'resolution': '',
        'output_format': '',
        'local_url': abs_path,
        'preview_url': url,
        'response_url': '',
        'request_data': {},
        'response_data': {},
        'status': 'success',
        'error_message': None,
        'extra': {'unassigned_orphan': True},
        'created_at': created_at,
        'updated_at': created_at,
        'task_id': None,
        'title': title,
        'creator': '',
        'api_source': '',
        'parent_id': None,
        'folder_path': '',
        'folder_id': None,
        'image_type': 'generation',
        'poster_copy': '',
        'local_path': abs_path,
        'thumbnail_path': abs_path,
        'is_virtual': True
    }


def list_unassigned_files() -> List[str]:
    """
    列出 generated_images 根目录下的所有图片文件名

    功能描述：
        扫描物理目录，拿到所有「属于未分配」的原图文件名

    实现逻辑：
        1. 目录不存在则返回空列表
        2. 仅返回文件（不递归进入子目录）
        3. 按扩展名过滤图片文件

    返回：
        文件名列表（含扩展名）
    """
    if not os.path.isdir(GENERATED_IMAGES_DIR):
        return []

    result: List[str] = []
    try:
        for entry in os.listdir(GENERATED_IMAGES_DIR):
            abs_path = os.path.join(GENERATED_IMAGES_DIR, entry)
            if not os.path.isfile(abs_path):
                continue
            _, ext = os.path.splitext(entry)
            if ext.lower() not in IMAGE_EXTENSIONS:
                continue
            result.append(entry)
    except OSError as exc:
        print(f"[UnassignedFolderService] 扫描 generated_images 目录失败: {exc}")
        return []

    return result


def get_database_records_for_images(filenames: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    在数据库中按 url 查找匹配的记录

    功能描述：
        给定一组原图文件名，批量查询 images 表中 url 字段匹配的记录
        用于「未分配」视图关联已有元数据（prompt、creator、model 等）

    实现逻辑：
        1. 拼接所有 URL 一次性 WHERE IN 查询
        2. 用 url 作为 key 索引返回
        3. 仅返回 folder_id 为空的记录：已归类到真实文件夹的图不属于「未分配」，
           否则会和"瓦努阿图"等文件夹视图出现重复
        4. 查询失败时返回空 dict，不影响主流程
    """
    if not filenames:
        return {}

    try:
        from models.database import get_db_connection
    except ImportError:
        return {}

    urls = [f"{IMAGES_STATIC_PREFIX}{name}" for name in filenames]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(urls))
        cursor.execute(
            f'''
            SELECT
                id, prompt, model, size, quality, aspect_ratio,
                resolution, output_format, local_url, preview_url,
                response_url, request_data, response_data, status,
                error_message, extra, created_at, updated_at,
                url, thumbnail, local_path, thumbnail_path, image_type,
                task_id, title, creator, api_source,
                parent_id, folder_path, poster_copy, folder_id
            FROM images
            WHERE url IN ({placeholders})
              AND folder_id IS NULL
              AND (is_deleted IS NULL OR is_deleted = 0)
            ''',
            urls
        )
        rows = cursor.fetchall()
        conn.close()
    except Exception as exc:
        print(f"[UnassignedFolderService] 数据库查询失败: {exc}")
        return {}

    import json
    matched: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        url = row['url'] or ''
        matched[url] = {
            'id': row['id'],
            'prompt': row['prompt'] or '',
            'model': row['model'] or '',
            'size': row['size'] or '',
            'quality': row['quality'] or '',
            'aspect_ratio': row['aspect_ratio'] or None,
            'resolution': row['resolution'] or '',
            'output_format': row['output_format'] or '',
            'local_url': row['local_url'] or '',
            'preview_url': row['preview_url'] or '',
            'response_url': row['response_url'] or '',
            'request_data': json.loads(row['request_data']) if row['request_data'] else {},
            'response_data': json.loads(row['response_data']) if row['response_data'] else {},
            'status': row['status'] or 'success',
            'error_message': row['error_message'],
            'extra': json.loads(row['extra']) if row['extra'] else {},
            'created_at': row['created_at'] or '',
            'updated_at': row['updated_at'] or '',
            'url': row['url'] or '',
            'thumbnail': row['thumbnail'] or '',
            'local_path': row['local_path'] or '',
            'thumbnail_path': row['thumbnail_path'] or '',
            'image_type': row['image_type'] or 'generation',
            'task_id': row['task_id'],
            'title': row['title'] or '',
            'creator': row['creator'] or '',
            'api_source': row['api_source'] or '',
            'parent_id': row['parent_id'],
            'folder_path': row['folder_path'] or '',
            'poster_copy': row['poster_copy'] or '',
            'folder_id': row['folder_id'],
            'is_virtual': False
        }
    return matched


def list_unassigned_images() -> List[Dict[str, Any]]:
    """
    列出「未分配」文件夹下的所有图片

    功能描述：
        返回 generated_images 根目录下所有图片的元数据
        优先用数据库记录，缺失的孤儿文件用虚拟对象补全

    实现逻辑：
        1. 扫描 generated_images 根目录拿到文件名集合
        2. 一次性数据库批量匹配
        3. 对未匹配的孤儿文件构造虚拟记录
        4. 按 created_at 降序返回（最新生成在前）

    返回：
        图片对象列表，字段结构与 serialize_image 输出一致
    """
    filenames = list_unassigned_files()
    if not filenames:
        return []

    matched = get_database_records_for_images(filenames)

    results: List[Dict[str, Any]] = []
    for filename in filenames:
        url = f"{IMAGES_STATIC_PREFIX}{filename}"
        abs_path = os.path.join(GENERATED_IMAGES_DIR, filename)
        try:
            mtime_ts = os.path.getmtime(abs_path)
            created_at = datetime.fromtimestamp(mtime_ts).isoformat()
        except OSError:
            created_at = datetime.now().isoformat()

        record = matched.get(url)
        if record:
            if not current_user_is_admin() and (record.get('creator') or '') != current_creator():
                continue
            # 数据库已有记录：把 local_path 同步成当前物理路径
            #   兜底：数据库可能存的是旧路径，物理文件可能已被替换
            if not record.get('local_path') or not os.path.isfile(record.get('local_path', '')):
                record['local_path'] = abs_path
            results.append(record)
        else:
            if not current_user_is_admin():
                continue
            results.append(_build_virtual_image(filename, abs_path, created_at))

    # 按 created_at 降序，空值排到最后
    results.sort(
        key=lambda item: item.get('created_at') or '',
        reverse=True
    )
    return results


def get_unassigned_folder_meta() -> Dict[str, Any]:
    """
    返回「未分配」文件夹的元数据，供前端文件夹下拉使用

    功能描述：
        与真实文件夹结构对齐，输出 id/name/count 字段
        count 与 list_unassigned_images 实际返回数量保持一致，
        避免前端下拉里显示的数字比实际加载的列表多

    实现逻辑：
        1. 调用 list_unassigned_images() 拿真实数据
        2. count 取结果数组的长度
        3. 失败时回退为 0，不阻塞接口

    返回：
        {
            'id': 'unassigned',
            'name': '未分配',
            'image_count': 数字,
            'is_virtual': True,
            'extra': {}
        }
    """
    try:
        # 与实际下拉项保持一致：先取 list 长度，避免数字与列表对不上
        #   兜底：list_unassigned_images 异常时返回 0，不抛错
        image_count = len(list_unassigned_images())
    except Exception as exc:
        print(f"[UnassignedFolderService] 统计未分配数量失败: {exc}")
        image_count = 0

    return {
        'id': UNASSIGNED_FOLDER_ID,
        'name': UNASSIGNED_FOLDER_NAME,
        'image_count': image_count,
        'is_virtual': True,
        'extra': {}
    }
