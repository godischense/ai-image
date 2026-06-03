"""
素材库路由

功能描述：
    提供素材库的API接口，包括获取素材列表、上传素材、管理文件夹等

接口列表：
    - GET /api/material/list - 获取素材图片列表
    - GET /api/material/info - 获取素材库统计信息
    - GET /api/material/folder/<folder_name> - 获取指定文件夹中的素材
    - POST /api/material/upload - 上传素材图片
    - POST /api/material/folder - 创建素材文件夹
    - DELETE /api/material/folder/<folder_name> - 删除素材文件夹
    - PUT /api/material/move - 移动素材到指定文件夹
    - PUT /api/material/rename - 重命名素材
    - PUT /api/material/manual-url - 设置/清除素材的 manual_url
    - DELETE /api/material/<filename> - 删除素材
"""

import os
from flask import Blueprint, request, jsonify
from typing import Dict, Any

# 创建蓝图
material_bp = Blueprint('material', __name__)

# 导入素材服务
from services.material_service import (
    get_material_list,
    get_material_list_with_subdirs,
    get_material_info,
    get_material_by_filename,
    get_materials_by_folder,
    upload_material,
    create_material_folder,
    delete_material_folder,
    move_material,
    delete_material,
    rename_material,
    set_manual_url,
    get_manual_url,
    remove_manual_url,
    get_folder_file_count,
    MATERIAL_DIR,
    ensure_material_dir
)


@material_bp.route('/api/material/list', methods=['GET'])
def get_materials():
    """
    获取素材图片列表

    查询参数：
    - folder: 文件夹名称（可选，空字符串表示根目录）

    响应：
    {
        "success": true,
        "data": [
            {
                "id": "图片名称.png",
                "filename": "图片名称.png",
                "name": "图片名称",
                "path": "/path/to/material/图片名称.png",
                "relative_path": "图片名称.png",
                "size": 102400,
                "size_mb": 0.1,
                "created_at": "2024-01-01T12:00:00",
                "modified_at": "2024-01-01T12:00:00",
                "extension": ".png",
                "folder": "",
                "folder_name": "根目录"
            }
        ]
    }
    """
    try:
        materials = get_material_list_with_subdirs()
        return jsonify({
            'success': True,
            'data': materials
        })
    except Exception as e:
        print(f"[Material] Failed to get material list: {e}")
        return jsonify({
            'success': False,
            'message': f'获取素材列表失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/info', methods=['GET'])
def get_info():
    """
    获取素材库统计信息

    响应：
    {
        "success": true,
        "data": {
            "file_count": 100,
            "total_size": 10485760,
            "total_size_mb": 10.0,
            "folder_count": 3,
            "folders": [
                {"name": "人物", "file_count": 30},
                {"name": "风景", "file_count": 50}
            ]
        }
    }
    """
    try:
        info = get_material_info()

        folders_with_count = []
        for folder in info.get('folders', []):
            folders_with_count.append({
                'name': folder,
                'file_count': get_folder_file_count(folder)
            })

        info['folders'] = folders_with_count

        return jsonify({
            'success': True,
            'data': info
        })
    except Exception as e:
        print(f"[Material] Failed to get material info: {e}")
        return jsonify({
            'success': False,
            'message': f'获取素材库信息失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/folder/<folder_name>', methods=['GET'])
def get_folder_materials(folder_name):
    """
    获取指定文件夹中的素材

    参数：
    - folder_name: 文件夹名称（使用 _root_ 表示根目录）

    响应：
    {
        "success": true,
        "data": [...]
    }
    """
    try:
        if folder_name == '_root_' or folder_name == '':
            materials = get_materials_by_folder('')
        else:
            materials = get_materials_by_folder(folder_name)

        return jsonify({
            'success': True,
            'data': materials
        })
    except Exception as e:
        print(f"[Material] Failed to get folder materials: {e}")
        return jsonify({
            'success': False,
            'message': f'获取文件夹素材失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/search', methods=['GET'])
def search_materials():
    """
    搜索素材

    查询参数：
    - q: 搜索关键词

    响应：
    {
        "success": true,
        "data": [...]
    }
    """
    try:
        keyword = request.args.get('q', '').strip().lower()
        materials = get_material_list_with_subdirs()

        if keyword:
            materials = [m for m in materials if keyword in m.get('name', '').lower()]

        return jsonify({
            'success': True,
            'data': materials
        })
    except Exception as e:
        print(f"[Material] Failed to search materials: {e}")
        return jsonify({
            'success': False,
            'message': f'搜索素材失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/upload', methods=['POST'])
def handle_upload():
    """
    上传素材图片

    请求：
        - file: 图片文件（multipart/form-data）
        - folder: 目标文件夹名称（可选）

    响应：
    {
        "success": true,
        "data": {
            "filename": "上传的文件名.png",
            "path": "/path/to/saved/file.png",
            "size": 102400,
            "folder": "目标文件夹"
        }
    }
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '没有上传文件'
            }), 400

        file = request.files['file']
        folder_name = request.form.get('folder', '')

        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '文件名为空'
            }), 400

        file_data = file.read()
        filename = file.filename

        result = upload_material(file_data, filename, folder_name if folder_name else None)

        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': f'上传失败: {result.get("error", "未知错误")}'
            }), 500

    except Exception as e:
        print(f"[Material] Failed to upload: {e}")
        return jsonify({
            'success': False,
            'message': f'上传失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/folder', methods=['POST'])
def handle_create_folder():
    """
    创建素材文件夹

    请求体：
    {
        "name": "文件夹名称"
    }

    响应：
    {
        "success": true,
        "data": {
            "name": "文件夹名称",
            "path": "/path/to/folder"
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

        result = create_material_folder(folder_name)

        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': f'创建失败: {result.get("error", "未知错误")}'
            }), 400

    except Exception as e:
        print(f"[Material] Failed to create folder: {e}")
        return jsonify({
            'success': False,
            'message': f'创建失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/folder/<folder_name>', methods=['DELETE'])
def handle_delete_folder(folder_name):
    """
    删除素材文件夹

    响应：
    {
        "success": true
    }
    """
    try:
        result = delete_material_folder(folder_name)

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', '删除失败')
            }), 400

    except Exception as e:
        print(f"[Material] Failed to delete folder: {e}")
        return jsonify({
            'success': False,
            'message': f'删除失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/move', methods=['PUT'])
def handle_move_material():
    """
    移动素材到指定文件夹

    请求体：
    {
        "filename": "文件名.png",
        "source_folder": "源文件夹",
        "target_folder": "目标文件夹"
    }

    响应：
    {
        "success": true,
        "data": {
            "new_path": "/path/to/new/location/file.png"
        }
    }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')
        source_folder = data.get('source_folder', '')
        target_folder = data.get('target_folder', '')

        if not filename:
            return jsonify({
                'success': False,
                'message': '文件名不能为空'
            }), 400

        result = move_material(filename, source_folder, target_folder)

        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': f'移动失败: {result.get("error", "未知错误")}'
            }), 400

    except Exception as e:
        print(f"[Material] Failed to move material: {e}")
        return jsonify({
            'success': False,
            'message': f'移动失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/rename', methods=['PUT'])
def handle_rename_material():
    """
    重命名素材

    请求体：
    {
        "filename": "旧文件名.png",
        "new_name": "新名称",
        "folder": "文件夹名称（可选）"
    }

    响应：
    {
        "success": true,
        "data": {
            "new_filename": "新名称.png",
            "new_path": "/path/to/new/file.png"
        }
    }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')
        new_name = data.get('new_name', '').strip()
        folder_name = data.get('folder', '')

        if not filename:
            return jsonify({
                'success': False,
                'message': '文件名不能为空'
            }), 400

        if not new_name:
            return jsonify({
                'success': False,
                'message': '新名称不能为空'
            }), 400

        result = rename_material(filename, new_name, folder_name if folder_name else None)

        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': f'重命名失败: {result.get("error", "未知错误")}'
            }), 400

    except Exception as e:
        print(f"[Material] Failed to rename material: {e}")
        return jsonify({
            'success': False,
            'message': f'重命名失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/manual-url', methods=['PUT'])
def handle_set_manual_url():
    """
    设置/清除素材的 manual_url

    功能描述：
        为指定素材设置手动填写的 URL，当使用素材作为参考图时优先使用此 URL
        如果 URL 为空字符串，则清除已有的 manual_url

    请求体：
    {
        "relative_path": "文件夹/文件名.png",  # 或 "文件名.png"（根目录素材）
        "url": "https://example.com/image.png"  # 手动填写的 URL，空字符串表示清除
    }

    响应：
    {
        "success": true,
        "data": {
            "relative_path": "文件夹/文件名.png",
            "manual_url": "https://example.com/image.png"
        }
    }
    """
    try:
        data = request.get_json()
        relative_path = data.get('relative_path', '').strip()
        url = data.get('url', '').strip()

        if not relative_path:
            return jsonify({
                'success': False,
                'message': 'relative_path 不能为空'
            }), 400

        result = set_manual_url(relative_path, url)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        print(f"[Material] Failed to set manual URL: {e}")
        return jsonify({
            'success': False,
            'message': f'设置手动 URL 失败: {str(e)}'
        }), 500


@material_bp.route('/api/material/<filename>', methods=['DELETE'])
def handle_delete_material(filename):
    """
    删除素材

    查询参数：
    - folder: 文件夹名称（可选，空字符串表示根目录）

    响应：
    {
        "success": true
    }
    """
    try:
        folder_name = request.args.get('folder', '')

        result = delete_material(filename, folder_name if folder_name else None)

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'删除失败: {result.get("error", "未知错误")}'
            }), 400

    except Exception as e:
        print(f"[Material] Failed to delete material: {e}")
        return jsonify({
            'success': False,
            'message': f'删除失败: {str(e)}'
        }), 500


# 确保素材目录存在
ensure_material_dir()