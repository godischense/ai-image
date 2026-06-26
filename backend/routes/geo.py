import os
import re
import shutil
import uuid
from datetime import datetime
from urllib.parse import quote, unquote

import requests
from flask import Blueprint, jsonify, request

from services.auth_service import current_creator, current_user_is_admin, scoped_creator
from services.creator_storage import creator_storage_dir, creator_subdir
from services.publish_compression_service import compress_image_to_publish_jpeg
from services.geo_publish_move_service import (
    backup_original_to_originals_dir,
    is_publishable_output_filename,
    restore_original_from_originals,
)


geo_bp = Blueprint('geo', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
GEO_DIR = os.path.join(PROJECT_ROOT, 'GEO')
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
PUBLISH_ROOT_NAME = '可发布'
PUBLISH_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def get_db_connection():
    from models.database import get_db_connection
    return get_db_connection()


def row_get(row, field, default=''):
    try:
        return row[field]
    except (KeyError, IndexError):
        return default


def is_image_file(filename):
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS


def normalize_folder_path(folder_path):
    folder_path = (folder_path or '').replace('\\', '/').strip('/')
    if not folder_path or folder_path == '.':
        return ''
    parts = [part for part in folder_path.split('/') if part and part not in ('.', '..')]
    return '/'.join(parts)


def get_item_relative_path(row):
    folder_path = normalize_folder_path(row_get(row, 'folder_path'))
    filename = os.path.basename(row['filename'])
    return f'{folder_path}/{filename}' if folder_path else filename


def get_item_abs_path(row):
    return os.path.join(GEO_DIR, *get_item_relative_path(row).split('/'))


def get_folder_abs_path(folder_path):
    folder_path = normalize_folder_path(folder_path)
    return os.path.join(GEO_DIR, *folder_path.split('/')) if folder_path else GEO_DIR


def _geo_scope_clause(prefix='WHERE'):
    if current_user_is_admin():
        return '', []
    return f' {prefix} creator = ?', [current_creator()]


def validate_publish_date(publish_date):
    publish_date = (publish_date or '').strip()
    if not PUBLISH_DATE_PATTERN.match(publish_date):
        return None
    try:
        datetime.strptime(publish_date, '%Y-%m-%d')
    except ValueError:
        return None
    return publish_date


def publish_folder_path(publish_date):
    return f'{PUBLISH_ROOT_NAME}/{publish_date}'


def get_publish_date_from_folder(folder_path):
    parts = normalize_folder_path(folder_path).split('/')
    if len(parts) == 2 and parts[0] == PUBLISH_ROOT_NAME:
        return validate_publish_date(parts[1])
    return None


def geo_url(relative_path):
    encoded = '/'.join(quote(part) for part in relative_path.split('/'))
    return f'/api/static/geo/{encoded}'


def unique_destination_path(directory, filename):
    os.makedirs(directory, exist_ok=True)
    base, ext = os.path.splitext(filename)
    candidate = filename
    index = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f'{base}_{index}{ext}'
        index += 1
    return os.path.join(directory, candidate), candidate


def scan_geo_images():
    files = {}
    if not os.path.exists(GEO_DIR):
        return files
    for root, dirnames, filenames in os.walk(GEO_DIR):
        dirnames[:] = [d for d in dirnames if d != '.Temp' and not d.startswith('.')]
        rel_dir = os.path.relpath(root, GEO_DIR)
        folder_path = '' if rel_dir == '.' else normalize_folder_path(rel_dir)
        for filename in filenames:
            if not is_image_file(filename):
                continue
            relative_path = f'{folder_path}/{filename}' if folder_path else filename
            files[relative_path] = {'filename': filename, 'folder_path': folder_path}
    return files


def serialize_geo_item(row):
    relative_path = get_item_relative_path(row)
    return {
        'id': row['id'],
        'filename': row['filename'],
        'folder_path': row_get(row, 'folder_path'),
        'display_name': row_get(row, 'display_name'),
        'platform': row_get(row, 'platform'),
        'publish_platform': row_get(row, 'publish_platform'),
        'score': row_get(row, 'score', 0),
        'copy_text': row_get(row, 'copy_text'),
        'copy_title': row_get(row, 'copy_title'),
        'is_usable': row_get(row, 'is_usable', 0),
        'is_publishable': row_get(row, 'is_publishable', 0),
        'publish_date': row_get(row, 'publish_date'),
        'social_copy': row_get(row, 'social_copy'),
        'publish_code': row_get(row, 'publish_code'),
        'poster_copy': row_get(row, 'poster_copy'),
        'audit_status': row_get(row, 'audit_status'),
        # 创作人字段：与 images.creator 对称，由生图/编辑链路透传或在 GEO 页面手动填写
        'creator': row_get(row, 'creator', ''),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'url': geo_url(relative_path),
    }


def publish_output_filename(filename):
    base, _ = os.path.splitext(os.path.basename(filename))
    if not base.endswith('_publish'):
        base = f'{base}_publish'
    return f'{base}.jpg'


def compress_item_file_to_publish(row, publish_date, force=False):
    # 把 row 指向的图片压缩为 _publish.jpg 并移动到目标 publish 日期目录。
    # 标记为可发布时（原图，不在 publish 目录）额外把原图备份到「可发布/_originals/」，
    # 供后续「取消发布」时恢复；跨日期移动（force=True，源是 _publish.jpg）不备份，
    # 只删除源文件即可。
    publish_date = validate_publish_date(publish_date) or datetime.now().strftime('%Y-%m-%d')
    source_path = get_item_abs_path(row)
    source_folder_path = normalize_folder_path(row_get(row, 'folder_path'))
    source_filename = os.path.basename(row['filename'])
    target_folder_path = publish_folder_path(publish_date)
    target_dir = get_folder_abs_path(target_folder_path)

    if not force and source_folder_path == target_folder_path:
        return source_filename, target_folder_path

    os.makedirs(target_dir, exist_ok=True)
    dest_path, final_filename = unique_destination_path(target_dir, publish_output_filename(source_filename))
    compress_image_to_publish_jpeg(source_path, dest_path)

    # 跨日期移动可发布图片时（源是 _publish.jpg）：删除旧位置的 _publish.jpg
    # 第一次标记为可发布时（源是原图 png/jpg）：把原图备份到 _originals
    if is_publishable_output_filename(source_filename):
        if os.path.abspath(source_path) != os.path.abspath(dest_path) and os.path.exists(source_path):
            os.remove(source_path)
    else:
        if os.path.exists(source_path) and os.path.abspath(source_path) != os.path.abspath(dest_path):
            backup_original_to_originals_dir(source_path, GEO_DIR, source_filename)
    return final_filename, target_folder_path


def move_or_compress_publish_file(row, publish_date):
    return compress_item_file_to_publish(row, publish_date, force=True)


def update_geo_row(cursor, item_id, updates):
    if not updates:
        return
    fields = []
    values = []
    for key, value in updates.items():
        fields.append(f'{key} = ?')
        values.append(value)
    values.append(item_id)
    cursor.execute(f"UPDATE geo_items SET {', '.join(fields)} WHERE id = ?", values)


def apply_publishable_file_state(cursor, row, publishable, now):
    if publishable == 1:
        publish_date = validate_publish_date(row_get(row, 'publish_date')) or datetime.now().strftime('%Y-%m-%d')
        filename, folder_path = compress_item_file_to_publish(row, publish_date)
        updates = {
            'filename': filename,
            'folder_path': folder_path,
            'is_usable': 1,
            'is_publishable': 1,
            'publish_date': publish_date,
            'updated_at': now,
        }
    else:
        # 取消发布：从「可发布/_originals/」恢复原图到 GEO 根目录，删除 publish 日期目录中的 _publish.jpg
        source_path = get_item_abs_path(row)  # _publish.jpg 在 publish 日期目录
        _, restored_filename = restore_original_from_originals(row, GEO_DIR)
        if restored_filename:
            if os.path.exists(source_path):
                os.remove(source_path)
            updates = {
                'filename': restored_filename,
                'folder_path': '',
                'is_publishable': 0,
                'publish_date': '',
                'updated_at': now,
            }
        else:
            # 兜底：找不到原图时（异常情况，可能是历史遗留数据没有备份），
            # 把 _publish.jpg 移到 GEO 根目录，保留旧行为。
            source_filename = os.path.basename(row['filename'])
            target_path, filename = unique_destination_path(GEO_DIR, source_filename)
            if os.path.exists(source_path):
                shutil.move(source_path, target_path)
            updates = {
                'filename': filename,
                'folder_path': '',
                'is_publishable': 0,
                'publish_date': '',
                'updated_at': now,
            }
    update_geo_row(cursor, row['id'], updates)


@geo_bp.route('/api/geo/list', methods=['GET'])
def list_geo_images():
    try:
        os.makedirs(GEO_DIR, exist_ok=True)
        dir_files = scan_geo_images()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM geo_items')
        db_records = {get_item_relative_path(row): row for row in cursor.fetchall()}
        now = datetime.now().isoformat()

        for relative_path, info in dir_files.items():
            if relative_path in db_records:
                continue
            item_id = str(uuid.uuid4())
            filename = info['filename']
            folder_path = info['folder_path']
            publish_date = get_publish_date_from_folder(folder_path) or ''
            is_publishable = 1 if publish_date else 0
            is_usable = 1 if publish_date else 0
            display_name = os.path.splitext(filename)[0]
            # 目录扫描新建的记录默认 creator 为空字符串，后续由用户在 GEO 页面手动填写
            cursor.execute('''
                INSERT INTO geo_items (
                    id, filename, folder_path, display_name, platform, publish_platform, score,
                    copy_text, copy_title, is_usable, is_publishable, publish_date,
                    social_copy, publish_code, poster_copy, audit_status, creator, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (item_id, filename, folder_path, display_name, '', '', 0, '', '', is_usable, is_publishable, publish_date, '', '', '', '', '', now, now))

        for relative_path, row in db_records.items():
            if relative_path not in dir_files:
                cursor.execute('DELETE FROM geo_items WHERE id = ?', (row['id'],))

        conn.commit()
        where_sql, params = _geo_scope_clause()
        cursor.execute(f'SELECT * FROM geo_items{where_sql} ORDER BY created_at DESC', params)
        images = [serialize_geo_item(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'images': images})
    except Exception as e:
        print(f'[GEO] list error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/update/<item_id>', methods=['PUT'])
def update_geo_item(item_id):
    try:
        data = request.get_json(silent=True) or {}
        # 创作人字段加入白名单，允许通过 PUT 接口直接修改
        allowed = {
            'display_name', 'platform', 'publish_platform', 'score', 'copy_text', 'copy_title',
            'is_usable', 'is_publishable', 'social_copy', 'publish_code', 'poster_copy', 'audit_status',
            'creator'
        }
        updates = {key: data[key] for key in allowed if key in data}
        now = datetime.now().isoformat()
        updates['updated_at'] = now

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'GEO 图片不存在'}), 404
        if not current_user_is_admin() and row_get(row, 'creator') != current_creator():
            conn.close()
            return jsonify({'success': False, 'error': '无权限'}), 403

        current_audit_status = row_get(row, 'audit_status')
        if current_audit_status == 'deleted':
            conn.close()
            return jsonify({'success': False, 'error': '已删除状态不可修改'}), 400

        publishable_update = None
        if 'is_publishable' in updates:
            publishable_update = 1 if int(updates.pop('is_publishable')) == 1 else 0
            if publishable_update == 0 and current_audit_status in ('reviewed', 'deleted'):
                conn.close()
                return jsonify({'success': False, 'error': '已审核后不可取消发布'}), 400

        if 'audit_status' in updates:
            audit_status = (updates.get('audit_status') or '').strip()
            if audit_status not in ('reviewed', 'deleted'):
                conn.close()
                return jsonify({'success': False, 'error': '审核状态无效'}), 400
            if audit_status == 'reviewed' and current_audit_status:
                conn.close()
                return jsonify({'success': False, 'error': '审核状态不可重复修改'}), 400
            if audit_status == 'deleted' and current_audit_status != 'reviewed':
                conn.close()
                return jsonify({'success': False, 'error': '只有已审核图片可标记已删除'}), 400

        update_geo_row(cursor, item_id, updates)
        if publishable_update is not None:
            cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
            apply_publishable_file_state(cursor, cursor.fetchone(), publishable_update, now)

        conn.commit()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        updated = cursor.fetchone()
        conn.close()
        return jsonify({'success': True, 'item': serialize_geo_item(updated)})
    except Exception as e:
        print(f'[GEO] update error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/batch-update', methods=['POST'])
def batch_update_geo_items():
    try:
        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or []
        updates = data.get('updates') or {}

        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        # 批量更新允许的字段，创作人同样纳入白名单
        allowed = {'display_name', 'platform', 'publish_platform', 'score', 'copy_text', 'copy_title', 'is_usable', 'is_publishable', 'publish_code', 'creator'}
        clean_updates = {key: updates[key] for key in allowed if key in updates}
        clean_updates['updated_at'] = now
        publishable_update = clean_updates.pop('is_publishable', None) if 'is_publishable' in clean_updates else None

        updated_items = []
        for item_id in ids:
            if not current_user_is_admin():
                cursor.execute('SELECT creator FROM geo_items WHERE id = ?', (item_id,))
                row = cursor.fetchone()
                if row and row_get(row, 'creator') != current_creator():
                    continue
            if clean_updates:
                update_geo_row(cursor, item_id, clean_updates)
            if publishable_update is not None:
                cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
                row = cursor.fetchone()
                if row:
                    apply_publishable_file_state(cursor, row, 1 if int(publishable_update) == 1 else 0, now)
            cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
            row = cursor.fetchone()
            if row:
                updated_items.append(serialize_geo_item(row))

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'items': updated_items})
    except Exception as e:
        print(f'[GEO] batch update error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/rename/<item_id>', methods=['PUT'])
def rename_geo_file(item_id):
    try:
        data = request.get_json(silent=True) or {}
        new_filename = os.path.basename((data.get('new_filename') or '').strip())
        if not new_filename or not is_image_file(new_filename):
            return jsonify({'success': False, 'error': '文件名无效'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'GEO 图片不存在'}), 404
        if not current_user_is_admin() and row_get(row, 'creator') != current_creator():
            conn.close()
            return jsonify({'success': False, 'error': '无权限'}), 403

        source_path = get_item_abs_path(row)
        folder_path = normalize_folder_path(row_get(row, 'folder_path'))
        target_path = os.path.join(get_folder_abs_path(folder_path), new_filename)
        if os.path.exists(target_path) and os.path.abspath(source_path) != os.path.abspath(target_path):
            conn.close()
            return jsonify({'success': False, 'error': '同名文件已存在'}), 400

        os.rename(source_path, target_path)
        now = datetime.now().isoformat()
        cursor.execute('UPDATE geo_items SET filename = ?, updated_at = ? WHERE id = ?', (new_filename, now, item_id))
        conn.commit()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        updated = cursor.fetchone()
        conn.close()
        return jsonify({'success': True, 'item': serialize_geo_item(updated)})
    except Exception as e:
        print(f'[GEO] rename error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/sync', methods=['POST'])
def sync_geo():
    return list_geo_images()


@geo_bp.route('/api/geo/delete/<item_id>', methods=['DELETE'])
def delete_geo_item(item_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'GEO 图片不存在'}), 404
        if not current_user_is_admin() and row_get(row, 'creator') != current_creator():
            conn.close()
            return jsonify({'success': False, 'error': '无权限'}), 403
        file_path = get_item_abs_path(row)
        if os.path.exists(file_path):
            os.remove(file_path)
        cursor.execute('DELETE FROM geo_items WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f'[GEO] delete error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/open-folder/<item_id>', methods=['GET'])
def open_geo_folder(item_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return jsonify({'success': False, 'error': 'GEO 图片不存在'}), 404
        if not current_user_is_admin() and row_get(row, 'creator') != current_creator():
            return jsonify({'success': False, 'error': '无权限'}), 403
        return jsonify({'success': True, 'path': get_item_abs_path(row)})
    except Exception as e:
        print(f'[GEO] open folder error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/publish-groups', methods=['GET'])
def get_publish_groups():
    try:
        groups = set()
        publish_root = get_folder_abs_path(PUBLISH_ROOT_NAME)
        if os.path.exists(publish_root):
            for name in os.listdir(publish_root):
                if os.path.isdir(os.path.join(publish_root, name)) and validate_publish_date(name):
                    groups.add(name)
        conn = get_db_connection()
        cursor = conn.cursor()
        if current_user_is_admin():
            cursor.execute("SELECT DISTINCT publish_date FROM geo_items WHERE publish_date IS NOT NULL AND TRIM(publish_date) != ''")
        else:
            cursor.execute("SELECT DISTINCT publish_date FROM geo_items WHERE creator = ? AND publish_date IS NOT NULL AND TRIM(publish_date) != ''", (current_creator(),))
        for row in cursor.fetchall():
            date_value = validate_publish_date(row['publish_date'])
            if date_value:
                groups.add(date_value)
        conn.close()
        return jsonify({'success': True, 'groups': sorted(groups, reverse=True)})
    except Exception as e:
        print(f'[GEO] publish groups error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/publish-groups', methods=['POST'])
def create_publish_group():
    data = request.get_json(silent=True) or {}
    publish_date = validate_publish_date(data.get('publish_date'))
    if not publish_date:
        return jsonify({'success': False, 'error': '发布日期无效'}), 400
    os.makedirs(get_folder_abs_path(publish_folder_path(publish_date)), exist_ok=True)
    return jsonify({'success': True, 'publish_date': publish_date})


@geo_bp.route('/api/geo/move-publish-group', methods=['POST'])
def move_publish_group():
    try:
        data = request.get_json(silent=True) or {}
        item_id = data.get('item_id')
        publish_date = validate_publish_date(data.get('publish_date'))
        if not item_id or not publish_date:
            return jsonify({'success': False, 'error': '参数无效'}), 400
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'GEO 图片不存在'}), 404
        if not current_user_is_admin() and row_get(row, 'creator') != current_creator():
            conn.close()
            return jsonify({'success': False, 'error': '无权限'}), 403
        filename, folder_path = move_or_compress_publish_file(row, publish_date)
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE geo_items
            SET filename = ?, folder_path = ?, publish_date = ?, is_usable = 1, is_publishable = 1, updated_at = ?
            WHERE id = ?
        ''', (filename, folder_path, publish_date, now, item_id))
        conn.commit()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        updated = cursor.fetchone()
        conn.close()
        return jsonify({
            'success': True,
            'item': serialize_geo_item(updated),
        })
    except Exception as e:
        print(f'[GEO] move publish group error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/compress-publish-group', methods=['POST'])
def compress_publish_group():
    try:
        data = request.get_json(silent=True) or {}
        publish_date = validate_publish_date(data.get('publish_date'))
        if not publish_date:
            return jsonify({'success': False, 'error': '发布日期无效'}), 400
        conn = get_db_connection()
        cursor = conn.cursor()
        if current_user_is_admin():
            cursor.execute('SELECT * FROM geo_items WHERE is_publishable = 1 AND publish_date = ?', (publish_date,))
        else:
            cursor.execute('SELECT * FROM geo_items WHERE creator = ? AND is_publishable = 1 AND publish_date = ?', (current_creator(), publish_date))
        rows = cursor.fetchall()
        now = datetime.now().isoformat()
        updated_items = []
        for row in rows:
            filename, folder_path = compress_item_file_to_publish(row, publish_date, force=True)
            cursor.execute('''
                UPDATE geo_items
                SET filename = ?, folder_path = ?, publish_date = ?, is_usable = 1, is_publishable = 1, updated_at = ?
                WHERE id = ?
            ''', (filename, folder_path, publish_date, now, row['id']))
            cursor.execute('SELECT * FROM geo_items WHERE id = ?', (row['id'],))
            updated_items.append(serialize_geo_item(cursor.fetchone()))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'items': updated_items})
    except Exception as e:
        print(f'[GEO] compress publish group error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@geo_bp.route('/api/geo/copy-from', methods=['POST'])
def copy_image_to_geo():
    try:
        data = request.get_json(silent=True) or {}
        image_url = (data.get('image_url') or '').strip()
        display_name = (data.get('display_name') or '').strip()
        platform = (data.get('platform') or '').strip()
        copy_text = (data.get('copy_text') or '').strip()
        poster_copy = (data.get('poster_copy') or '').strip()
        # 创作人字段：从请求体中读取，缺失时退到空字符串
        creator = scoped_creator(data.get('creator'))
        if not image_url:
            return jsonify({'success': False, 'error': '图片URL不能为空'}), 400

        source_path = None
        local_static_prefixes = {
            '/api/static/generated_images/': os.path.join(PROJECT_ROOT, 'generated_images'),
            '/api/static/edit_images/': os.path.join(PROJECT_ROOT, 'edit_folders'),
            '/api/static/material/': os.path.join(PROJECT_ROOT, '素材'),
            '/api/static/preparation/': os.path.join(PROJECT_ROOT, '预备'),
            '/api/static/geo/': GEO_DIR,
        }
        for prefix, dir_path in local_static_prefixes.items():
            if image_url.startswith(prefix):
                relative_name = normalize_folder_path(unquote(image_url.replace(prefix, '', 1)))
                candidate = os.path.join(dir_path, *relative_name.split('/')) if relative_name else dir_path
                if os.path.exists(candidate):
                    source_path = candidate
                    break
        if not source_path and os.path.exists(image_url):
            source_path = image_url

        original_filename = os.path.basename(source_path) if source_path else f'geo_{uuid.uuid4().hex[:8]}.png'
        if not os.path.splitext(original_filename)[1]:
            original_filename = f'{original_filename}.png'
        target_folder_path = creator_subdir(creator)
        target_dir = creator_storage_dir(GEO_DIR, creator)
        os.makedirs(target_dir, exist_ok=True)
        target_path, target_filename = unique_destination_path(target_dir, original_filename)

        if source_path:
            shutil.copy2(source_path, target_path)
        else:
            resp = requests.get(image_url, timeout=60, stream=True)
            resp.raise_for_status()
            with open(target_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

        conn = get_db_connection()
        cursor = conn.cursor()
        item_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        name_without_ext = os.path.splitext(target_filename)[0]
        # 创作人字段写入 INSERT，与 images.creator 链路对齐
        cursor.execute('''
                INSERT INTO geo_items (
                    id, filename, folder_path, display_name, platform, publish_platform, score,
                    copy_text, copy_title, is_usable, is_publishable, publish_date,
                    social_copy, publish_code, poster_copy, audit_status, creator, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (item_id, target_filename, target_folder_path, display_name or name_without_ext, platform, '', 0, copy_text, '', 0, 0, '', '', '', poster_copy, '', creator, now, now))
        conn.commit()
        cursor.execute('SELECT * FROM geo_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        conn.close()
        return jsonify({'success': True, 'item': serialize_geo_item(row), 'message': '已复制到GEO目录'})
    except Exception as e:
        print(f'[GEO] copy-from error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
