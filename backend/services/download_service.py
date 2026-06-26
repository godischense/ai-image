"""
图片下载服务模块

功能描述：
    提供图片自动下载到本地文件夹的功能，支持创建目录、下载重试、文件名生成等

实现逻辑：
    1. 接收远程图片 URL
    2. 检查并创建本地存储目录（如果不存在）
    3. 生成唯一的本地文件名（包含时间戳和UUID）
    4. 下载远程图片内容（支持重试和SSL错误处理）
    5. 保存到本地目录
    6. 返回本地文件路径

异常处理：
    - 网络请求失败：记录错误并抛出异常
    - 文件写入失败：清理已创建的文件并抛出异常
    - URL 无效：抛出 ValueError 异常
    - SSL 错误：尝试跳过SSL验证重试
"""

import os
import requests
import uuid
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
import urllib3
from services.creator_storage import creator_storage_dir, static_url_for_path


class DownloadService:
    """图片下载服务类"""

    def __init__(self):
        """
        初始化下载服务

        实现逻辑：
            1. 确定存储目录（generated_images）
            2. 创建目录（如果不存在）
        """
        self.storage_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'generated_images'
        ).replace('\\', '/')

        if not os.path.exists(self.storage_dir):
            try:
                os.makedirs(self.storage_dir)
                print(f"[DownloadService] Created storage directory: {self.storage_dir}")
            except Exception as e:
                error_msg = f"Failed to create storage directory {self.storage_dir}: {str(e)}"
                print(f"[DownloadService] Error: {error_msg}")
                raise RuntimeError(error_msg)

    def _get_extension_from_url(self, url: str) -> str:
        """
        从URL提取文件扩展名

        参数：
            url: 图片URL

        返回：
            文件扩展名（包含点号，如 '.png'）
        """
        # 移除URL参数
        url_without_params = url.split('?')[0]
        
        # 提取扩展名
        if '.' in url_without_params:
            ext = url_without_params.rsplit('.', 1)[1].lower()
            # 限制扩展名长度，防止恶意输入
            if len(ext) <= 10 and ext.isalnum():
                return '.' + ext
        
        # 默认返回.png
        return '.png'

    def _generate_filename(self, url: str, extension: str) -> str:
        """
        生成唯一的文件名

        参数：
            url: 原始图片URL
            extension: 文件扩展名

        返回：
            唯一文件名，格式为 'generated_YYYYMMDD_HHMMSS_uuid_extension'
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        unique_id = str(uuid.uuid4()).split('-')[0]
        
        return f"generated_{timestamp}_{url_hash}_{unique_id}{extension}"

    def download(self, image_url: str, local_path: Optional[str] = None, creator: str = '') -> Dict[str, Any]:
        """
        下载远程图片到本地

        参数：
            image_url: 远程图片URL
            local_path: 可选的本地路径，如果不提供则自动生成

        返回：
            包含下载结果的字典
        """
        if not image_url or not image_url.strip():
            raise ValueError("Image URL is required")

        # 如果没有提供本地路径，自动生成
        if not local_path:
            # 获取文件扩展名
            extension = self._get_extension_from_url(image_url)

            # 生成唯一文件名
            filename = self._generate_filename(image_url, extension)

            # 完整的本地文件路径
            target_storage_dir = creator_storage_dir(self.storage_dir, creator)
            os.makedirs(target_storage_dir, exist_ok=True)
            local_path = os.path.join(target_storage_dir, filename)

            # 近 N 秒内同 URL 已下载到本地 → 直接复用，避免重复下载产生孤儿文件
            # 实现逻辑：扫描存储目录下文件名含相同 url_hash 的近期文件，命中则替换 local_path 并短路返回
            # 异常处理：去重模块异常时 fail-open，继续走正常下载流程
            try:
                from services.download_dedup import find_recent_same_url_file
                reused_path = find_recent_same_url_file(image_url, target_storage_dir)
                if reused_path and os.path.isfile(reused_path) and os.path.getsize(reused_path) > 0:
                    print(f"[DownloadService] Reusing recent download for url_hash={hashlib.md5(image_url.encode()).hexdigest()[:8]}, path={reused_path}")
                    local_path = reused_path
                    # 命中复用 → 直接返回成功结果，不发 HTTP 请求、不重写文件
                    local_url = static_url_for_path(local_path, self.storage_dir, '/api/static/generated_images')
                    return {
                        'success': True,
                        'local_path': local_path,
                        'local_url': local_url,
                        'url': image_url,
                        'reused': True
                    }
            except Exception as dedup_err:
                print(f"[DownloadService] Dedup check failed, proceeding with normal download: {dedup_err}")

        print(f"[DownloadService] Downloading image from: {image_url}")
        print(f"[DownloadService] Saving to: {local_path}")

        # 配置请求会话，支持重试和SSL处理
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=2)
        session.mount('https://', adapter)
        session.mount('http://', adapter)

        # 尝试下载，支持SSL错误重试
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 下载图片，设置超时时间为 90 秒
                response = session.get(image_url, timeout=90, stream=True)
                response.raise_for_status()

                # 检查响应内容类型
                content_type = response.headers.get('Content-Type', '')
                if 'image' not in content_type and not any(ext in content_type for ext in ['png', 'jpeg', 'jpg', 'gif', 'webp']):
                    print(f"[DownloadService] Warning: Content-Type is {content_type}, expected image")

                # 分块写入文件以处理大文件
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                print(f"[DownloadService] Successfully downloaded image to: {local_path}")

                # 仅 generated_images 目录下的文件提供静态访问 URL。
                local_url = static_url_for_path(local_path, self.storage_dir, '/api/static/generated_images')

                return {
                    'success': True,
                    'local_path': local_path,
                    'local_url': local_url,
                    'filename': os.path.basename(local_path),
                    'original_url': image_url,
                    'storage_dir': self.storage_dir,
                    'file_size': os.path.getsize(local_path)
                }

            except requests.exceptions.SSLError as e:
                last_error = e
                print(f"[DownloadService] SSL Error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print(f"[DownloadService] Retrying without SSL verification...")
                    # 禁用SSL验证重试
                    session.verify = False
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    continue
                else:
                    error_msg = f"SSL Error after {max_retries} attempts: {str(e)}"
                    print(f"[DownloadService] Error: {error_msg}")
                    if os.path.exists(local_path):
                        os.remove(local_path)
                    raise RuntimeError(error_msg)

            except requests.exceptions.Timeout:
                last_error = e
                print(f"[DownloadService] Timeout (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print(f"[DownloadService] Retrying...")
                    continue
                else:
                    error_msg = f"Download timeout after {max_retries} attempts: {str(e)}"
                    print(f"[DownloadService] Error: {error_msg}")
                    if os.path.exists(local_path):
                        os.remove(local_path)
                    raise RuntimeError(error_msg)

            except requests.exceptions.RequestException as e:
                last_error = e
                print(f"[DownloadService] Request Error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print(f"[DownloadService] Retrying...")
                    continue
                else:
                    error_msg = f"Failed to download image from {image_url} after {max_retries} attempts: {str(e)}"
                    print(f"[DownloadService] Error: {error_msg}")
                    if os.path.exists(local_path):
                        os.remove(local_path)
                    raise RuntimeError(error_msg)

            except IOError as e:
                error_msg = f"Failed to save image to {local_path}: {str(e)}"
                print(f"[DownloadService] Error: {error_msg}")
                raise RuntimeError(error_msg)

        # 如果所有重试都失败
        error_msg = f"Failed to download image from {image_url}: {str(last_error)}"
        print(f"[DownloadService] Error: {error_msg}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise RuntimeError(error_msg)


# 全局下载服务实例（延迟初始化）
_download_service_instance: Optional[DownloadService] = None


def get_download_service() -> DownloadService:
    """
    获取全局下载服务实例（单例模式）

    返回：
        DownloadService 实例
    """
    global _download_service_instance
    if _download_service_instance is None:
        _download_service_instance = DownloadService()
    return _download_service_instance


def download_image_to_local(image_url: str, local_path: Optional[str] = None, creator: str = '') -> Dict[str, Any]:
    """
    下载图片到本地的便捷函数

    功能描述：
        封装 DownloadService.download 方法，提供更简洁的调用方式

    参数：
        image_url: 远程图片URL
        local_path: 可选的本地路径

    返回：
        包含下载结果的字典（与 DownloadService.download 返回值相同）

    使用示例：
        >>> result = download_image_to_local("https://example.com/image.png")
        >>> print(result['local_path'])
    """
    service = get_download_service()
    return service.download(image_url, local_path, creator)


def delete_local_file(local_path: str) -> bool:
    """
    删除本地文件

    参数：
        local_path: 本地文件路径

    返回：
        删除成功返回 True，失败返回 False
    """
    if not local_path:
        return False

    try:
        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"[DownloadService] Successfully deleted file: {local_path}")
            return True
        else:
            print(f"[DownloadService] File does not exist, nothing to delete: {local_path}")
            return False
    except Exception as e:
        error_msg = f"Failed to delete file {local_path}: {str(e)}"
        print(f"[DownloadService] Error: {error_msg}")
        return False


def rename_local_file(local_path: str, new_name: str) -> bool:
    """
    重命名本地文件

    参数：
        local_path: 当前文件路径
        new_name: 新文件名（不含路径）

    返回：
        重命名成功返回 True，失败返回 False
    """
    if not local_path or not new_name:
        return False

    try:
        directory = os.path.dirname(local_path)
        new_path = os.path.join(directory, new_name)

        if os.path.exists(local_path):
            os.rename(local_path, new_path)
            print(f"[DownloadService] Successfully renamed file: {local_path} -> {new_path}")
            return True
        else:
            print(f"[DownloadService] File does not exist: {local_path}")
            return False
    except Exception as e:
        error_msg = f"Failed to rename file {local_path}: {str(e)}"
        print(f"[DownloadService] Error: {error_msg}")
        return False
