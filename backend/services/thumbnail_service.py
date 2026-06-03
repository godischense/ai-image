"""
缩略图生成服务模块

功能描述：
    为本地原图生成列表展示用的缩略图，缩略图文件独立存放并提供可访问 URL。

实现逻辑：
    1. 初始化时定位项目根目录下的 generated_thumbnails 文件夹
    2. 如果缩略图目录不存在则自动创建
    3. 接收本地原图路径，读取并按限制尺寸生成缩略图
    4. 返回缩略图本地路径和前端可访问 URL

异常处理：
    - 原图不存在：抛出 ValueError
    - 图片无法读取或写入失败：抛出 RuntimeError
"""

import hashlib
import os
from typing import Optional, Dict, Any
from PIL import Image, ImageOps


class ThumbnailService:
    """缩略图服务类"""

    def __init__(self, storage_dir: str = None, max_size: tuple[int, int] = (512, 512)):
        """
        初始化缩略图服务

        参数：
            storage_dir: 缩略图存放目录，默认项目根目录下的 generated_thumbnails
            max_size: 缩略图最长边限制，默认 512x512
        """
        if storage_dir is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            storage_dir = os.path.join(project_root, 'generated_thumbnails')

        self.storage_dir = storage_dir
        self.max_size = max_size
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """
        确保存储目录存在

        功能描述：
            当缩略图目录不存在时自动创建，避免首次生成时因目录缺失失败。

        异常处理：
            - 创建目录失败时抛出 RuntimeError，避免上层误以为缩略图已生成
        """
        try:
            if not os.path.exists(self.storage_dir):
                os.makedirs(self.storage_dir, exist_ok=True)
                print(f"[ThumbnailService] Created thumbnail directory: {self.storage_dir}")
        except OSError as err:
            error_message = f"Failed to create thumbnail directory {self.storage_dir}: {err}"
            print(f"[ThumbnailService] Error: {error_message}")
            raise RuntimeError(error_message)

    def _build_thumbnail_signature(self, source_path: str) -> str:
        """
        生成缩略图签名

        功能描述：
            基于原图绝对路径、文件大小和修改时间生成稳定签名，保证同一原图重复生成时复用同一缩略图。

        实现逻辑：
            1. 读取原图绝对路径
            2. 拼接文件大小与纳秒级修改时间
            3. 使用哈希生成固定长度签名

        异常处理：
            - 文件状态读取失败时抛出 RuntimeError，避免继续生成无法稳定复用的缩略图
        """
        try:
            normalized_source_path = os.path.abspath(source_path)
            file_state = os.stat(normalized_source_path)
            signature_source = (
                f"{normalized_source_path}|{file_state.st_size}|{file_state.st_mtime_ns}"
            )
            return hashlib.md5(signature_source.encode('utf-8')).hexdigest()[:12]
        except OSError as err:
            error_message = f"Failed to inspect source image for thumbnail signature: {err}"
            print(f"[ThumbnailService] Error: {error_message}")
            raise RuntimeError(error_message)

    def _build_thumbnail_filename(self, source_path: str, source_extension: str) -> str:
        """
        生成缩略图文件名

        功能描述：
            基于原图文件名和稳定签名生成可复用的缩略图名称。

        实现逻辑：
            1. 读取原图基础文件名
            2. 追加 thumb 前缀与稳定签名
            3. 使用可稳定输出的目标扩展名
        """
        source_name = os.path.splitext(os.path.basename(source_path))[0]
        stable_signature = self._build_thumbnail_signature(source_path)
        return f"{source_name}_thumb_{stable_signature}.{source_extension}"

    def _cleanup_duplicate_thumbnails(self, source_path: str, current_filename: str) -> None:
        """
        清理同一原图的历史重复缩略图

        功能描述：
            在当前缩略图已可用时，删除同一原图旧的随机命名缩略图，避免缩略图目录持续堆积重复文件。

        实现逻辑：
            1. 按原图基础名称匹配同前缀缩略图
            2. 跳过当前正在使用的缩略图
            3. 尝试删除其他历史文件，失败仅记录日志不影响主流程
        """
        source_name = os.path.splitext(os.path.basename(source_path))[0]
        expected_prefix = f"{source_name}_thumb_"

        try:
            for entry in os.scandir(self.storage_dir):
                if not entry.is_file():
                    continue

                if not entry.name.startswith(expected_prefix):
                    continue

                if entry.name == current_filename:
                    continue

                try:
                    os.remove(entry.path)
                    print(f"[ThumbnailService] Removed duplicate thumbnail: {entry.path}")
                except OSError as err:
                    print(
                        f"[ThumbnailService] Warning: Failed to remove duplicate thumbnail "
                        f"{entry.path}: {err}"
                    )
        except OSError as err:
            print(f"[ThumbnailService] Warning: Failed to scan thumbnail directory: {err}")

    def _resolve_save_format(self, image_mode: str) -> tuple[str, str]:
        """
        解析缩略图保存格式

        功能描述：
            根据图片模式选择更稳妥的缩略图输出格式，避免透明通道丢失导致报错。

        实现逻辑：
            1. 透明图输出 PNG
            2. 非透明图输出 JPEG
        """
        if image_mode in ('RGBA', 'LA') or image_mode.endswith('A'):
            return 'png', 'PNG'
        return 'jpg', 'JPEG'

    def generate_from_local(self, source_path: str) -> Dict[str, Any]:
        """
        从本地原图生成缩略图

        功能描述：
            对本地原图进行缩放并保存为独立缩略图文件，供列表页使用。

        参数：
            source_path: 原图本地完整路径

        返回：
            - success: 是否生成成功
            - thumbnail_path: 缩略图本地完整路径
            - thumbnail_url: 缩略图可访问 URL
            - filename: 缩略图文件名

        异常处理：
            - 原图不存在时抛出 ValueError
            - 打开或保存失败时抛出 RuntimeError
        """
        if not source_path or not isinstance(source_path, str):
            raise ValueError("Invalid source path: path cannot be empty")

        source_path = source_path.strip()
        if not os.path.exists(source_path):
            raise ValueError(f"Source image does not exist: {source_path}")

        self._ensure_directory()

        try:
            with Image.open(source_path) as source_image:
                normalized_image = ImageOps.exif_transpose(source_image)
                extension, save_format = self._resolve_save_format(normalized_image.mode)
                thumbnail_filename = self._build_thumbnail_filename(source_path, extension)
                thumbnail_path = os.path.join(self.storage_dir, thumbnail_filename)
                thumbnail_url = f"/api/static/generated_thumbnails/{thumbnail_filename}"

                if os.path.exists(thumbnail_path):
                    self._cleanup_duplicate_thumbnails(source_path, thumbnail_filename)
                    return {
                        'success': True,
                        'thumbnail_path': thumbnail_path,
                        'thumbnail_url': thumbnail_url,
                        'filename': thumbnail_filename
                    }

                preview_image = normalized_image.copy()
                preview_image.thumbnail(self.max_size, Image.Resampling.LANCZOS)

                save_kwargs: Dict[str, Any] = {'optimize': True}
                if save_format == 'JPEG':
                    preview_image = preview_image.convert('RGB')
                    save_kwargs['quality'] = 85

                preview_image.save(thumbnail_path, format=save_format, **save_kwargs)

            self._cleanup_duplicate_thumbnails(source_path, thumbnail_filename)
            return {
                'success': True,
                'thumbnail_path': thumbnail_path,
                'thumbnail_url': thumbnail_url,
                'filename': thumbnail_filename
            }
        except ValueError:
            raise
        except Exception as err:
            error_message = f"Failed to generate thumbnail for {source_path}: {err}"
            print(f"[ThumbnailService] Error: {error_message}")
            raise RuntimeError(error_message)


_thumbnail_service_instance: Optional[ThumbnailService] = None


def get_thumbnail_service() -> ThumbnailService:
    """获取全局缩略图服务实例"""
    global _thumbnail_service_instance
    if _thumbnail_service_instance is None:
        _thumbnail_service_instance = ThumbnailService()
    return _thumbnail_service_instance


def create_thumbnail_from_local(source_path: str) -> Dict[str, Any]:
    """
    便捷函数：从本地原图生成缩略图

    功能描述：
        用于路由层快速创建缩略图，避免直接操作服务实例。
    """
    service = get_thumbnail_service()
    return service.generate_from_local(source_path)
