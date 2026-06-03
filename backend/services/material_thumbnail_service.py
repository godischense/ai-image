"""
素材缩略图服务

功能描述：
    为素材库中的图片生成缩略图，存入项目根目录下的 素材缩略图 文件夹。
    复用 ThumbnailService，仅替换存储目录和 URL 前缀。

实现逻辑：
    1. 单例模式获取 ThumbnailService 实例，storage_dir 指向 素材缩略图
    2. create_material_thumbnail 调用 generate_from_local 生成缩略图
    3. 将默认 URL 前缀替换为素材缩略图专用前缀

异常处理：
    - 缩略图生成失败时返回 success=False
    - 文件系统异常由 ThumbnailService 内部处理
"""

import os
from services.thumbnail_service import ThumbnailService

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

MATERIAL_THUMBNAIL_DIR = os.path.join(PROJECT_ROOT, '素材缩略图')
THUMBNAIL_URL_PREFIX = '/api/static/material_thumbnails'

_thumbnail_service_instance = None


def get_material_thumbnail_service():
    """
    获取素材缩略图服务单例

    功能描述：
        返回配置好 material_thumbnails 目录的 ThumbnailService 实例
    """
    global _thumbnail_service_instance
    if _thumbnail_service_instance is None:
        _thumbnail_service_instance = ThumbnailService(
            storage_dir=MATERIAL_THUMBNAIL_DIR
        )
    return _thumbnail_service_instance


def create_material_thumbnail(source_path: str):
    """
    为素材原图创建缩略图

    功能描述：
        调用 ThumbnailService.generate_from_local 生成缩略图，
        并将返回的 URL 前缀替换为素材缩略图专用前缀

    参数：
        source_path: 素材原图的本地完整路径

    返回：
        {
            'success': 是否成功,
            'thumbnail_path': 缩略图本地路径,
            'thumbnail_url': 前端可访问的缩略图 URL,
            'filename': 缩略图文件名
        }
    """
    try:
        service = get_material_thumbnail_service()
        result = service.generate_from_local(source_path)

        if result.get('success') and result.get('thumbnail_url'):
            filename = result.get('filename', '')
            result['thumbnail_url'] = f'{THUMBNAIL_URL_PREFIX}/{filename}'

        return result
    except Exception as e:
        print(f"[MaterialThumbnail] Failed to create thumbnail: {e}")
        return {
            'success': False,
            'error': str(e)
        }
