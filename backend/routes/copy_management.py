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
    confirm_upload_copy_html,
    create_copy_board,
    delete_copy_board,
    list_copy_files,
    read_copy_board,
    read_copy_html,
    rename_copy_board,
    save_country_note,
    save_copy_board,
    save_copy_html,
    upload_copy_html,
)
# 协作锁服务：用于校验保存请求的 token，避免过期/被抢占的客户端继续保存
from services import copy_presence_service


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
        # 接收客户端传来的文件锁 token；用于协作场景下校验是否仍是合法编辑者
        owner_token = (data.get('token') or '').strip() or None

        if not relative_path:
            return jsonify({'success': False, 'error': '缺少path参数'}), 400

        if not isinstance(content, str):
            return jsonify({'success': False, 'error': '缺少content参数'}), 400

        # 协作 token 校验：失败直接 403 拒绝写入，避免过期/被抢占的编辑覆盖现有内容
        if owner_token is not None and not copy_presence_service.verify_save_token(relative_path, owner_token):
            return jsonify({
                'success': False,
                'error': '您的编辑会话已过期（文件锁已被释放/被抢占），请重新打开文件后再保存',
                'code': 'LOCK_EXPIRED'
            }), 403

        result = save_copy_html(relative_path, content)

        if result.get('success'):
            # 保存成功 → 广播完整内容给其他订阅者（只读用户可实时看到更新）
            copy_presence_service.broadcast(relative_path, {
                'type': 'content_update',
                'file_key': relative_path,
                'content': content,
                'by_token': owner_token or ''
            })
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
        # 接收客户端传来的文件锁 token；用于协作场景下校验是否仍是合法编辑者
        owner_token = (data.get('token') or '').strip() or None

        if not relative_path:
            return jsonify({'success': False, 'error': '缺少path参数'}), 400

        # 协作 token 校验：失败直接 403 拒绝写入，避免过期/被抢占的编辑覆盖现有内容
        if owner_token is not None and not copy_presence_service.verify_save_token(relative_path, owner_token):
            return jsonify({
                'success': False,
                'error': '您的编辑会话已过期（文件锁已被释放/被抢占），请重新打开文件后再保存',
                'code': 'LOCK_EXPIRED'
            }), 403

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


# 上传HTML文案文件
# 功能描述：
#     接收前端上传的HTML文件，自动从文件名中提取国家名称，
#     保存到对应国家文件夹下（文件夹不存在则自动创建）。
@copy_management_bp.route('/api/copy/upload-html', methods=['POST'])
def upload_copy_html_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '缺少file参数'}), 400

        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'success': False, 'error': '未选择文件'}), 400

        result = upload_copy_html(file, file.filename)
        if result.get('success'):
            return jsonify(result)
        return jsonify({'success': False, 'error': result.get('error', '上传失败')}), 400

    except Exception as e:
        print(f"[CopyManagement] upload_copy_html_file error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# 确认覆盖上传HTML文件
# 功能描述：
#     当上传的HTML文件已存在时，前端确认覆盖后调用此接口，
#     将文件内容写入覆盖已有文件。
@copy_management_bp.route('/api/copy/upload-html-confirm', methods=['POST'])
def confirm_upload_copy_html_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '缺少file参数'}), 400

        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'success': False, 'error': '未选择文件'}), 400

        data = request.form or {}
        country = (data.get('country') or '').strip()

        if not country:
            return jsonify({'success': False, 'error': '缺少country参数'}), 400

        result = confirm_upload_copy_html(file.filename, country)
        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error', '确认覆盖失败')}), 400

        safe_country = result['country']
        import os as _os
        from services.copy_service import COPY_DIR
        country_dir = _os.path.join(COPY_DIR, safe_country)
        target_path = _os.path.join(country_dir, _os.path.basename(file.filename))
        file.save(target_path)

        from datetime import datetime
        file_info = {
            'name': _os.path.basename(file.filename),
            'relative_path': f'{safe_country}/{_os.path.basename(file.filename)}',
            'modified_at': datetime.fromtimestamp(_os.path.getmtime(target_path)).isoformat(),
            'type': 'html'
        }
        return jsonify({
            'success': True,
            'file': file_info,
            'country': safe_country,
            'message': '文件已覆盖上传'
        })

    except Exception as e:
        print(f"[CopyManagement] confirm_upload_copy_html_file error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
