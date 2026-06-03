"""
素材库服务

功能描述：
    提供素材库功能，扫描素材目录获取图片列表供用户选择作为参考图

文件夹配置：
    素材目录：E:\AI-image\素材

接口列表：
    - get_material_list() - 获取素材图片列表
    - get_material_info() - 获取素材库统计信息
    - scan_material_file(filename) - 获取单个素材的详细信息
    - upload_material() - 上传素材图片
    - create_material_folder() - 创建素材文件夹
    - delete_material_folder() - 删除素材文件夹
    - move_material() - 移动素材到指定文件夹
    - delete_material() - 删除素材
    - set_manual_url() - 设置素材的 manual_url
    - get_manual_url() - 获取素材的 manual_url
    - remove_manual_url() - 删除素材的 manual_url
"""

import json
import os
import shutil
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

# 基础目录配置
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
PROJECT_ROOT_DIR = os.path.dirname(BACKEND_DIR)

# 素材目录
MATERIAL_DIR = os.path.join(PROJECT_ROOT_DIR, '素材')

# 素材元数据文件（存储 manual_url 等信息）
MATERIAL_METADATA_FILE = os.path.join(MATERIAL_DIR, 'material_metadata.json')

# 支持的图片格式
SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}

# 加载素材元数据
# 功能描述：
#     从 material_metadata.json 加载所有素材的元数据（如 manual_url）
#     如果文件不存在或损坏，返回空字典
def _load_metadata() -> dict:
    if not os.path.exists(MATERIAL_METADATA_FILE):
        return {}
    try:
        with open(MATERIAL_METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Material] Failed to load metadata: {e}")
        return {}

# 保存素材元数据
# 功能描述：
#     将元数据字典写入 material_metadata.json
def _save_metadata(metadata: dict):
    try:
        os.makedirs(os.path.dirname(MATERIAL_METADATA_FILE), exist_ok=True)
        with open(MATERIAL_METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[Material] Failed to save metadata: {e}")

# 设置素材的 manual_url
# 功能描述：
#     为指定素材设置手动填写的 URL，保存到元数据文件
#     参数 relative_path：素材的相对路径（如 "folder/file.png" 或 "file.png"）
#     参数 url：手动填写的 URL，为空字符串则清除
def set_manual_url(relative_path: str, url: str) -> dict:
    metadata = _load_metadata()
    if 'manual_urls' not in metadata:
        metadata['manual_urls'] = {}
    if url:
        metadata['manual_urls'][relative_path] = url
    else:
        # url 为空字符串时删除该记录
        metadata['manual_urls'].pop(relative_path, None)
    _save_metadata(metadata)
    return {'success': True, 'relative_path': relative_path, 'manual_url': url}

# 获取素材的 manual_url
# 功能描述：
#     从元数据中读取指定素材的 manual_url，不存在返回 None
def get_manual_url(relative_path: str):
    metadata = _load_metadata()
    return metadata.get('manual_urls', {}).get(relative_path, None)

# 删除素材的 manual_url
# 功能描述：
#     从元数据中移除指定素材的记录，通常用于素材被删除时清理
def remove_manual_url(relative_path: str):
    metadata = _load_metadata()
    if 'manual_urls' in metadata:
        metadata['manual_urls'].pop(relative_path, None)
        _save_metadata(metadata)

# 缩略图生成（延迟导入避免循环依赖）
def _create_thumbnail_for_material(source_path: str) -> str:
    """
    为素材图片生成缩略图

    功能描述：
        调用 material_thumbnail_service 生成缩略图，失败时返回空字符串

    参数：
        source_path: 素材原图路径

    返回：
        缩略图 URL，失败时返回空字符串
    """
    try:
        from services.material_thumbnail_service import create_material_thumbnail
        thumb = create_material_thumbnail(source_path)
        if thumb.get('success'):
            return thumb.get('thumbnail_url', '')
    except Exception as e:
        print(f"[Material] Thumbnail generation failed: {e}")
    return ''


def ensure_material_dir():
    """
    确保素材目录存在

    功能描述：
        创建素材目录（如果不存在）
    """
    os.makedirs(MATERIAL_DIR, exist_ok=True)


def is_image_file(filename: str) -> bool:
    """
    检查文件是否为支持的图片格式

    参数：
        filename: 文件名

    返回：
        是否为支持的图片格式
    """
    ext = os.path.splitext(filename.lower())[1]
    return ext in SUPPORTED_IMAGE_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """
    清理文件名

    功能描述：
        将文件名中的非法字符替换为下划线

    参数：
        filename: 原始文件名

    返回：
        清理后的文件名
    """
    if not filename:
        return f"material_{int(time.time())}"

    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')

    return filename


def sanitize_folder_name(name: str) -> str:
    """
    清理文件夹名称

    功能描述：
        将名称中的非法字符替换为下划线

    参数：
        name: 原始文件夹名称

    返回：
        清理后的文件夹名称
    """
    if not name:
        return 'untitled'

    name = name.strip()
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        name = name.replace(char, '_')

    if len(name) > 50:
        name = name[:50]

    if not name:
        return 'untitled'

    return name


def get_material_list(folder_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取素材图片列表

    功能描述：
        扫描素材目录，获取所有支持的图片文件列表

    参数：
        folder_path: 子文件夹路径（可选），默认为素材根目录

    返回：
        图片文件列表
    """
    if folder_path:
        scan_dir = os.path.join(MATERIAL_DIR, folder_path)
    else:
        scan_dir = MATERIAL_DIR

    # 确保目录存在
    if not os.path.exists(scan_dir):
        return []

    try:
        materials = []
        metadata = _load_metadata()
        manual_urls = metadata.get('manual_urls', {})

        for item in os.listdir(scan_dir):
            item_path = os.path.join(scan_dir, item)

            if os.path.isfile(item_path) and is_image_file(item):
                stat = os.stat(item_path)
                relative = os.path.join(folder_path, item) if folder_path else item
                materials.append({
                    'id': relative,
                    'filename': item,
                    'name': os.path.splitext(item)[0],
                    'path': item_path,
                    'relative_path': relative,
                    'size': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'extension': os.path.splitext(item)[1].lower(),
                    'thumbnail_url': _create_thumbnail_for_material(item_path),
                    'manual_url': manual_urls.get(relative, '')
                })

        # 按修改时间倒序排列
        materials.sort(key=lambda x: x['modified_at'], reverse=True)
        return materials

    except Exception as e:
        print(f"[Material] Failed to get material list: {e}")
        return []


def get_material_list_with_subdirs() -> List[Dict[str, Any]]:
    """
    获取素材图片列表（包括子文件夹）

    功能描述：
        递归扫描素材目录及其子文件夹，获取所有图片文件

    返回：
        图片文件列表（包含所属子文件夹信息）
    """
    if not os.path.exists(MATERIAL_DIR):
        return []

    try:
        materials = []
        subfolders = []

        # 首先列出所有子文件夹
        for item in os.listdir(MATERIAL_DIR):
            item_path = os.path.join(MATERIAL_DIR, item)
            if os.path.isdir(item_path):
                subfolders.append(item)

        # 添加根目录的图片
        root_materials = get_material_list()
        for mat in root_materials:
            mat['folder'] = ''
            mat['folder_name'] = '根目录'
        materials.extend(root_materials)

        # 扫描每个子文件夹
        for subfolder in subfolders:
            sub_materials = get_material_list(subfolder)
            for mat in sub_materials:
                mat['folder'] = subfolder
                mat['folder_name'] = subfolder
            materials.extend(sub_materials)

        return materials

    except Exception as e:
        print(f"[Material] Failed to get material list with subdirs: {e}")
        return []


def get_material_info() -> Dict[str, Any]:
    """
    获取素材库统计信息

    返回：
        {
            'file_count': 文件数量,
            'total_size': 总大小（字节）,
            'total_size_mb': 总大小（MB）,
            'folder_count': 子文件夹数量,
            'folders': ['子文件夹1', '子文件夹2']
        }
    """
    ensure_material_dir()

    try:
        materials = get_material_list()
        file_count = len(materials)
        total_size = sum(m.get('size', 0) for m in materials)

        # 获取子文件夹
        folders = []
        for item in os.listdir(MATERIAL_DIR):
            item_path = os.path.join(MATERIAL_DIR, item)
            if os.path.isdir(item_path):
                folders.append(item)

        return {
            'file_count': file_count,
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'folder_count': len(folders),
            'folders': folders
        }

    except Exception as e:
        print(f"[Material] Failed to get material info: {e}")
        return {
            'file_count': 0,
            'total_size': 0,
            'total_size_mb': 0,
            'folder_count': 0,
            'folders': [],
            'error': str(e)
        }


def get_material_by_filename(filename: str) -> Optional[Dict[str, Any]]:
    """
    根据文件名获取素材信息

    参数：
        filename: 文件名

    返回：
        素材信息，如果不存在返回 None
    """
    materials = get_material_list()

    for mat in materials:
        if mat['filename'] == filename:
            return mat

    return None


def get_materials_by_folder(folder_name: str) -> List[Dict[str, Any]]:
    """
    获取指定文件夹中的素材

    参数：
        folder_name: 文件夹名称（空字符串表示根目录）

    返回：
        素材列表
    """
    if folder_name:
        materials = get_material_list(folder_name)
        for mat in materials:
            mat['folder'] = folder_name
            mat['folder_name'] = folder_name
        return materials
    else:
        return get_material_list()


def upload_material(file_data: bytes, filename: str, folder_name: Optional[str] = None) -> Dict[str, Any]:
    """
    上传素材图片

    功能描述：
        将上传的图片文件保存到素材库指定文件夹

    实现逻辑：
        1. 清理文件名
        2. 如果指定了文件夹，确保文件夹存在
        3. 生成唯一文件名（避免覆盖）
        4. 保存文件
        5. 返回文件信息

    参数：
        file_data: 文件二进制数据
        filename: 原始文件名
        folder_name: 目标文件夹名称（可选）

    返回：
        {
            'success': 是否成功,
            'filename': 保存的文件名,
            'path': 保存的完整路径,
            'size': 文件大小
        }
    """
    ensure_material_dir()

    try:
        safe_filename = sanitize_filename(filename)

        if folder_name:
            target_dir = os.path.join(MATERIAL_DIR, sanitize_folder_name(folder_name))
        else:
            target_dir = MATERIAL_DIR

        os.makedirs(target_dir, exist_ok=True)

        # 生成唯一文件名
        name, ext = os.path.splitext(safe_filename)
        final_filename = safe_filename
        counter = 1

        while os.path.exists(os.path.join(target_dir, final_filename)):
            final_filename = f"{name}_{int(time.time())}_{counter}{ext}"
            counter += 1

        target_path = os.path.join(target_dir, final_filename)

        with open(target_path, 'wb') as f:
            f.write(file_data)

        stat = os.stat(target_path)

        return {
            'success': True,
            'id': os.path.join(folder_name, final_filename) if folder_name else final_filename,
            'filename': final_filename,
            'path': target_path,
            'relative_path': os.path.join(folder_name, final_filename) if folder_name else final_filename,
            'size': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'folder': folder_name or '',
            'created_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[Material] Failed to upload material: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def create_material_folder(folder_name: str) -> Dict[str, Any]:
    """
    创建素材文件夹

    功能描述：
        在素材目录下创建新的子文件夹

    参数：
        folder_name: 文件夹名称

    返回：
        {
            'success': 是否成功,
            'name': 文件夹名称,
            'path': 文件夹路径
        }
    """
    ensure_material_dir()

    try:
        safe_name = sanitize_folder_name(folder_name)
        target_path = os.path.join(MATERIAL_DIR, safe_name)

        if os.path.exists(target_path):
            return {
                'success': False,
                'error': '文件夹已存在'
            }

        os.makedirs(target_path, exist_ok=True)

        return {
            'success': True,
            'name': safe_name,
            'path': target_path,
            'created_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[Material] Failed to create folder: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def delete_material_folder(folder_name: str) -> Dict[str, Any]:
    """
    删除素材文件夹

    功能描述：
        删除素材库中指定的子文件夹（必须为空）

    参数：
        folder_name: 文件夹名称

    返回：
        {
            'success': 是否成功,
            'deleted_count': 删除的文件数量
        }
    """
    if not folder_name:
        return {
            'success': False,
            'error': '无法删除根目录'
        }

    target_path = os.path.join(MATERIAL_DIR, folder_name)

    if not os.path.exists(target_path):
        return {
            'success': True  # 文件夹不存在也算成功
        }

    if not os.path.isdir(target_path):
        return {
            'success': False,
            'error': '指定的路径不是文件夹'
        }

    try:
        # 检查文件夹是否为空
        contents = os.listdir(target_path)
        if contents:
            return {
                'success': False,
                'error': f'文件夹不为空，包含 {len(contents)} 个项目'
            }

        os.rmdir(target_path)

        return {
            'success': True,
            'deleted_count': 0,
            'deleted_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[Material] Failed to delete folder: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def move_material(filename: str, source_folder: str, target_folder: str) -> Dict[str, Any]:
    """
    移动素材到指定文件夹

    功能描述：
        将素材从源文件夹移动到目标文件夹

    参数：
        filename: 文件名
        source_folder: 源文件夹名称（空字符串表示根目录）
        target_folder: 目标文件夹名称（空字符串表示根目录）

    返回：
        {
            'success': 是否成功,
            'new_path': 新的文件路径
        }
    """
    if source_folder == target_folder:
        return {
            'success': True,
            'message': '文件已在目标文件夹'
        }

    try:
        if source_folder:
            source_path = os.path.join(MATERIAL_DIR, source_folder, filename)
        else:
            source_path = os.path.join(MATERIAL_DIR, filename)

        if not os.path.exists(source_path):
            return {
                'success': False,
                'error': '源文件不存在'
            }

        if target_folder:
            target_dir = os.path.join(MATERIAL_DIR, target_folder)
            os.makedirs(target_dir, exist_ok=True)
        else:
            target_dir = MATERIAL_DIR

        target_path = os.path.join(target_dir, filename)

        shutil.move(source_path, target_path)

        return {
            'success': True,
            'new_path': target_path,
            'new_relative_path': os.path.join(target_folder, filename) if target_folder else filename,
            'moved_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[Material] Failed to move material: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def delete_material(filename: str, folder_name: Optional[str] = None) -> Dict[str, Any]:
    """
    删除素材

    功能描述：
        从素材库中删除指定的图片文件

    参数：
        filename: 文件名
        folder_name: 文件夹名称（可选，空字符串表示根目录）

    返回：
        {
            'success': 是否成功
        }
    """
    try:
        if folder_name:
            file_path = os.path.join(MATERIAL_DIR, folder_name, filename)
            relative_path = os.path.join(folder_name, filename)
        else:
            file_path = os.path.join(MATERIAL_DIR, filename)
            relative_path = filename

        if not os.path.exists(file_path):
            # 文件不存在时也清理元数据（避免残留）
            remove_manual_url(relative_path)
            return {
                'success': True  # 文件不存在也算成功
            }

        os.remove(file_path)

        # 删除素材时同步清理元数据中的 manual_url
        remove_manual_url(relative_path)

        return {
            'success': True,
            'deleted_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[Material] Failed to delete material: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def rename_material(old_filename: str, new_name: str, folder_name: Optional[str] = None) -> Dict[str, Any]:
    """
    重命名素材

    功能描述：
        重命名素材库中指定的图片文件，保留原扩展名

    实现逻辑：
        1. 构建旧文件路径和新文件路径
        2. 验证旧文件存在
        3. 验证新文件名合法且不冲突
        4. 执行重命名

    参数：
        old_filename: 旧文件名（含扩展名）
        new_name: 新名称（不含扩展名）
        folder_name: 文件夹名称（可选）

    返回：
        {
            'success': 是否成功,
            'new_filename': 新文件名,
            'new_path': 新文件路径
        }
    """
    try:
        if folder_name:
            folder_path = os.path.join(MATERIAL_DIR, sanitize_folder_name(folder_name))
        else:
            folder_path = MATERIAL_DIR

        old_path = os.path.join(folder_path, old_filename)

        if not os.path.exists(old_path):
            return {
                'success': False,
                'error': '文件不存在'
            }

        ext = os.path.splitext(old_filename)[1]
        safe_new_name = sanitize_filename(new_name)
        new_filename = safe_new_name + ext
        new_path = os.path.join(folder_path, new_filename)

        if new_filename == old_filename:
            return {
                'success': True,
                'new_filename': new_filename,
                'new_path': new_path
            }

        if os.path.exists(new_path):
            return {
                'success': False,
                'error': '目标文件名已存在'
            }

        os.rename(old_path, new_path)

        return {
            'success': True,
            'new_filename': new_filename,
            'new_path': new_path,
            'renamed_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[Material] Failed to rename material: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def get_folder_file_count(folder_name: str) -> int:
    """
    获取文件夹中的文件数量

    参数：
        folder_name: 文件夹名称

    返回：
        文件数量
    """
    folder_path = os.path.join(MATERIAL_DIR, folder_name)

    if not os.path.exists(folder_path):
        return 0

    try:
        count = 0
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path) and is_image_file(item):
                count += 1
        return count
    except Exception:
        return 0
