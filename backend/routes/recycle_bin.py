"""
回收站路由

功能描述：
    提供图片回收站的API接口，包括移动到回收站、恢复、清空、清理过期文件等

接口列表：
    - GET /api/recycle/list - 获取回收站文件列表（文件系统）
    - GET /api/recycle/images - 获取回收站图片列表（数据库）
    - GET /api/recycle/image-count - 获取回收站图片数量
    - GET /api/recycle/info - 获取回收站统计信息
    - POST /api/recycle/move/{image_id} - 将图片移入回收站
    - POST /api/recycle/restore/{image_id} - 从回收站恢复图片
    - DELETE /api/recycle/<image_id> - 从回收站永久删除图片（含缩略图）
    - DELETE /api/recycle/empty - 清空回收站
    - DELETE /api/recycle/file/{filename} - 删除回收站中的指定文件
    - POST /api/recycle/cleanup - 手动触发清理过期文件
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify
from typing import Dict, Any

# 创建蓝图
recycle_bp = Blueprint('recycle', __name__)

# 导入回收站服务
from services.recycle_bin_service import (
    move_to_recycle,
    restore_from_recycle,
    delete_permanently,
    empty_recycle_bin,
    cleanup_expired,
    list_recycle_bin,
    get_recycle_bin_info,
    RECYCLE_BIN_DIR,
    ensure_recycle_bin_dir,
    find_file_in_recycle_bin
)

# 导入数据库连接
from models.database import get_db_connection


@recycle_bp.route('/api/recycle/list', methods=['GET'])
def get_recycle_list():
    """
    获取回收站文件列表

    响应：
    {
        "success": true,
        "data": [
            {
                "filename": "图片名称.png",
                "path": "/path/to/file",
                "size": 102400,
                "created_at": "2024-01-01T12:00:00",
                "modified_at": "2024-01-01T12:00:00",
                "days_old": 5
            }
        ]
    }
    """
    try:
        files = list_recycle_bin()
        return jsonify({
            'success': True,
            'data': files
        })
    except Exception as e:
        print(f"[Recycle] Failed to get recycle list: {e}")
        return jsonify({
            'success': False,
            'message': f'获取回收站列表失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/images', methods=['GET'])
def get_recycle_images():
    """
    获取回收站中的图片列表（从数据库）

    功能描述：
        从数据库获取 is_deleted = 1 的图片记录

    响应：
    {
        "success": true,
        "data": [
            {
                "id": "uuid",
                "url": "...",
                "thumbnail": "...",
                "prompt": "...",
                ...
            }
        ]
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 确保 is_deleted 字段存在
        cursor.execute("PRAGMA table_info(images)")
        columns = [row['name'] for row in cursor.fetchall()]

        if 'is_deleted' not in columns:
            conn.close()
            return jsonify({
                'success': True,
                'data': []
            })

        cursor.execute('''
            SELECT * FROM images
            WHERE is_deleted = 1
            ORDER BY deleted_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()

        # 转换为列表格式
        images = []
        for row in rows:
            img_dict = dict(row)
            images.append(img_dict)

        return jsonify({
            'success': True,
            'data': images
        })
    except Exception as e:
        print(f"[Recycle] Failed to get recycle images: {e}")
        return jsonify({
            'success': False,
            'message': f'获取回收站图片列表失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/info', methods=['GET'])
def get_recycle_info():
    """
    获取回收站统计信息

    响应：
    {
        "success": true,
        "data": {
            "file_count": 10,
            "total_size": 10485760,
            "total_size_mb": 10.0,
            "oldest_file": "2024-01-01T12:00:00",
            "newest_file": "2024-01-10T12:00:00"
        }
    }
    """
    try:
        info = get_recycle_bin_info()
        return jsonify({
            'success': True,
            'data': info
        })
    except Exception as e:
        print(f"[Recycle] Failed to get recycle info: {e}")
        return jsonify({
            'success': False,
            'message': f'获取回收站信息失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/image-count', methods=['GET'])
def get_recycle_image_count():
    """
    获取回收站中图片数量

    功能描述：
        从数据库中获取已删除图片（is_deleted = 1）的数量

    响应：
    {
        "success": true,
        "data": {
            "count": 10
        }
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 确保 is_deleted 字段存在
        cursor.execute("PRAGMA table_info(images)")
        columns = [row['name'] for row in cursor.fetchall()]

        if 'is_deleted' not in columns:
            conn.close()
            return jsonify({
                'success': True,
                'data': {'count': 0}
            })

        cursor.execute('SELECT COUNT(*) as count FROM images WHERE is_deleted = 1')
        result = cursor.fetchone()
        count = result['count'] if result else 0

        conn.close()

        return jsonify({
            'success': True,
            'data': {'count': count}
        })
    except Exception as e:
        print(f"[Recycle] Failed to get recycle image count: {e}")
        return jsonify({
            'success': False,
            'message': f'获取回收站图片数量失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/move/<image_id>', methods=['POST'])
def move_image_to_recycle(image_id):
    """
    将图片移入回收站（软删除）

    功能描述：
        将图片标记为已删除状态。如果存在本地文件则移动到回收站目录。

    请求体：
    {
        "source_path": "/path/to/source/image.png"  // 可选，如果没有本地文件则只标记数据库
    }

    响应：
    {
        "success": true,
        "data": {
            "image_id": "uuid",
            "recycle_path": "/path/to/recycle/image.png",  // 如果没有本地文件则为空
            "deleted_at": "2024-01-01T12:00:00"
        }
    }
    """
    try:
        data = request.get_json() or {}
        source_path = data.get('source_path', '')
        deleted_at = datetime.now().isoformat()
        recycle_path = ''

        # 更新数据库记录
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查图片是否存在，获取 local_path
        cursor.execute('SELECT id, local_path FROM images WHERE id = ?', (image_id,))
        image = cursor.fetchone()

        if image:
            # 添加回收站相关字段（如果不存在）
            cursor.execute("PRAGMA table_info(images)")
            columns = [row['name'] for row in cursor.fetchall()]

            if 'is_deleted' not in columns:
                cursor.execute('ALTER TABLE images ADD COLUMN is_deleted INTEGER DEFAULT 0')
            if 'deleted_at' not in columns:
                cursor.execute('ALTER TABLE images ADD COLUMN deleted_at TEXT')
            if 'recycle_path' not in columns:
                cursor.execute('ALTER TABLE images ADD COLUMN recycle_path TEXT')

            # 如果没有传入 source_path，使用数据库中的 local_path
            if not source_path:
                source_path = image['local_path'] or ''

            # 如果有本地文件路径且文件存在，则移动到回收站
            if source_path and os.path.exists(source_path):
                result = move_to_recycle(image_id, source_path)
                if result.get('success'):
                    recycle_path = result.get('recycle_path', '')
                    deleted_at = result.get('deleted_at', deleted_at)
                else:
                    print(f"[Recycle] Warning: Failed to move file to recycle: {result.get('error')}")

            # 更新数据库，标记为已删除
            cursor.execute('''
                UPDATE images
                SET is_deleted = 1, deleted_at = ?, recycle_path = ?
                WHERE id = ?
            ''', (deleted_at, recycle_path, image_id))

            conn.commit()
            conn.close()

        return jsonify({
            'success': True,
            'data': {
                'image_id': image_id,
                'recycle_path': recycle_path,
                'deleted_at': deleted_at
            }
        })

    except Exception as e:
        print(f"[Recycle] Failed to move image to recycle: {e}")
        return jsonify({
            'success': False,
            'message': f'移动到回收站失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/restore/<image_id>', methods=['POST'])
def restore_image_from_recycle(image_id):
    """
    从回收站恢复图片

    请求体：
    {
        "target_path": "/path/to/restore/image.png"  // 可选，默认恢复到原位置
    }

    响应：
    {
        "success": true,
        "data": {
            "image_id": "uuid",
            "restored_path": "/path/to/restored/image.png"
        }
    }
    """
    try:
        data = request.get_json() or {}
        target_path = data.get('target_path')

        # 获取图片信息
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, recycle_path, local_path, is_deleted
            FROM images
            WHERE id = ?
        ''', (image_id,))

        image = cursor.fetchone()

        if not image:
            conn.close()
            return jsonify({
                'success': False,
                'message': '图片不存在'
            }), 404

        recycle_path = image['recycle_path'] or image['local_path']

        # 如果回收站路径无效（为空或文件不存在），尝试在回收站目录中搜索匹配的文件
        if not recycle_path or not os.path.exists(recycle_path):
            found_path = find_file_in_recycle_bin(image_id)
            if found_path:
                recycle_path = found_path

        # 如果未指定目标路径，使用原位置
        if not target_path:
            target_path = image['local_path']
            # 如果原始目录已不存在，则恢复到全部图片目录（generated_images）
            target_dir = os.path.dirname(target_path)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            GENERATED_IMAGES_DIR = os.path.join(project_root, 'generated_images')
            if target_dir and not os.path.exists(target_dir):
                original_filename = os.path.basename(target_path)
                target_path = os.path.join(GENERATED_IMAGES_DIR, original_filename)

        # 从回收站恢复
        result = restore_from_recycle(image_id, recycle_path, target_path)

        if result.get('success'):
            # 更新数据库记录
            cursor.execute('''
                UPDATE images
                SET is_deleted = 0, deleted_at = NULL, recycle_path = NULL, local_path = ?
                WHERE id = ?
            ''', (target_path, image_id))

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'data': {
                    'image_id': image_id,
                    'restored_path': result.get('restored_path')
                }
            })
        else:
            conn.close()
            return jsonify({
                'success': False,
                'message': f'恢复失败: {result.get("error", "未知错误")}'
            }), 500

    except Exception as e:
        print(f"[Recycle] Failed to restore image: {e}")
        return jsonify({
            'success': False,
            'message': f'恢复失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/<image_id>', methods=['DELETE'])
def permanent_delete_image(image_id):
    """
    从回收站永久删除图片

    功能描述：
        彻底删除回收站中的图片及其缩略图

    实现逻辑：
        1. 从数据库获取图片信息（recycle_path 和 thumbnail）
        2. 删除回收站中的原图文件
        3. 删除 generated_thumbnails 中的缩略图文件
        4. 从数据库中删除图片记录

    响应：
    {
        "success": true,
        "message": "删除成功"
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, recycle_path, thumbnail, is_deleted
            FROM images
            WHERE id = ? AND is_deleted = 1
        ''', (image_id,))

        image = cursor.fetchone()

        if not image:
            conn.close()
            return jsonify({
                'success': False,
                'message': '图片不存在或未在回收站中'
            }), 404

        recycle_path = image['recycle_path']
        thumbnail_url = image['thumbnail']

        # 1. 删除回收站中的原图文件
        if recycle_path and os.path.exists(recycle_path):
            try:
                os.remove(recycle_path)
            except Exception as e:
                print(f"[Recycle] Failed to delete recycle file: {e}")

        # 2. 删除缩略图文件
        if thumbnail_url:
            THUMBNAIL_STATIC_PREFIX = '/api/static/generated_thumbnails/'
            if thumbnail_url.startswith(THUMBNAIL_STATIC_PREFIX):
                thumbnail_filename = thumbnail_url.replace(THUMBNAIL_STATIC_PREFIX, '', 1)
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                thumbnail_path = os.path.join(project_root, 'generated_thumbnails', thumbnail_filename)
                if os.path.exists(thumbnail_path):
                    try:
                        os.remove(thumbnail_path)
                    except Exception as e:
                        print(f"[Recycle] Failed to delete thumbnail file: {e}")

        # 3. 从数据库删除记录
        cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': '删除成功'
        })

    except Exception as e:
        print(f"[Recycle] Failed to permanently delete image: {e}")
        return jsonify({
            'success': False,
            'message': f'永久删除失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/empty', methods=['DELETE'])
def empty_recycle():
    """
    清空回收站

    响应：
    {
        "success": true,
        "data": {
            "deleted_count": 10
        }
    }
    """
    try:
        result = empty_recycle_bin()

        if result.get('success'):
            # 清空数据库中的已删除记录
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images WHERE is_deleted = 1')
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'data': {
                    'deleted_count': result.get('deleted_count', 0)
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': f'清空失败: {result.get("error", "未知错误")}'
            }), 500

    except Exception as e:
        print(f"[Recycle] Failed to empty recycle: {e}")
        return jsonify({
            'success': False,
            'message': f'清空失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/file/<filename>', methods=['DELETE'])
def delete_recycle_file(filename):
    """
    删除回收站中的指定文件

    响应：
    {
        "success": true
    }
    """
    try:
        # 构建文件路径
        file_path = os.path.join(RECYCLE_BIN_DIR, filename)

        result = delete_permanently(file_path)

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'删除失败: {result.get("error", "未知错误")}'
            }), 500

    except Exception as e:
        print(f"[Recycle] Failed to delete file: {e}")
        return jsonify({
            'success': False,
            'message': f'删除失败: {str(e)}'
        }), 500


@recycle_bp.route('/api/recycle/cleanup', methods=['POST'])
def trigger_cleanup():
    """
    手动触发清理过期文件

    请求体（可选）：
    {
        "days": 30  // 超过多少天清理，默认30天
    }

    响应：
    {
        "success": true,
        "data": {
            "deleted_count": 5,
            "files_deleted": ["file1.png", "file2.png"]
        }
    }
    """
    try:
        data = request.get_json() or {}
        days = data.get('days', 30)

        result = cleanup_expired(days)

        if result.get('success'):
            return jsonify({
                'success': True,
                'data': {
                    'deleted_count': result.get('deleted_count', 0),
                    'files_deleted': result.get('files_deleted', []),
                    'cleaned_at': result.get('cleaned_at')
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': f'清理失败: {result.get("error", "未知错误")}'
            }), 500

    except Exception as e:
        print(f"[Recycle] Failed to cleanup: {e}")
        return jsonify({
            'success': False,
            'message': f'清理失败: {str(e)}'
        }), 500


# 确保回收站目录存在
ensure_recycle_bin_dir()