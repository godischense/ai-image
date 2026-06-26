"""
文件夹管理器路由

功能描述：
    提供文件夹和图片的管理接口，包括创建、查询、更新、删除等操作
    文件夹实际存储在项目根目录的"图片管理"文件夹下

接口列表：
    - POST /api/folders - 创建文件夹
    - GET /api/folders - 获取所有文件夹
    - GET /api/folders/{folder_id} - 获取单个文件夹详情
    - PUT /api/folders/{folder_id} - 更新文件夹名称
    - DELETE /api/folders/{folder_id} - 删除文件夹
    - POST /api/folders/{folder_id}/images - 添加图片到文件夹
    - GET /api/folders/{folder_id}/images - 获取文件夹中的图片
    - DELETE /api/images/{image_id} - 删除图片
    - PUT /api/images/{image_id}/move - 移动图片到其他文件夹
"""

import uuid
import json
import shutil
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from typing import Optional, Dict, Any

# 创建蓝图
folder_manager_bp = Blueprint('folder_manager', __name__)

# 导入数据库连接
from models.database import get_db_connection

# 导入文件夹服务
from services.folder_service import (
    create_image_folder,
    delete_image_folder,
    move_image_to_folder,
    list_image_folders,
    IMAGE_MANAGE_DIR
)

# 导入未分配虚拟文件夹服务
from services.unassigned_folder_service import (
    list_unassigned_images,
    get_unassigned_folder_meta,
    UNASSIGNED_FOLDER_ID
)
from services.auth_service import current_creator, current_user_is_admin

# ==================== 文件夹相关接口 ====================

@folder_manager_bp.route('/api/folders', methods=['POST'])
def create_folder():
    """
    创建文件夹

    请求体：
    {
        "name": "文件夹名称",
        "extra": {}  // 可选，备用字段
    }

    响应：
    {
        "success": true,
        "data": {
            "id": "uuid-string",
            "name": "文件夹名称",
            "folder_path": "图片管理/文件夹名称",
            "extra": {},
            "created_at": "2024-01-01T12:00:00"
        }
    }
    """
    try:
        data = request.get_json()
        folder_name = data.get('name', '').strip()

        if not folder_name:
            return jsonify({
                'success': False,
                'message': '文件夹名称不能为空'
            }), 400

        # 在磁盘上创建实际的文件夹
        folder_result = create_image_folder(folder_name)

        if not folder_result.get('success'):
            return jsonify({
                'success': False,
                'message': f'创建文件夹失败: {folder_result.get("error", "未知错误")}'
            }), 500

        # 创建数据库记录
        folder_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        extra = json.dumps(data.get('extra', {}))
        folder_path = folder_result.get('folder_path')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO folders (id, name, folder_path, extra, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (folder_id, folder_name, folder_path, extra, created_at, created_at))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'id': folder_id,
                'name': folder_name,
                'folder_path': folder_path,
                'extra': data.get('extra', {}),
                'created_at': created_at
            }
        }), 201

    except Exception as e:
        print(f"[FolderManager] Failed to create folder: {e}")
        return jsonify({
            'success': False,
            'message': f'创建文件夹失败: {str(e)}'
        }), 500


@folder_manager_bp.route('/api/folders', methods=['GET'])
def get_all_folders():
    """
    获取所有文件夹

    功能描述：
        返回 folders 表中的真实文件夹，并在最前面拼接「未分配」虚拟文件夹
        「未分配」对应 generated_thumbnails 根目录下的图片，不需要数据库记录

    响应：
    {
        "success": true,
        "data": [
            {
                "id": "unassigned",
                "name": "未分配",
                "image_count": 数量,
                "is_virtual": true,
                "extra": {}
            },
            {
                "id": "uuid-string",
                "name": "文件夹名称",
                "image_count": 10,
                "extra": {},
                "created_at": "2024-01-01T12:00:00"
            }
        ]
    }
    """
    try:
        # 未分配虚拟文件夹永远位于列表首位
        # 失败处理：扫描抛错时仍返回空 count 的元数据，避免前端下拉空掉
        try:
            unassigned_meta = get_unassigned_folder_meta()
        except Exception as unassigned_err:
            print(f"[FolderManager] 获取未分配文件夹元数据失败: {unassigned_err}")
            unassigned_meta = {
                'id': UNASSIGNED_FOLDER_ID,
                'name': '未分配',
                'image_count': 0,
                'is_virtual': True,
                'extra': {}
            }

        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取所有文件夹及图片数量（排除已删除图片）
        creator_join_filter = '' if current_user_is_admin() else ' AND i.creator = ?'
        params = [] if current_user_is_admin() else [current_creator()]
        cursor.execute(f'''
            SELECT
                f.id,
                f.name,
                f.extra,
                f.created_at,
                COUNT(CASE WHEN i.is_deleted IS NULL OR i.is_deleted = 0 THEN i.id END) as image_count
            FROM folders f
            LEFT JOIN images i ON f.id = i.folder_id{creator_join_filter}
            GROUP BY f.id
            ORDER BY f.created_at DESC
        ''', params)

        folders = [unassigned_meta]
        for row in cursor.fetchall():
            folders.append({
                'id': row['id'],
                'name': row['name'],
                'image_count': row['image_count'],
                'extra': json.loads(row['extra']) if row['extra'] else {},
                'created_at': row['created_at'],
                'is_virtual': False
            })

        conn.close()

        return jsonify({
            'success': True,
            'data': folders
        })

    except Exception as e:
        print(f"[FolderManager] Failed to get folders: {e}")
        return jsonify({
            'success': False,
            'message': f'获取文件夹列表失败: {str(e)}'
        }), 500


@folder_manager_bp.route('/api/folders/<folder_id>', methods=['GET'])
def get_folder_detail(folder_id):
    """
    获取单个文件夹详情

    响应：
    {
        "success": true,
        "data": {
            "id": "uuid-string",
            "name": "文件夹名称",
            "folder_path": "图片管理/文件夹名称",
            "images": [...],
            "extra": {},
            "created_at": "2024-01-01T12:00:00"
        }
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取文件夹信息
        cursor.execute('''
            SELECT id, name, extra, created_at
            FROM folders
            WHERE id = ?
        ''', (folder_id,))

        folder = cursor.fetchone()

        if not folder:
            conn.close()
            return jsonify({
                'success': False,
                'message': '文件夹不存在'
            }), 404

        # 获取文件夹中的图片（排除已删除）
        scope_sql = '' if current_user_is_admin() else ' AND creator = ?'
        params = [folder_id] if current_user_is_admin() else [folder_id, current_creator()]
        cursor.execute(f'''
            SELECT
                id, prompt, model, size, quality, aspect_ratio,
                resolution, output_format, local_url, preview_url,
                response_url, request_data, response_data, status,
                error_message, extra, created_at,
                url, thumbnail, local_path, thumbnail_path, image_type
            FROM images
            WHERE folder_id = ? AND (is_deleted IS NULL OR is_deleted = 0){scope_sql}
            ORDER BY created_at DESC
        ''', params)

        images = []
        for row in cursor.fetchall():
            images.append({
                'id': row['id'],
                'prompt': row['prompt'],
                'model': row['model'],
                'size': row['size'],
                'quality': row['quality'],
                'aspect_ratio': row['aspect_ratio'],
                'resolution': row['resolution'],
                'output_format': row['output_format'],
                'local_url': row['local_url'],
                'preview_url': row['preview_url'],
                'response_url': row['response_url'],
                'request_data': json.loads(row['request_data']) if row['request_data'] else {},
                'response_data': json.loads(row['response_data']) if row['response_data'] else {},
                'status': row['status'],
                'error_message': row['error_message'],
                'extra': json.loads(row['extra']) if row['extra'] else {},
                'created_at': row['created_at'],
                'url': row['url'],
                'thumbnail': row['thumbnail'],
                'local_path': row['local_path'],
                'thumbnail_path': row['thumbnail_path'],
                'image_type': row['image_type']
            })

        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'id': folder['id'],
                'name': folder['name'],
                'images': images,
                'extra': json.loads(folder['extra']) if folder['extra'] else {},
                'created_at': folder['created_at']
            }
        })

    except Exception as e:
        print(f"[FolderManager] Failed to get folder detail: {e}")
        return jsonify({
            'success': False,
            'message': f'获取文件夹详情失败: {str(e)}'
        }), 500


@folder_manager_bp.route('/api/folders/<folder_id>', methods=['PUT'])
def update_folder(folder_id):
    """
    更新文件夹名称

    请求体：
    {
        "name": "新文件夹名称",
        "extra": {}  // 可选，更新备用字段
    }

    响应：
    {
        "success": true,
        "data": {
            "id": "uuid-string",
            "name": "新文件夹名称",
            "folder_path": "图片管理/新文件夹名称",
            "extra": {},
            "updated_at": "2024-01-01T12:00:00"
        }
    }
    """
    try:
        data = request.get_json()
        new_name = data.get('name', '').strip()

        if not new_name:
            return jsonify({
                'success': False,
                'message': '文件夹名称不能为空'
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查文件夹是否存在
        cursor.execute('SELECT id, name, folder_path FROM folders WHERE id = ?', (folder_id,))
        folder = cursor.fetchone()
        if not folder:
            conn.close()
            return jsonify({
                'success': False,
                'message': '文件夹不存在'
            }), 404

        # 获取旧的文件夹路径
        old_folder_path = folder['folder_path']
        old_name = folder['name']

        # 重命名磁盘上的文件夹
        if old_name != new_name and old_folder_path:
            # 构建旧的绝对路径
            old_abs_path = os.path.join(IMAGE_MANAGE_DIR, old_folder_path) if not os.path.isabs(old_folder_path) else old_folder_path
            # 构建新的绝对路径
            new_abs_path = os.path.join(IMAGE_MANAGE_DIR, new_name)

            if os.path.exists(old_abs_path):
                try:
                    shutil.move(old_abs_path, new_abs_path)
                except Exception as e:
                    print(f"[FolderManager] Failed to rename folder on disk: {e}")

        # 更新数据库
        updated_at = datetime.now().isoformat()
        new_folder_path = new_name
        update_fields = []
        params = []

        if 'name' in data:
            update_fields.append('name = ?')
            params.append(new_name)
            update_fields.append('folder_path = ?')
            params.append(new_folder_path)

        if 'extra' in data:
            update_fields.append('extra = ?')
            params.append(json.dumps(data['extra']))

        update_fields.append('updated_at = ?')
        params.append(updated_at)
        params.append(folder_id)

        cursor.execute(f'''
            UPDATE folders
            SET {', '.join(update_fields)}
            WHERE id = ?
        ''', tuple(params))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'id': folder_id,
                'name': new_name,
                'folder_path': new_folder_path,
                'extra': data.get('extra', {}),
                'updated_at': updated_at
            }
        })

    except Exception as e:
        print(f"[FolderManager] Failed to update folder: {e}")
        return jsonify({
            'success': False,
            'message': f'更新文件夹失败: {str(e)}'
        }), 500


@folder_manager_bp.route('/api/folders/<folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    """
    删除文件夹

    功能描述：
        1. 将文件夹中所有图片文件从子文件夹移动到 generated_images 根目录
        2. 更新图片的 local_path、local_url、url 数据库字段，指向新位置
        3. 将图片的 folder_id 设置为 null（保留在"全部图片"中）
        4. 删除文件夹数据库记录
        5. 删除磁盘上的文件夹目录

    实现逻辑：
        1. 检查文件夹是否存在，不存在则返回 404
        2. 查询该文件夹下所有图片记录
        3. 遍历每张图片，将实际文件从子文件夹移动到 generated_images 根目录
        4. 同步更新数据库中每张图片的路径字段（local_path、local_url、url）
        5. 将 folder_id 置空，表示图片归属于"全部图片"
        6. 删除文件夹数据库记录
        7. 删除磁盘上空文件夹目录

    异常处理：
        - 文件移动失败：仍清除 folder_id，保留原路径，打印错误日志
        - 文件夹目录删除失败：仅打印错误日志，不影响接口成功返回
        - 文件名冲突：自动添加 uuid 后缀避免覆盖已有文件

    响应：
    {
        "success": true,
        "message": "文件夹「xxx」已删除，其中的图片已移至全部图片"
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查文件夹是否存在
        cursor.execute('SELECT id, name, folder_path FROM folders WHERE id = ?', (folder_id,))
        folder = cursor.fetchone()
        if not folder:
            conn.close()
            return jsonify({
                'success': False,
                'message': '文件夹不存在'
            }), 404

        folder_path = folder['folder_path']
        folder_name = folder['name']
        # 构建文件夹的绝对路径
        folder_abs_path = os.path.join(IMAGE_MANAGE_DIR, folder_path) if not os.path.isabs(folder_path) else folder_path

        # 查询该文件夹下的所有图片记录，用于后续文件移动
        cursor.execute('SELECT id, url, local_path, local_url FROM images WHERE folder_id = ?', (folder_id,))
        images_in_folder = cursor.fetchall()

        # 遍历每张图片，将实际文件从子文件夹移动到 generated_images 根目录
        for img in images_in_folder:
            # 从 local_path 或 local_url 中找到实际存在的本地文件
            source_path = ''
            for candidate in [img['local_path'], img['local_url']]:
                if candidate and os.path.isfile(candidate):
                    source_path = candidate
                    break

            if source_path:
                try:
                    filename = os.path.basename(source_path)
                    dest_path = os.path.join(IMAGE_MANAGE_DIR, filename)
                    # 处理文件名冲突：如果根目录已存在同名文件，添加 uuid 后缀
                    if os.path.exists(dest_path):
                        name, ext = os.path.splitext(filename)
                        dest_path = os.path.join(IMAGE_MANAGE_DIR, f"{name}_{uuid.uuid4().hex[:8]}{ext}")
                    shutil.move(source_path, dest_path)
                    # 同步更新数据库中图片的路径信息，并清除 folder_id
                    new_url = f"/api/static/generated_images/{os.path.basename(dest_path)}"
                    cursor.execute(
                        'UPDATE images SET local_path = ?, local_url = ?, url = ?, folder_id = NULL WHERE id = ?',
                        (dest_path, dest_path, new_url, img['id'])
                    )
                except Exception as move_err:
                    print(f"[FolderManager] 移动图片文件失败 {img['id']}: {move_err}")
                    # 文件移动失败时，仍然清除 folder_id，保留原路径作为兜底
                    cursor.execute(
                        'UPDATE images SET folder_id = NULL WHERE id = ?',
                        (img['id'],)
                    )
            else:
                # 无本地文件的图片（如仅远程URL的图片），直接清除 folder_id
                cursor.execute(
                    'UPDATE images SET folder_id = NULL WHERE id = ?',
                    (img['id'],)
                )

        # 兜底：清除可能遗漏的图片的 folder_id（例如 images_in_folder 查询后新增的）
        cursor.execute('UPDATE images SET folder_id = NULL WHERE folder_id = ?', (folder_id,))

        # 删除文件夹数据库记录
        cursor.execute('DELETE FROM folders WHERE id = ?', (folder_id,))

        conn.commit()
        conn.close()

        # 删除磁盘上的文件夹目录（此时文件夹应该已经为空或只剩无关文件）
        if os.path.exists(folder_abs_path):
            try:
                shutil.rmtree(folder_abs_path)
            except Exception as rmtree_err:
                print(f"[FolderManager] 删除文件夹磁盘目录失败: {rmtree_err}")

        return jsonify({
            'success': True,
            'message': f'文件夹「{folder_name}」已删除，其中的图片已移至未分配'
        })

    except Exception as e:
        print(f"[FolderManager] 删除文件夹失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'删除文件夹失败: {str(e)}'
        }), 500


# ==================== 图片相关接口 ====================

@folder_manager_bp.route('/api/folders/<folder_id>/images', methods=['POST'])
def add_image_to_folder(folder_id):
    """
    添加图片到文件夹

    请求体：
    {
        "prompt": "提示词",
        "model": "gpt-image-2",
        "size": "1024x1024",
        "quality": "high",
        "aspect_ratio": "1:1",
        "resolution": "2K",
        "output_format": "png",
        "local_url": "/path/to/local/image.png",
        "preview_url": "/path/to/preview/image.png",
        "response_url": "https://api.example.com/image.jpg",
        "request_data": {},
        "response_data": {},
        "status": "success",
        "error_message": null,
        "extra": {}
    }

    响应：
    {
        "success": true,
        "data": {
            "id": "uuid-string",
            "folder_id": "folder-uuid",
            ...
        }
    }
    """
    try:
        data = request.get_json()

        # 检查文件夹是否存在
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, name, folder_path FROM folders WHERE id = ?', (folder_id,))
        folder = cursor.fetchone()
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'message': '文件夹不存在'
            }), 404

        folder_name = folder['name']
        folder_path = folder['folder_path']

        # 创建图片ID
        image_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO images (
                id, folder_id, prompt, model, size, quality,
                aspect_ratio, resolution, output_format, local_url,
                preview_url, response_url, request_data, response_data,
                status, error_message, extra, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            image_id,
            folder_id,
            data.get('prompt', ''),
            data.get('model', ''),
            data.get('size', ''),
            data.get('quality', ''),
            data.get('aspect_ratio', ''),
            data.get('resolution', ''),
            data.get('output_format', ''),
            data.get('local_url', ''),
            data.get('preview_url', ''),
            data.get('response_url', ''),
            json.dumps(data.get('request_data', {})),
            json.dumps(data.get('response_data', {})),
            data.get('status', 'success'),
            data.get('error_message'),
            json.dumps(data.get('extra', {})),
            created_at
        ))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'id': image_id,
                'folder_id': folder_id,
                **data,
                'created_at': created_at
            }
        }), 201

    except Exception as e:
        print(f"[FolderManager] Failed to add image: {e}")
        return jsonify({
            'success': False,
            'message': f'添加图片失败: {str(e)}'
        }), 500


@folder_manager_bp.route('/api/folders/unassigned/images', methods=['GET'])
def get_unassigned_folder_images():
    """
    获取「未分配」虚拟文件夹下的图片列表

    功能描述：
        返回 generated_thumbnails 根目录下的所有图片
        字段结构与 /api/folders/<folder_id>/images 保持一致，
        方便前端 ImageLibrary 复用同一套展示逻辑

    实现逻辑：
        1. 扫描 thumbnails 根目录拿到文件名集合
        2. 数据库批量匹配已有记录，补全元数据
        3. 孤儿文件用虚拟对象兜底
        4. 按 created_at 降序返回

    响应：
    {
        "success": true,
        "data": [
            {
                "id": "...",
                "url": "...",
                "thumbnail": "...",
                ...
            }
        ]
    }

    失败处理：
        - 扫描失败：返回空列表，不抛错
        - 数据库查询失败：仍返回虚拟记录占位
    """
    try:
        images = list_unassigned_images()
        return jsonify({
            'success': True,
            'data': images
        })
    except Exception as e:
        print(f"[FolderManager] 获取未分配图片失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'获取未分配图片失败: {str(e)}'
        }), 500


@folder_manager_bp.route('/api/folders/<folder_id>/images', methods=['GET'])
def get_folder_images(folder_id):
    """
    获取文件夹中的图片

    响应：
    {
        "success": true,
        "data": [
            {
                "id": "uuid-string",
                "prompt": "提示词",
                "model": "gpt-image-2",
                ...
            }
        ]
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查文件夹是否存在
        cursor.execute('SELECT id FROM folders WHERE id = ?', (folder_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'message': '文件夹不存在'
            }), 404

        # 获取图片列表（排除已删除）
        # 字段集必须与 serialize_image 输出保持一致，否则前端按文件夹/全部切换时会出现
        # 字段缺失（典型问题：creator 缺失导致制作人筛选把文件夹内全部图片过滤掉）。
        # 注意：fail_reason / progress 在 tasks 表，不在 images 表，不能 SELECT。
        cursor.execute('''
            SELECT
                id, prompt, model, size, quality, aspect_ratio,
                resolution, output_format, local_url, preview_url,
                response_url, request_data, response_data, status,
                error_message, extra, created_at,
                url, thumbnail, local_path, thumbnail_path, image_type,
                task_id, title, creator, api_source,
                parent_id, folder_path, updated_at, poster_copy
            FROM images
            WHERE folder_id = ? AND (is_deleted IS NULL OR is_deleted = 0)
            ORDER BY created_at DESC
        ''', (folder_id,))

        images = []
        for row in cursor.fetchall():
            images.append({
                'id': row['id'],
                'prompt': row['prompt'],
                'model': row['model'],
                'size': row['size'],
                'quality': row['quality'],
                'aspect_ratio': row['aspect_ratio'],
                'resolution': row['resolution'],
                'output_format': row['output_format'],
                'local_url': row['local_url'],
                'preview_url': row['preview_url'],
                'response_url': row['response_url'],
                'request_data': json.loads(row['request_data']) if row['request_data'] else {},
                'response_data': json.loads(row['response_data']) if row['response_data'] else {},
                'status': row['status'],
                'error_message': row['error_message'],
                'extra': json.loads(row['extra']) if row['extra'] else {},
                'created_at': row['created_at'],
                'url': row['url'],
                'thumbnail': row['thumbnail'],
                'local_path': row['local_path'],
                'thumbnail_path': row['thumbnail_path'],
                'image_type': row['image_type'],
                'task_id': row['task_id'],
                'title': row['title'] or '',
                'creator': row['creator'] or '',
                'api_source': row['api_source'] or '',
                'parent_id': row['parent_id'],
                'folder_path': row['folder_path'] or '',
                'updated_at': row['updated_at'] or '',
                'poster_copy': row['poster_copy'] or ''
            })

        conn.close()

        return jsonify({
            'success': True,
            'data': images
        })

    except Exception as e:
        print(f"[FolderManager] Failed to get images: {e}")
        return jsonify({
            'success': False,
            'message': f'获取图片列表失败: {str(e)}'
        }), 500


@folder_manager_bp.route('/api/images/<image_id>', methods=['DELETE'])
def delete_image(image_id):
    """
    删除图片

    响应：
    {
        "success": true,
        "message": "删除成功"
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查图片是否存在，并获取其路径信息
        cursor.execute('SELECT id, local_url, folder_id FROM images WHERE id = ?', (image_id,))
        image = cursor.fetchone()
        if not image:
            conn.close()
            return jsonify({
                'success': False,
                'message': '图片不存在'
            }), 404

        local_url = image['local_url']

        # 删除数据库记录
        cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
        conn.commit()
        conn.close()

        # 删除磁盘上的图片文件（原图）
        # 注意：这里只删除原图，缩略图由其他服务管理
        if local_url:
            # local_url可能是绝对路径或相对路径
            if os.path.isabs(local_url) and os.path.exists(local_url):
                try:
                    os.remove(local_url)
                except Exception as e:
                    print(f"[FolderManager] Failed to delete image file: {e}")

        return jsonify({
            'success': True,
            'message': '删除成功'
        })

    except Exception as e:
        print(f"[FolderManager] Failed to delete image: {e}")
        return jsonify({
            'success': False,
            'message': f'删除图片失败: {str(e)}'
        }), 500


@folder_manager_bp.route('/api/images/<image_id>/move', methods=['PUT'])
def move_image(image_id):
    """
    移动图片到其他文件夹（物理移动文件 + 更新数据库 URL）

    功能描述：
        1. 将图片文件从当前位置物理移动到 generated_images/<文件夹名>/ 目录
        2. 同步更新数据库中 url、local_path、local_url 三列，确保一致性
        3. 新 URL 指向 /api/static/generated_images/<文件夹名>/<文件名>

    请求体：
    {
        "target_folder_id": "target-uuid"
    }

    响应：
    {
        "success": true,
        "data": {
            "id": "image-uuid",
            "folder_id": "target-uuid",
            "url": "...",
            "local_path": "..."
        }
    }
    """
    try:
        data = request.get_json()
        target_folder_id = data.get('target_folder_id')

        if not target_folder_id:
            return jsonify({
                'success': False,
                'message': '目标文件夹ID不能为空'
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 读取图片所有路径相关列
        scope_sql = '' if current_user_is_admin() else ' AND creator = ?'
        params = [image_id] if current_user_is_admin() else [image_id, current_creator()]
        cursor.execute(
            f'SELECT id, url, local_path, local_url, folder_id FROM images WHERE id = ?{scope_sql}',
            params
        )
        image = cursor.fetchone()
        if not image:
            conn.close()
            return jsonify({
                'success': False,
                'message': '图片不存在'
            }), 404

        # 检查目标文件夹是否存在
        cursor.execute('SELECT id, name FROM folders WHERE id = ?', (target_folder_id,))
        target_folder = cursor.fetchone()
        if not target_folder:
            conn.close()
            return jsonify({
                'success': False,
                'message': '目标文件夹不存在'
            }), 404

        target_folder_name = target_folder['name']
        source_local_path = image['local_path'] or ''
        source_local_url = image['local_url'] or ''
        source_url = image['url'] or ''

        # 尝试从 local_path 或 local_url 中找到实际存在的本地文件
        # local_path: 主生图流程填充（如 generated_images/xxx.png）
        # local_url: folder_manager 流程填充（可能为空）
        available_path = ''
        for candidate in [source_local_path, source_local_url]:
            if candidate and os.path.isfile(candidate):
                available_path = candidate
                break

        new_url = source_url
        new_local_path = source_local_path
        new_local_url = source_local_url

        if available_path:
            filename = os.path.basename(available_path)
            move_result = move_image_to_folder(available_path, target_folder_name, filename)
            if move_result.get('success'):
                new_local_path = move_result.get('new_path', available_path)
                new_local_url = new_local_path
                # 构建新 URL，指向 generated_images 目录
                relative_path = move_result.get('relative_path', '')
                new_url = f"/api/static/generated_images/{relative_path.replace(os.sep, '/')}"
        else:
            # 无本地文件（仅远程URL的图片），更新 folder_id 但保留原 URL
            pass

        # 同步更新数据库中的四列
        cursor.execute('''
            UPDATE images
            SET folder_id = ?, url = ?, local_path = ?, local_url = ?
            WHERE id = ?
        ''', (target_folder_id, new_url, new_local_path, new_local_url, image_id))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'id': image_id,
                'folder_id': target_folder_id,
                'url': new_url,
                'local_path': new_local_path
            }
        })

    except Exception as e:
        print(f"[FolderManager] 移动图片失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'移动图片失败: {str(e)}'
        }), 500


# ==================== 初始化数据库表 ====================

def init_folder_tables():
    """
    初始化文件夹相关数据库表
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 创建 folders 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            folder_path TEXT,
            extra TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # 检查并添加 folders 表的缺失字段
    cursor.execute("PRAGMA table_info(folders)")
    folder_columns = [row['name'] for row in cursor.fetchall()]
    
    if 'folder_path' not in folder_columns:
        cursor.execute('ALTER TABLE folders ADD COLUMN folder_path TEXT')
        print("[FolderManager] Added folder_path column to folders table")

    # 确保 images 表有 folder_id 字段
    cursor.execute("PRAGMA table_info(images)")
    columns = [row['name'] for row in cursor.fetchall()]

    if 'folder_id' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN folder_id TEXT')
        print("[FolderManager] Added folder_id column to images table")

    if 'aspect_ratio' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN aspect_ratio TEXT')
        print("[FolderManager] Added aspect_ratio column to images table")

    if 'resolution' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN resolution TEXT')
        print("[FolderManager] Added resolution column to images table")

    if 'output_format' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN output_format TEXT')
        print("[FolderManager] Added output_format column to images table")

    if 'local_url' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN local_url TEXT')
        print("[FolderManager] Added local_url column to images table")

    if 'preview_url' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN preview_url TEXT')
        print("[FolderManager] Added preview_url column to images table")

    if 'response_url' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN response_url TEXT')
        print("[FolderManager] Added response_url column to images table")

    if 'request_data' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN request_data TEXT')
        print("[FolderManager] Added request_data column to images table")

    if 'response_data' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN response_data TEXT')
        print("[FolderManager] Added response_data column to images table")

    if 'status' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN status TEXT')
        print("[FolderManager] Added status column to images table")

    if 'error_message' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN error_message TEXT')
        print("[FolderManager] Added error_message column to images table")

    if 'extra' not in columns:
        cursor.execute('ALTER TABLE images ADD COLUMN extra TEXT')
        print("[FolderManager] Added extra column to images table")

    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_images_folder_id ON images(folder_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_images_created_at ON images(created_at)')

    conn.commit()
    conn.close()


# 初始化表
init_folder_tables()
