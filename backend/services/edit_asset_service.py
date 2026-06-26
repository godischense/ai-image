"""
编辑图片资产服务模块

功能描述：
    负责编辑结果原图与编辑页缩略图的落盘、路径组织和静态访问 URL 生成。

实现逻辑：
    1. 使用 edit_folders 作为编辑原图目录根节点
    2. 使用 edit_thumbnails 作为编辑页缩略图目录根节点
    3. 先将编辑结果原图下载到指定编辑目录
    4. 再基于落盘原图生成编辑页专用缩略图
    5. 返回前端可直接访问的原图 URL、缩略图 URL、本地路径和错误信息

异常处理：
    - 文件夹不存在时自动创建
    - 原图下载失败时返回明确错误，允许上层决定是否保留远程 URL 兜底
    - 缩略图生成失败时不阻断原图落盘，但会返回错误供上层记录
"""

import os
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from services.download_service import download_image_to_local
from services.folder_service import (
    EDIT_FOLDERS_DIR,
    PROJECT_ROOT_DIR,
    ensure_edit_folders_dir,
    get_folder_absolute_path,
    sanitize_folder_name
)
from services.thumbnail_service import create_thumbnail_from_local
from services.creator_storage import creator_storage_dir, creator_subdir


EDIT_THUMBNAILS_DIR = os.path.join(PROJECT_ROOT_DIR, 'edit_thumbnails')
EDIT_IMAGE_STATIC_PREFIX = '/api/static/edit_images/'
EDIT_THUMBNAIL_STATIC_PREFIX = '/api/static/edit_thumbnails/'


def ensure_edit_thumbnails_dir() -> None:
    """
    确保编辑缩略图根目录存在

    功能描述：
        编辑页缩略图采用独立目录，首次使用时自动创建。
    """
    os.makedirs(EDIT_THUMBNAILS_DIR, exist_ok=True)


def _to_posix_path(relative_path: str) -> str:
    return relative_path.replace('\\', '/')


def build_edit_image_url(relative_path: str) -> str:
    """
    构建编辑原图静态访问 URL
    """
    normalized_path = _to_posix_path(relative_path or '').lstrip('/')
    return f"{EDIT_IMAGE_STATIC_PREFIX}{normalized_path}" if normalized_path else ''


def build_edit_thumbnail_url(relative_path: str) -> str:
    """
    构建编辑缩略图静态访问 URL
    """
    normalized_path = _to_posix_path(relative_path or '').lstrip('/')
    return f"{EDIT_THUMBNAIL_STATIC_PREFIX}{normalized_path}" if normalized_path else ''


def get_edit_thumbnail_absolute_path(folder_path: str, filename: str) -> str:
    """
    获取编辑缩略图绝对路径
    """
    ensure_edit_thumbnails_dir()
    if folder_path:
        return os.path.join(EDIT_THUMBNAILS_DIR, folder_path, filename)
    return os.path.join(EDIT_THUMBNAILS_DIR, filename)


def create_edit_thumbnail_from_local(local_image_path: str, folder_path: str) -> Dict[str, Any]:
    """
    基于编辑原图生成编辑页缩略图

    功能描述：
        先在普通缩略图目录生成临时文件，再移动到 edit_thumbnails 对应目录，确保复用现有缩略图逻辑。
    """
    ensure_edit_thumbnails_dir()

    temp_thumbnail_result = create_thumbnail_from_local(local_image_path)
    temp_thumbnail_path = temp_thumbnail_result.get('thumbnail_path')
    thumbnail_filename = temp_thumbnail_result.get('filename')

    if not temp_thumbnail_path or not thumbnail_filename:
        raise RuntimeError('编辑缩略图生成失败：未返回有效文件信息')

    target_thumbnail_path = get_edit_thumbnail_absolute_path(folder_path, thumbnail_filename)
    target_thumbnail_dir = os.path.dirname(target_thumbnail_path)
    os.makedirs(target_thumbnail_dir, exist_ok=True)

    shutil.move(temp_thumbnail_path, target_thumbnail_path)

    relative_path = os.path.relpath(target_thumbnail_path, EDIT_THUMBNAILS_DIR)
    return {
        'thumbnail_path': target_thumbnail_path,
        'thumbnail_relative_path': relative_path,
        'thumbnail_url': build_edit_thumbnail_url(relative_path),
        'filename': thumbnail_filename
    }


def prepare_edit_image_assets(image_url: str, folder_path: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    准备编辑结果原图与缩略图

    功能描述：
        将编辑结果下载到 edit_folders 指定目录，并生成 edit_thumbnails 对应缩略图。
    """
    ensure_edit_folders_dir()
    ensure_edit_thumbnails_dir()

    if not folder_path:
        raise ValueError('编辑图片缺少 folder_path，无法准备编辑资产')

    absolute_folder = get_folder_absolute_path(folder_path)
    os.makedirs(absolute_folder, exist_ok=True)

    # 确保始终生成目标路径，即使没有指定 filename
    if not filename:
        # 从URL提取扩展名，或使用默认名称
        ext = os.path.splitext(image_url.split('?')[0])[1] or '.png'
        filename = f"edited_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

    download_result = download_image_to_local(
        image_url,
        os.path.join(absolute_folder, filename)
    )

    local_path = download_result.get('local_path')
    if not local_path:
        raise RuntimeError('编辑原图下载成功但未返回 local_path')

    image_relative_path = os.path.relpath(local_path, EDIT_FOLDERS_DIR)
    image_url_value = build_edit_image_url(image_relative_path)

    thumbnail_url = ''
    thumbnail_path = None
    thumbnail_error = ''

    try:
        thumbnail_result = create_edit_thumbnail_from_local(local_path, folder_path)
        thumbnail_url = thumbnail_result.get('thumbnail_url', '')
        thumbnail_path = thumbnail_result.get('thumbnail_path')
    except (ValueError, RuntimeError) as err:
        thumbnail_error = str(err)

    return {
        'url': image_url_value,
        'display_url': image_url_value,
        'local_path': local_path,
        'image_relative_path': image_relative_path,
        'thumbnail': thumbnail_url,
        'thumbnail_path': thumbnail_path,
        'error': thumbnail_error
    }


# 将编辑结果直接保存到 edit_folders 根目录
# 替代旧的 create_edit_folder 子文件夹逻辑，直接将编辑结果原图和缩略图
# 保存在 edit_folders 和 edit_thumbnails 根目录下
def save_edit_result_directly(image_url: str, prompt: str = '', size: str = None, creator: str = '') -> Dict[str, Any]:
    """
    将编辑结果直接保存到 edit_folders 根目录

    功能描述：
        替代旧的 create_edit_folder 子文件夹逻辑，直接将编辑结果原图和缩略图
        保存在 edit_folders 和 edit_thumbnails 根目录下。

    实现逻辑：
        1. 确保目录存在
        2. 生成唯一文件名：edit_ + 清理后的prompt前20字 + 时间戳 + 随机串
        3. 下载原图到 edit_folders
        4. 生成缩略图到 edit_thumbnails
        5. 返回本地URL和缩略图URL

    异常处理：
        - 原图下载失败时返回错误信息，不继续执行缩略图生成
        - 缩略图生成失败时不阻断原图保存，返回空缩略图URL和错误信息
    """
    ensure_edit_folders_dir()
    ensure_edit_thumbnails_dir()

    creator_dir = creator_subdir(creator)
    target_edit_dir = creator_storage_dir(EDIT_FOLDERS_DIR, creator)
    os.makedirs(target_edit_dir, exist_ok=True)

    safe_prompt = sanitize_folder_name(prompt or 'edited')[:20]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = str(uuid.uuid4())[:8]
    filename = f"edit_{safe_prompt}_{timestamp}_{random_suffix}.png"

    local_path = os.path.join(target_edit_dir, filename)

    download_result = download_image_to_local(image_url, local_path)

    if not download_result.get('success') or not download_result.get('local_path'):
        return {
            'success': False,
            'error': download_result.get('error', '原图下载失败')
        }

    local_path = download_result['local_path']
    image_relative_path = os.path.relpath(local_path, EDIT_FOLDERS_DIR)
    image_url_value = build_edit_image_url(image_relative_path)

    thumbnail_url = ''
    thumbnail_path = None
    thumbnail_error = ''

    try:
        thumbnail_result = create_edit_thumbnail_from_local(local_path, creator_dir)
        thumbnail_url = thumbnail_result.get('thumbnail_url', '')
        thumbnail_path = thumbnail_result.get('thumbnail_path')
    except (ValueError, RuntimeError) as err:
        thumbnail_error = str(err)

    return {
        'success': True,
        'url': image_url_value,
        'display_url': image_url_value,
        'local_path': local_path,
        'image_relative_path': image_relative_path,
        'thumbnail': thumbnail_url,
        'thumbnail_path': thumbnail_path,
        'error': thumbnail_error
    }
