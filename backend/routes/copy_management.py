"""
文案管理路由

功能描述：
    提供文案HTML文件的浏览和内容读取API接口

接口列表：
    - GET /api/copy/files - 获取所有文案文件列表（按国家分组）
    - GET /api/copy/content - 获取指定HTML文件的原始内容
"""

import os
from flask import Blueprint, request, jsonify

# 创建蓝图
copy_management_bp = Blueprint('copy_management', __name__)

# 导入服务
from services.copy_service import (
    create_copy_board,
    delete_copy_board,
    list_copy_files,
    read_copy_board,
    read_copy_html,
    rename_copy_board,
    save_country_note,
    save_copy_board,
    save_copy_html,
)


@copy_management_bp.route('/api/copy/files', methods=['GET'])
def get_copy_files():
    """
    获取文案文件列表，按国家分组

    功能描述：
        实时扫描 文案/ 目录，返回按国家分组的HTML文件列表。
        每次请求都重新扫描磁盘，不缓存。

    返回：
        成功：{"success": true, "countries": [...]}
        失败：{"success": false, "error": "..."}
    """
    try:
        result = list_copy_files()
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': result.get('error', '获取文件列表失败')}), 500
    except Exception as e:
        print(f"[CopyManagement] get_copy_files error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_management_bp.route('/api/copy/country-note', methods=['POST'])
def save_copy_country_note():
    try:
        data = request.get_json(silent=True) or {}
        country = (data.get('country') or '').strip()
        note = data.get('note', '')

        if not country:
            return jsonify({'success': False, 'error': '缺少country参数'}), 400
        if not isinstance(note, str):
            return jsonify({'success': False, 'error': 'note必须是字符串'}), 400

        result = save_country_note(country, note)
        if result.get('success'):
            return jsonify(result)
        return jsonify({'success': False, 'error': result.get('error', '保存备注失败')}), 400

    except Exception as e:
        print(f"[CopyManagement] save_copy_country_note error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_management_bp.route('/api/copy/content', methods=['GET'])
def get_copy_content():
    """
    获取指定HTML文件的原始内容

    查询参数：
        path - 相对于 文案/ 目录的文件路径，如 "土耳其/xxx.html"

    返回：
        成功：{"success": true, "content": "HTML字符串", "encoding": "utf-8"}
        失败：{"success": false, "error": "..."}
    """
    try:
        relative_path = request.args.get('path', '').strip()

        if not relative_path:
            return jsonify({'success': False, 'error': '缺少path参数'}), 400

        result = read_copy_html(relative_path)

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': result.get('error', '读取文件失败')}), 404

    except Exception as e:
        print(f"[CopyManagement] get_copy_content error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_management_bp.route('/api/copy/content', methods=['POST'])
def save_copy_content():
    """
    保存指定HTML文案文件的内容
    """
    try:
        data = request.get_json(silent=True) or {}
        relative_path = (data.get('path') or '').strip()
        content = data.get('content')

        if not relative_path:
            return jsonify({'success': False, 'error': '缺少path参数'}), 400

        if not isinstance(content, str):
            return jsonify({'success': False, 'error': '缺少content参数'}), 400

        result = save_copy_html(relative_path, content)

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': result.get('error', '保存文件失败')}), 400

    except Exception as e:
        print(f"[CopyManagement] save_copy_content error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_management_bp.route('/api/copy/boards', methods=['POST'])
def create_copy_board_file():
    try:
        data = request.get_json(silent=True) or {}
        country = (data.get('country') or '').strip()

        if not country:
            return jsonify({'success': False, 'error': '缺少country参数'}), 400

        result = create_copy_board(country)
        if result.get('success'):
            return jsonify(result)
        return jsonify({'success': False, 'error': result.get('error', '创建空白文案页失败')}), 400

    except Exception as e:
        print(f"[CopyManagement] create_copy_board_file error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_management_bp.route('/api/copy/boards/content', methods=['GET'])
def get_copy_board_content():
    try:
        relative_path = request.args.get('path', '').strip()

        if not relative_path:
            return jsonify({'success': False, 'error': '缺少path参数'}), 400

        result = read_copy_board(relative_path)
        if result.get('success'):
            return jsonify(result)
        return jsonify({'success': False, 'error': result.get('error', '读取空白文案页失败')}), 404

    except Exception as e:
        print(f"[CopyManagement] get_copy_board_content error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_management_bp.route('/api/copy/boards/content', methods=['POST'])
def save_copy_board_content():
    try:
        data = request.get_json(silent=True) or {}
        relative_path = (data.get('path') or '').strip()
        cards = data.get('cards')

        if not relative_path:
            return jsonify({'success': False, 'error': '缺少path参数'}), 400

        result = save_copy_board(relative_path, cards)
        if result.get('success'):
            return jsonify(result)
        return jsonify({'success': False, 'error': result.get('error', '保存空白文案页失败')}), 400

    except Exception as e:
        print(f"[CopyManagement] save_copy_board_content error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_management_bp.route('/api/copy/boards/content', methods=['DELETE'])
def delete_copy_board_content():
    try:
        relative_path = request.args.get('path', '').strip()

        if not relative_path:
            return jsonify({'success': False, 'error': '缺少path参数'}), 400

        result = delete_copy_board(relative_path)
        if result.get('success'):
            return jsonify(result)
        return jsonify({'success': False, 'error': result.get('error', '删除原生卡片页失败')}), 400

    except Exception as e:
        print(f"[CopyManagement] delete_copy_board_content error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_management_bp.route('/api/copy/boards/rename', methods=['POST'])
def rename_copy_board_file():
    try:
        data = request.get_json(silent=True) or {}
        relative_path = (data.get('path') or '').strip()
        new_name = (data.get('name') or '').strip()

        if not relative_path:
            return jsonify({'success': False, 'error': '缺少path参数'}), 400
        if not new_name:
            return jsonify({'success': False, 'error': '缺少name参数'}), 400

        result = rename_copy_board(relative_path, new_name)
        if result.get('success'):
            return jsonify(result)
        return jsonify({'success': False, 'error': result.get('error', '重命名原生卡片页失败')}), 400

    except Exception as e:
        print(f"[CopyManagement] rename_copy_board_file error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
