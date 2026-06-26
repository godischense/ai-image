import os
import shutil
from datetime import datetime
from typing import Optional, Dict, Any

# 基础目录配置
# 编辑结果目录固定创建在项目根目录下，避免误落到 backend 子目录中。
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
PROJECT_ROOT_DIR = os.path.dirname(BACKEND_DIR)
EDIT_FOLDERS_DIR = os.path.join(PROJECT_ROOT_DIR, 'edit_folders')

# 图片文件夹配置
# 直接在 generated_images 目录下创建子文件夹，弃用独立的"图片管理"目录
IMAGE_MANAGE_DIR = os.path.join(PROJECT_ROOT_DIR, 'generated_images')


def sanitize_folder_name(name: str) -> str:
    """
    清理文件夹名称

    功能描述：
        将名称中的非法字符替换为下划线，确保可用于文件夹命名

    实现逻辑：
        1. 去除首尾空白
        2. 替换 Windows/Linux 非法字符
        3. 限制长度不超过 50 个字符
    """
    if not name:
        return 'untitled'

    # 去除首尾空白
    name = name.strip()

    # 替换非法字符（含换行、回车、制表符等在文件系统中无效的字符）
    illegal_chars = '<>:"/\\|?*\n\r\t'
    for char in illegal_chars:
        name = name.replace(char, '_')

    # 限制长度
    if len(name) > 50:
        name = name[:50]

    # 如果为空，使用默认名称
    if not name:
        return 'untitled'

    return name


def create_image_folder(folder_name: str) -> Dict[str, Any]:
    """
    创建图片管理子文件夹

    功能描述：
        在图片管理目录下创建对应的子文件夹，用于存放用户创建的图片文件夹

    实现逻辑：
        1. 确保图片管理根目录存在
        2. 清理文件夹名称
        3. 在图片管理目录下创建子文件夹
        4. 返回文件夹路径信息

    参数：
        folder_name: 用户输入的文件夹名称

    返回：
        {
            'folder_path': 相对于图片管理目录的路径,
            'absolute_path': 绝对路径,
            'folder_name': 文件夹名称,
            'success': 是否成功
        }
    """
    safe_name = sanitize_folder_name(folder_name)
    absolute_path = os.path.join(IMAGE_MANAGE_DIR, safe_name)

    try:
        os.makedirs(absolute_path, exist_ok=True)
        return {
            'folder_path': safe_name,
            'absolute_path': absolute_path,
            'folder_name': safe_name,
            'success': True
        }
    except Exception as e:
        print(f"[FolderService] Failed to create image folder: {e}")
        return {
            'folder_path': None,
            'absolute_path': None,
            'folder_name': None,
            'success': False,
            'error': str(e)
        }


def get_image_folder_path(folder_name: str) -> str:
    """
    获取图片文件夹的绝对路径

    功能描述：
        根据文件夹名称获取对应的绝对路径

    参数：
        folder_name: 文件夹名称

    返回：
        文件夹的绝对路径
    """
    return os.path.join(IMAGE_MANAGE_DIR, sanitize_folder_name(folder_name))


def move_image_to_folder(source_path: str, folder_name: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    将图片移动到指定文件夹

    功能描述：
        将图片从原位置移动到图片管理下的对应子文件夹
        缩略图位置不变，只移动原图

    实现逻辑：
        1. 构建目标文件夹路径
        2. 如果未指定文件名，从源路径提取
        3. 移动图片文件
        4. 返回新的路径信息

    参数：
        source_path: 源图片的绝对路径
        folder_name: 目标文件夹名称
        filename: 指定的目标文件名（可选）

    返回：
        {
            'new_path': 新的图片路径,
            'success': 是否成功
        }
    """
    target_folder = os.path.join(IMAGE_MANAGE_DIR, sanitize_folder_name(folder_name))

    if not os.path.exists(target_folder):
        os.makedirs(target_folder, exist_ok=True)

    if not filename:
        filename = os.path.basename(source_path)

    target_path = os.path.join(target_folder, filename)

    try:
        shutil.move(source_path, target_path)
        return {
            'new_path': target_path,
            'relative_path': os.path.join(sanitize_folder_name(folder_name), filename),
            'success': True
        }
    except Exception as e:
        print(f"[FolderService] Failed to move image to folder: {e}")
        return {
            'new_path': None,
            'success': False,
            'error': str(e)
        }


def delete_image_folder(folder_name: str) -> Dict[str, Any]:
    """
    删除图片文件夹

    功能描述：
        删除图片管理下的对应子文件夹及其所有内容

    参数：
        folder_name: 文件夹名称

    返回：
        {
            'success': 是否成功
        }
    """
    folder_path = os.path.join(IMAGE_MANAGE_DIR, sanitize_folder_name(folder_name))

    if not os.path.exists(folder_path):
        return {'success': True}

    try:
        shutil.rmtree(folder_path)
        return {'success': True}
    except Exception as e:
        print(f"[FolderService] Failed to delete image folder: {e}")
        return {'success': False, 'error': str(e)}


def list_image_folders() -> list:
    """
    列出所有图片文件夹

    功能描述：
        获取图片管理目录下的所有子文件夹列表

    返回：
        文件夹列表
    """
    try:
        folders = []
        for item in os.listdir(IMAGE_MANAGE_DIR):
            item_path = os.path.join(IMAGE_MANAGE_DIR, item)
            if os.path.isdir(item_path):
                folders.append({
                    'name': item,
                    'path': item,
                    'absolute_path': item_path
                })
        return folders
    except Exception as e:
        print(f"[FolderService] Failed to list image folders: {e}")
        return []


def ensure_edit_folders_dir():
    """
    确保编辑文件夹根目录存在

    功能描述：
        创建 edit_folders 目录（如果不存在）
    """
    os.makedirs(EDIT_FOLDERS_DIR, exist_ok=True)


# [DEPRECATED] 编辑结果现在直接存入 edit_folders 根目录，不再创建子文件夹
def create_edit_folder(parent_image_id: str, parent_title: str, parent_folder_path: Optional[str] = None) -> Dict[str, Any]:
    """
    创建编辑图片的存储文件夹

    功能描述：
        根据父图片信息创建对应的文件夹，用于存放编辑后的图片

    实现逻辑：
        1. 如果是根图片（无 parent_folder_path），创建 edit_名称_时间戳 文件夹
        2. 如果是子图片，在父文件夹下创建 sub_名称_时间戳 子文件夹
        3. 返回文件夹路径信息

    参数：
        parent_image_id: 父图片ID
        parent_title: 父图片标题/名称
        parent_folder_path: 父图片的文件夹路径（如果有）

    返回：
        {
            'folder_path': 相对路径,
            'absolute_path': 绝对路径,
            'folder_name': 文件夹名称
        }
    """
    ensure_edit_folders_dir()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = sanitize_folder_name(parent_title)

    if not parent_folder_path:
        # 根图片：创建 edit_名称_时间戳 文件夹
        folder_name = f"edit_{safe_name}_{timestamp}"
        relative_path = folder_name
    else:
        # 子图片：在父文件夹下创建 sub_名称_时间戳 子文件夹
        folder_name = f"sub_{safe_name}_{timestamp}"
        relative_path = os.path.join(parent_folder_path, folder_name)

    absolute_path = os.path.join(EDIT_FOLDERS_DIR, relative_path)

    try:
        os.makedirs(absolute_path, exist_ok=True)
        return {
            'folder_path': relative_path,
            'absolute_path': absolute_path,
            'folder_name': folder_name,
            'success': True
        }
    except Exception as e:
        print(f"[FolderService] Failed to create folder: {e}")
        return {
            'folder_path': None,
            'absolute_path': None,
            'folder_name': None,
            'success': False,
            'error': str(e)
        }


# [DEPRECATED] 编辑结果现在直接存入 edit_folders 根目录，不再创建子文件夹
def rename_edit_folder(old_folder_path: str, new_title: str) -> Dict[str, Any]:
    """
    重命名编辑文件夹

    功能描述：
        当图片重命名时，同步重命名对应的文件夹

    实现逻辑：
        1. 解析旧文件夹路径
        2. 生成新文件夹名称（保留时间戳）
        3. 重命名文件夹
        4. 返回新的路径信息

    参数：
        old_folder_path: 旧文件夹相对路径
        new_title: 新标题

    返回：
        {
            'new_folder_path': 新相对路径,
            'new_absolute_path': 新绝对路径,
            'success': 是否成功
        }
    """
    if not old_folder_path:
        return {
            'new_folder_path': None,
            'new_absolute_path': None,
            'success': True  # 没有文件夹需要重命名
        }

    ensure_edit_folders_dir()

    old_absolute_path = os.path.join(EDIT_FOLDERS_DIR, old_folder_path)

    if not os.path.exists(old_absolute_path):
        return {
            'new_folder_path': old_folder_path,
            'new_absolute_path': old_absolute_path,
            'success': True  # 文件夹不存在，无需重命名
        }

    try:
        # 解析旧文件夹名称，提取时间戳
        old_folder_name = os.path.basename(old_folder_path)
        parts = old_folder_name.rsplit('_', 1)

        if len(parts) == 2 and parts[1].replace('_', '').isdigit():
            # 保留前缀和时间戳
            prefix = parts[0].rsplit('_', 1)[0] if '_' in parts[0] else parts[0]
            timestamp = parts[1]
        else:
            # 无法解析，使用当前时间戳
            prefix = 'edit' if 'edit_' in old_folder_name else 'sub'
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        safe_name = sanitize_folder_name(new_title)
        new_folder_name = f"{prefix}_{safe_name}_{timestamp}"

        # 构建新路径
        parent_dir = os.path.dirname(old_folder_path)
        if parent_dir:
            new_relative_path = os.path.join(parent_dir, new_folder_name)
        else:
            new_relative_path = new_folder_name

        new_absolute_path = os.path.join(EDIT_FOLDERS_DIR, new_relative_path)

        # 如果目标已存在，添加序号
        counter = 1
        original_new_absolute_path = new_absolute_path
        while os.path.exists(new_absolute_path):
            new_folder_name = f"{prefix}_{safe_name}_{timestamp}_{counter}"
            if parent_dir:
                new_relative_path = os.path.join(parent_dir, new_folder_name)
            else:
                new_relative_path = new_folder_name
            new_absolute_path = os.path.join(EDIT_FOLDERS_DIR, new_relative_path)
            counter += 1

        # 重命名文件夹
        shutil.move(old_absolute_path, new_absolute_path)

        return {
            'new_folder_path': new_relative_path,
            'new_absolute_path': new_absolute_path,
            'success': True
        }

    except Exception as e:
        print(f"[FolderService] Failed to rename folder: {e}")
        return {
            'new_folder_path': old_folder_path,
            'new_absolute_path': old_absolute_path,
            'success': False,
            'error': str(e)
        }


def save_image_to_folder(image_url: str, folder_path: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    将图片保存到指定文件夹

    功能描述：
        下载图片并保存到编辑文件夹中

    实现逻辑：
        1. 构建完整保存路径
        2. 下载图片
        3. 保存到指定路径
        4. 返回本地路径信息

    参数：
        image_url: 图片URL
        folder_path: 相对文件夹路径
        filename: 指定文件名（可选）

    返回：
        {
            'local_path': 本地绝对路径,
            'relative_path': 相对路径,
            'success': 是否成功
        }
    """
    ensure_edit_folders_dir()

    absolute_folder = os.path.join(EDIT_FOLDERS_DIR, folder_path)
    os.makedirs(absolute_folder, exist_ok=True)

    if not filename:
        # 从URL提取扩展名，或使用默认名称
        ext = os.path.splitext(image_url.split('?')[0])[1] or '.png'
        filename = f"edited_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

    local_path = os.path.join(absolute_folder, filename)

    try:
        from services.download_service import download_image_to_local

        # 下载图片
        result = download_image_to_local(image_url, local_path)

        if result.get('success'):
            return {
                'local_path': local_path,
                'relative_path': os.path.join(folder_path, filename),
                'success': True
            }
        else:
            return {
                'local_path': None,
                'relative_path': None,
                'success': False,
                'error': result.get('error', 'Download failed')
            }

    except Exception as e:
        print(f"[FolderService] Failed to save image to folder: {e}")
        return {
            'local_path': None,
            'relative_path': None,
            'success': False,
            'error': str(e)
        }


def get_folder_absolute_path(folder_path: str) -> str:
    """
    获取文件夹的绝对路径

    功能描述：
        将相对路径转换为绝对路径
    """
    return os.path.join(EDIT_FOLDERS_DIR, folder_path)


def delete_edit_folder(folder_path: str) -> bool:
    """
    删除编辑文件夹

    功能描述：
        递归删除编辑文件夹及其所有内容

    实现逻辑：
        1. 构建绝对路径
        2. 检查文件夹是否存在
        3. 递归删除
        4. 返回是否成功
    """
    if not folder_path:
        return True

    absolute_path = os.path.join(EDIT_FOLDERS_DIR, folder_path)

    if not os.path.exists(absolute_path):
        return True

    try:
        shutil.rmtree(absolute_path)
        return True
    except Exception as e:
        print(f"[FolderService] Failed to delete folder: {e}")
        return False


# [DEPRECATED] 编辑结果现在直接存入 edit_folders 根目录，不再创建子文件夹
def list_edit_folders() -> list:
    """
    列出所有编辑文件夹

    功能描述：
        获取 edit_folders 目录下的所有文件夹列表
    """
    ensure_edit_folders_dir()

    try:
        folders = []
        for item in os.listdir(EDIT_FOLDERS_DIR):
            item_path = os.path.join(EDIT_FOLDERS_DIR, item)
            if os.path.isdir(item_path):
                folders.append({
                    'name': item,
                    'path': item,
                    'absolute_path': item_path
                })
        return folders
    except Exception as e:
        print(f"[FolderService] Failed to list folders: {e}")
        return []