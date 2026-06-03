"""
回收站服务

功能描述：
    提供图片回收站功能，包括将图片移入回收站、恢复图片、清空回收站、自动清理过期文件等

文件夹配置：
    回收站目录：E:\AI-image\回收站

接口列表：
    - move_to_recycle(image_id) - 将图片移入回收站
    - restore_from_recycle(image_id) - 从回收站恢复图片
    - empty_recycle_bin() - 清空回收站
    - cleanup_expired(days=30) - 清理过期文件（默认30天）
    - list_recycle_bin() - 获取回收站文件列表

使用方式：
    - 删除图片时调用 move_to_recycle() 将图片移到回收站
    - 用户可在回收站界面恢复图片或永久删除
    - 系统定期调用 cleanup_expired() 清理过期文件
"""

import os
import shutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# 基础目录配置
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
PROJECT_ROOT_DIR = os.path.dirname(BACKEND_DIR)

# 回收站目录
RECYCLE_BIN_DIR = os.path.join(PROJECT_ROOT_DIR, '回收站')


def ensure_recycle_bin_dir():
    """
    确保回收站目录存在

    功能描述：
        创建回收站目录（如果不存在）
    """
    os.makedirs(RECYCLE_BIN_DIR, exist_ok=True)


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
        return f"file_{int(time.time())}"

    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')

    return filename


def move_to_recycle(image_id: str, source_path: str) -> Dict[str, Any]:
    """
    将图片移入回收站

    功能描述：
        将指定图片从原位置移动到回收站目录

    实现逻辑：
        1. 确保回收站目录存在
        2. 生成带时间戳的目标文件名（避免冲突）
        3. 移动文件到回收站
        4. 返回移动结果

    参数：
        image_id: 图片ID
        source_path: 源图片的绝对路径

    返回：
        {
            'success': 是否成功,
            'recycle_path': 回收站中的路径,
            'deleted_at': 删除时间
        }
    """
    ensure_recycle_bin_dir()

    if not source_path or not os.path.exists(source_path):
        return {
            'success': False,
            'error': '源文件不存在'
        }

    try:
        # 获取原文件名
        original_filename = os.path.basename(source_path)
        # 生成带时间戳的新文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(original_filename)
        new_filename = f"{sanitize_filename(name)}_{timestamp}_{image_id[:8]}{ext}"

        # 目标路径
        target_path = os.path.join(RECYCLE_BIN_DIR, new_filename)

        # 移动文件
        shutil.move(source_path, target_path)

        deleted_at = datetime.now().isoformat()

        return {
            'success': True,
            'recycle_path': target_path,
            'recycle_filename': new_filename,
            'original_filename': original_filename,
            'deleted_at': deleted_at
        }

    except Exception as e:
        print(f"[RecycleBin] Failed to move file to recycle bin: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def restore_from_recycle(image_id: str, recycle_path: str, target_path: str) -> Dict[str, Any]:
    """
    从回收站恢复图片

    功能描述：
        将图片从回收站恢复到原位置或指定位置

    实现逻辑：
        1. 检查回收站文件是否存在
        2. 如果目标目录不存在则创建
        3. 移动文件到目标位置
        4. 返回恢复结果

    参数：
        image_id: 图片ID
        recycle_path: 回收站中的文件路径
        target_path: 目标恢复路径

    返回：
        {
            'success': 是否成功,
            'restored_path': 恢复后的路径
        }
    """
    if not recycle_path or not os.path.exists(recycle_path):
        return {
            'success': False,
            'error': '回收站文件不存在'
        }

    try:
        # 确保目标目录存在
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # 移动文件
        shutil.move(recycle_path, target_path)

        return {
            'success': True,
            'restored_path': target_path,
            'restored_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[RecycleBin] Failed to restore file from recycle bin: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# 根据图片ID在回收站目录中查找匹配的文件
def find_file_in_recycle_bin(image_id: str) -> Optional[str]:
    """
    功能描述：
        在回收站目录中搜索匹配图片ID的文件

    实现逻辑：
        1. 确保回收站目录存在
        2. 遍历回收站目录中的文件
        3. 检查文件名是否包含图片ID的前8位
        4. 返回第一个匹配的文件路径，未找到则返回None

    参数：
        image_id: 图片的完整UUID

    返回：
        匹配的文件路径（绝对路径），未找到则返回None
    """
    ensure_recycle_bin_dir()
    id_prefix = image_id[:8]
    for item in os.listdir(RECYCLE_BIN_DIR):
        if id_prefix in item:
            item_path = os.path.join(RECYCLE_BIN_DIR, item)
            if os.path.isfile(item_path):
                return item_path
    return None


def delete_permanently(recycle_path: str) -> Dict[str, Any]:
    """
    永久删除回收站中的文件

    功能描述：
        从回收站中永久删除指定文件

    参数：
        recycle_path: 回收站中的文件路径

    返回：
        {
            'success': 是否成功
        }
    """
    if not recycle_path or not os.path.exists(recycle_path):
        return {
            'success': True  # 文件不存在也算成功
        }

    try:
        os.remove(recycle_path)
        return {
            'success': True,
            'deleted_at': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"[RecycleBin] Failed to delete file permanently: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def empty_recycle_bin() -> Dict[str, Any]:
    """
    清空回收站

    功能描述：
        删除回收站目录下的所有文件和文件夹

    返回：
        {
            'success': 是否成功,
            'deleted_count': 删除的文件数量
        }
    """
    ensure_recycle_bin_dir()

    try:
        deleted_count = 0
        for item in os.listdir(RECYCLE_BIN_DIR):
            item_path = os.path.join(RECYCLE_BIN_DIR, item)
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    deleted_count += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    deleted_count += 1
            except Exception as e:
                print(f"[RecycleBin] Failed to delete item {item}: {e}")

        return {
            'success': True,
            'deleted_count': deleted_count,
            'emptied_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[RecycleBin] Failed to empty recycle bin: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def cleanup_expired(days: int = 30) -> Dict[str, Any]:
    """
    清理过期文件

    功能描述：
        自动清理回收站中超过指定天数的文件

    实现逻辑：
        1. 获取回收站目录下的所有文件
        2. 检查每个文件的修改时间
        3. 删除超过指定天数的文件

    参数：
        days: 过期天数，默认30天

    返回：
        {
            'success': 是否成功,
            'deleted_count': 删除的文件数量,
            'files_deleted': 被删除的文件列表
        }
    """
    ensure_recycle_bin_dir()

    try:
        deleted_count = 0
        files_deleted = []
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        for item in os.listdir(RECYCLE_BIN_DIR):
            item_path = os.path.join(RECYCLE_BIN_DIR, item)
            try:
                if os.path.isfile(item_path):
                    # 检查文件修改时间
                    file_mtime = os.path.getmtime(item_path)
                    if file_mtime < cutoff_time:
                        os.remove(item_path)
                        deleted_count += 1
                        files_deleted.append(item)
                elif os.path.isdir(item_path):
                    # 检查文件夹修改时间
                    dir_mtime = os.path.getmtime(item_path)
                    if dir_mtime < cutoff_time:
                        shutil.rmtree(item_path)
                        deleted_count += 1
                        files_deleted.append(item)
            except Exception as e:
                print(f"[RecycleBin] Failed to cleanup item {item}: {e}")

        return {
            'success': True,
            'deleted_count': deleted_count,
            'files_deleted': files_deleted,
            'cleaned_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[RecycleBin] Failed to cleanup expired files: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def list_recycle_bin() -> List[Dict[str, Any]]:
    """
    获取回收站文件列表

    功能描述：
        获取回收站目录下所有文件的列表及其信息

    返回：
        文件信息列表
    """
    ensure_recycle_bin_dir()

    try:
        files = []
        for item in os.listdir(RECYCLE_BIN_DIR):
            item_path = os.path.join(RECYCLE_BIN_DIR, item)
            if os.path.isfile(item_path):
                stat = os.stat(item_path)
                files.append({
                    'filename': item,
                    'path': item_path,
                    'size': stat.st_size,
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'days_old': (time.time() - stat.st_mtime) / (24 * 60 * 60)
                })
            elif os.path.isdir(item_path):
                stat = os.stat(item_path)
                files.append({
                    'filename': item,
                    'path': item_path,
                    'type': 'folder',
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'days_old': (time.time() - stat.st_mtime) / (24 * 60 * 60)
                })

        # 按修改时间倒序排列
        files.sort(key=lambda x: x['modified_at'], reverse=True)
        return files

    except Exception as e:
        print(f"[RecycleBin] Failed to list recycle bin: {e}")
        return []


def get_recycle_bin_info() -> Dict[str, Any]:
    """
    获取回收站统计信息

    功能描述：
        获取回收站的文件数量、总大小等信息

    返回：
        {
            'file_count': 文件数量,
            'total_size': 总大小（字节）,
            'oldest_file': 最旧文件的日期,
            'newest_file': 最新文件的日期
        }
    """
    ensure_recycle_bin_dir()

    try:
        files = list_recycle_bin()
        file_count = len(files)
        total_size = sum(f.get('size', 0) for f in files if 'size' in f)

        oldest = min(files, key=lambda x: x['modified_at']) if files else None
        newest = max(files, key=lambda x: x['modified_at']) if files else None

        return {
            'file_count': file_count,
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'oldest_file': oldest['modified_at'] if oldest else None,
            'newest_file': newest['modified_at'] if newest else None
        }

    except Exception as e:
        print(f"[RecycleBin] Failed to get recycle bin info: {e}")
        return {
            'file_count': 0,
            'total_size': 0,
            'total_size_mb': 0,
            'error': str(e)
        }
