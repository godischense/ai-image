"""
预备成品图片路由

功能描述：
    提供预备目录中成品图片的管理API接口，包括获取图片列表、更新元数据、
    批量操作、重命名文件、同步目录等

接口列表：
    - GET /api/preparation/list - 获取所有成品图片列表（含元数据）
    - PUT /api/preparation/update/<item_id> - 更新单张图片元数据
    - POST /api/preparation/batch-update - 批量更新图片元数据
    - PUT /api/preparation/rename/<item_id> - 重命名实际文件
    - POST /api/preparation/sync - 手动同步目录与数据库
"""

import os
import uuid
import shutil
import re
from datetime import datetime
from flask import Blueprint, request, jsonify
from urllib.parse import quote

from .preparation_assign import assign_person_in_charge
from services.publish_compression_service import TARGET_PUBLISH_BYTES, compress_image_to_publish_jpeg

preparation_bp = Blueprint('preparation', __name__)

# 获取项目根目录和预备目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
PREPARATION_DIR = os.path.join(PROJECT_ROOT, '预备')

# 支持的图片扩展名
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
PUBLISH_ROOT_NAME = '可发布'
PUBLISH_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def get_db_connection():
    from models.database import get_db_connection
    return get_db_connection()

def is_image_file(filename):
    """判断文件名是否为支持的图片格式"""
    _, ext = os.path.splitext(filename)
    return ext.lower() in IMAGE_EXTENSIONS


def normalize_folder_path(folder_path):
    """Normalize a preparation-relative folder path for DB storage."""
    folder_path = (folder_path or '').replace('\\', '/').strip('/')
    if not folder_path or folder_path == '.':
        return ''
    parts = []
    for part in folder_path.split('/'):
        if not part or part in ('.', '..'):
            continue
        parts.append(part)
    return '/'.join(parts)


def row_get(row, field, default=''):
    try:
        return row[field]
    except (KeyError, IndexError):
        return default


def get_item_relative_path(row):
    folder_path = normalize_folder_path(row_get(row, 'folder_path'))
    filename = os.path.basename(row['filename'])
    return f'{folder_path}/{filename}' if folder_path else filename


def get_item_abs_path(row):
    return os.path.join(PREPARATION_DIR, *get_item_relative_path(row).split('/'))


def get_folder_abs_path(folder_path):
    folder_path = normalize_folder_path(folder_path)
    return os.path.join(PREPARATION_DIR, *folder_path.split('/')) if folder_path else PREPARATION_DIR


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
    folder_path = normalize_folder_path(folder_path)
    parts = folder_path.split('/') if folder_path else []
    if len(parts) == 2 and parts[0] == PUBLISH_ROOT_NAME:
        return validate_publish_date(parts[1])
    return None


def preparation_url(relative_path):
    encoded = '/'.join(quote(part) for part in relative_path.split('/'))
    return f'/api/static/preparation/{encoded}'


def scan_preparation_images():
    """Recursively scan preparation images, skipping hidden directories and .Temp."""
    files = {}
    if not os.path.exists(PREPARATION_DIR):
        return files
    for root, dirnames, filenames in os.walk(PREPARATION_DIR):
        dirnames[:] = [
            d for d in dirnames
            if d != '.Temp' and not d.startswith('.')
        ]
        rel_dir = os.path.relpath(root, PREPARATION_DIR)
        folder_path = '' if rel_dir == '.' else normalize_folder_path(rel_dir)
        for filename in filenames:
            if not is_image_file(filename):
                continue
            relative_path = f'{folder_path}/{filename}' if folder_path else filename
            files[relative_path] = {
                'filename': filename,
                'folder_path': folder_path,
                'relative_path': relative_path
            }
    return files


def unique_destination_path(dest_dir, filename):
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(dest_dir, filename)
    if not os.path.exists(candidate):
        return candidate, filename
    timestamp = datetime.now().strftime('%H%M%S')
    candidate_name = f'{base}_{timestamp}{ext}'
    candidate = os.path.join(dest_dir, candidate_name)
    if not os.path.exists(candidate):
        return candidate, candidate_name
    for index in range(2, 1000):
        candidate_name = f'{base}_{timestamp}_{index}{ext}'
        candidate = os.path.join(dest_dir, candidate_name)
        if not os.path.exists(candidate):
            return candidate, candidate_name
    raise RuntimeError('无法生成不重名的目标文件名')


def move_item_file(row, target_folder_path):
    target_folder_path = normalize_folder_path(target_folder_path)
    source_path = get_item_abs_path(row)
    if not os.path.exists(source_path):
        raise FileNotFoundError('原文件不存在，可能已被外部删除')
    dest_dir = get_folder_abs_path(target_folder_path)
    os.makedirs(dest_dir, exist_ok=True)
    source_folder_path = normalize_folder_path(row_get(row, 'folder_path'))
    filename = os.path.basename(row['filename'])
    if source_folder_path == target_folder_path:
        return filename, target_folder_path
    dest_path, final_filename = unique_destination_path(dest_dir, filename)
    shutil.move(source_path, dest_path)
    return final_filename, target_folder_path


def publish_output_filename(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    if not base.endswith('_publish'):
        base = f'{base}_publish'
    return f'{base}.jpg'


def is_publish_jpeg_under_target(row):
    source_path = get_item_abs_path(row)
    ext = os.path.splitext(row['filename'])[1].lower()
    return (
        ext in ('.jpg', '.jpeg')
        and os.path.exists(source_path)
        and os.path.getsize(source_path) <= TARGET_PUBLISH_BYTES
    )


def compress_item_file_to_publish(row, publish_date, force=False):
    publish_date = validate_publish_date(publish_date) or datetime.now().strftime('%Y-%m-%d')
    target_folder_path = publish_folder_path(publish_date)
    target_folder_path = normalize_folder_path(target_folder_path)
    source_folder_path = normalize_folder_path(row_get(row, 'folder_path'))
    source_filename = os.path.basename(row['filename'])
    source_path = get_item_abs_path(row)
    if not os.path.exists(source_path):
        raise FileNotFoundError('原文件不存在，可能已被外部删除')

    if not force and source_folder_path == target_folder_path and is_publish_jpeg_under_target(row):
        return source_filename, target_folder_path

    dest_dir = get_folder_abs_path(target_folder_path)
    os.makedirs(dest_dir, exist_ok=True)

    if source_folder_path == target_folder_path and os.path.splitext(source_filename)[1].lower() in ('.jpg', '.jpeg'):
        final_filename = source_filename
        dest_path = os.path.join(dest_dir, final_filename)
    else:
        dest_path, final_filename = unique_destination_path(dest_dir, publish_output_filename(source_filename))

    compress_image_to_publish_jpeg(source_path, dest_path)

    if os.path.abspath(source_path) != os.path.abspath(dest_path) and os.path.exists(source_path):
        os.remove(source_path)

    return final_filename, target_folder_path


def move_or_compress_publish_file(row, publish_date):
    publish_date = validate_publish_date(publish_date) or datetime.now().strftime('%Y-%m-%d')
    target_folder_path = publish_folder_path(publish_date)
    if is_publish_jpeg_under_target(row):
        return move_item_file(row, target_folder_path)
    return compress_item_file_to_publish(row, publish_date, force=True)


def apply_publishable_file_state(cursor, row, publishable, now):
    updates = {
        'is_publishable': publishable,
        'updated_at': now,
    }
    if publishable == 1:
        publish_date = validate_publish_date(row_get(row, 'publish_date')) or datetime.now().strftime('%Y-%m-%d')
        filename, folder_path = compress_item_file_to_publish(row, publish_date)
        updates.update({
            'is_usable': 1,
            'publish_date': publish_date,
            'folder_path': folder_path,
            'filename': filename,
        })
    else:
        filename, folder_path = move_item_file(row, '')
        updates.update({
            'publish_date': '',
            'folder_path': folder_path,
            'filename': filename,
        })
    assignments = ', '.join([f'{field} = ?' for field in updates])
    values = list(updates.values()) + [row['id']]
    cursor.execute(f'UPDATE preparation_items SET {assignments} WHERE id = ?', values)
    return updates


def serialize_preparation_item(row):
    """统一序列化预备成品记录，避免各接口漏字段。"""
    relative_path = get_item_relative_path(row)
    return {
        'id': row['id'],
        'filename': row['filename'],
        'folder_path': row_get(row, 'folder_path'),
        'relative_path': relative_path,
        'display_name': row['display_name'],
        'platform': row['platform'],
        'score': row['score'],
        'copy_text': row['copy_text'],
        'copy_title': row['copy_title'],
        'is_usable': row['is_usable'],
        'is_publishable': row['is_publishable'],
        'publish_date': row_get(row, 'publish_date'),
        'social_copy': row['social_copy'],
        'publish_code': row['publish_code'],
        'person_in_charge': row_get(row, 'person_in_charge'),
        'poster_copy': row_get(row, 'poster_copy'),
        'url': preparation_url(relative_path),
        'created_at': row['created_at'],
        'updated_at': row['updated_at']
    }

@preparation_bp.route('/api/preparation/list', methods=['GET'])
def list_preparation_images():
    """
    获取预备目录中的所有成品图片及其元数据

    功能描述：
        1. 扫描预备目录中的所有图片文件
        2. 查询数据库中已有的元数据记录
        3. 新文件自动创建数据库记录（默认元数据）
        4. 返回合并后的完整列表

    返回：
        成功：{ "success": true, "images": [...] }
        失败：{ "success": false, "error": "..." }
    """
    try:
        if not os.path.exists(PREPARATION_DIR):
            return jsonify({'success': True, 'images': []})

        # 扫描目录中的图片文件
        dir_files = scan_preparation_images()

        conn = get_db_connection()
        cursor = conn.cursor()

        # 查询数据库中所有记录
        cursor.execute('SELECT * FROM preparation_items')
        db_rows = cursor.fetchall()
        db_records = {}
        for row in db_rows:
            db_records[get_item_relative_path(row)] = dict(row)

        # 处理新文件（在目录中但不在数据库中）
        now = datetime.now().isoformat()
        for relative_path in sorted(dir_files):
            file_info = dir_files[relative_path]
            filename = file_info['filename']
            folder_path = file_info['folder_path']
            if relative_path not in db_records:
                item_id = str(uuid.uuid4())
                name_without_ext = os.path.splitext(filename)[0]
                publish_date = get_publish_date_from_folder(folder_path) or ''
                is_publishable = 1 if publish_date else 0
                is_usable = 1 if publish_date else 0
                cursor.execute('''
                    INSERT INTO preparation_items (
                        id, filename, folder_path, display_name, platform, score, copy_text, copy_title,
                        is_usable, is_publishable, publish_date, social_copy, publish_code, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (item_id, filename, folder_path, name_without_ext, '', 0, '', '', is_usable, is_publishable, publish_date, '', '', now, now))
                db_records[relative_path] = {
                    'id': item_id,
                    'filename': filename,
                    'folder_path': folder_path,
                    'display_name': name_without_ext,
                    'platform': '',
                    'score': 0,
                    'copy_text': '',
                    'copy_title': '',
                    'is_usable': is_usable,
                    'is_publishable': is_publishable,
                    'publish_date': publish_date,
                    'social_copy': '',
                    'publish_code': '',
                    'created_at': now,
                    'updated_at': now
                }

        # 处理已删除的文件（在数据库中但不在目录中）
        deleted_files = set(db_records.keys()) - set(dir_files.keys())
        for relative_path in deleted_files:
            cursor.execute('DELETE FROM preparation_items WHERE id = ?', (db_records[relative_path]['id'],))
            del db_records[relative_path]

        conn.commit()

        # 对已有文案但无负责人的记录进行自动分配
        # 因为自动分配功能只会在更新接口触发，历史数据可能没有负责人
        auto_assign_needed = False
        for record in db_records.values():
            current_person = record.get('person_in_charge', '')
            if current_person:
                continue
            # 收集需要检查的文本（海报文案和生图提示词）
            check_texts = []
            poster_copy = record.get('poster_copy', '')
            copy_text = record.get('copy_text', '')
            if poster_copy:
                check_texts.append(str(poster_copy))
            if copy_text:
                check_texts.append(str(copy_text))
            if not check_texts:
                continue
            # 尝试自动分配负责人
            for text in check_texts:
                assigned = assign_person_in_charge(text)
                if assigned:
                    record['person_in_charge'] = assigned
                    cursor.execute(
                        'UPDATE preparation_items SET person_in_charge = ?, updated_at = ? WHERE id = ?',
                        (assigned, now, record['id'])
                    )
                    auto_assign_needed = True
                    break

        if auto_assign_needed:
            conn.commit()

        # 构建返回结果
        images = []
        for relative_path in sorted(dir_files):
            if relative_path in db_records:
                record = db_records[relative_path]
                images.append(serialize_preparation_item(record))

        conn.close()
        return jsonify({'success': True, 'images': images})

    except Exception as e:
        print(f"[Preparation] list error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/update/<item_id>', methods=['PUT'])
def update_preparation_item(item_id):
    """
    更新单张成品图片的元数据

    功能描述：
        更新图片的 display_name、platform、score、copy_text 等字段

    请求体 JSON:
        {
            "display_name": "可选，展示名称",
            "platform": "可选，平台名称",
            "score": 可选，评分(0-100),
            "copy_text": "可选，文案分组"
        }

    返回：
        成功：{ "success": true, "item": {...} }
        失败：{ "success": false, "error": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查记录是否存在
        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': '记录不存在'}), 404

        # 构建更新字段
        update_data = dict(data)
        if 'is_publishable' in update_data:
            try:
                publishable = int(update_data['is_publishable'])
                if publishable not in (0, 1):
                    conn.close()
                    return jsonify({'success': False, 'error': '可发布状态值无效'}), 400
                update_data['is_publishable'] = publishable
                if publishable == 1:
                    update_data['is_usable'] = 1
            except (ValueError, TypeError):
                conn.close()
                return jsonify({'success': False, 'error': '可发布状态必须是数字'}), 400

        if 'is_usable' in update_data:
            try:
                usable = int(update_data['is_usable'])
                if usable not in (0, 1):
                    conn.close()
                    return jsonify({'success': False, 'error': '可用状态值无效'}), 400
                update_data['is_usable'] = usable
                if usable == 0:
                    update_data['is_publishable'] = 0
            except (ValueError, TypeError):
                conn.close()
                return jsonify({'success': False, 'error': '可用状态必须是数字'}), 400

        update_fields = []
        update_values = []
        allowed_fields = {
            'display_name', 'platform', 'score', 'copy_text', 'copy_title', 'is_usable',
            'is_publishable', 'social_copy', 'publish_code', 'person_in_charge', 'poster_copy'
        }
        publishable_update = update_data.pop('is_publishable', None) if 'is_publishable' in update_data else None

        for field in allowed_fields:
            if field in update_data:
                value = update_data[field]
                # 评分范围校验
                if field == 'score':
                    try:
                        value = int(value)
                        if value < 0 or value > 100:
                            conn.close()
                            return jsonify({'success': False, 'error': '评分必须在0-100之间'}), 400
                    except (ValueError, TypeError):
                        conn.close()
                        return jsonify({'success': False, 'error': '评分必须是数字'}), 400
                if field in ('publish_code', 'social_copy'):
                    value = (value or '').strip()
                update_fields.append(f'{field} = ?')
                update_values.append(value)

        if not update_fields and publishable_update is None:
            conn.close()
            return jsonify({'success': False, 'error': '没有需要更新的字段'}), 400

        # 自动分配负责人：如果更新了海报文案或生图提示词，且当前负责人为空，则尝试自动分配
        if 'person_in_charge' not in update_data and (any('poster_copy' in f for f in update_fields) or any('copy_text' in f for f in update_fields)):
            current_person = row_get(row, 'person_in_charge')
            if not current_person:
                # 收集要检查的文本
                check_texts = []
                if 'poster_copy' in update_data:
                    check_texts.append(str(update_data['poster_copy']))
                if 'copy_text' in update_data:
                    check_texts.append(str(update_data['copy_text']))
                for text in check_texts:
                    assigned = assign_person_in_charge(text)
                    if assigned:
                        update_fields.append('person_in_charge = ?')
                        update_values.append(assigned)
                        break

        now = datetime.now().isoformat()
        if update_fields:
            update_fields.append('updated_at = ?')
            update_values.append(now)
            update_values.append(item_id)

            cursor.execute(f'''
                UPDATE preparation_items
                SET {', '.join(update_fields)}
                WHERE id = ?
            ''', update_values)

        if publishable_update is not None:
            cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
            row_for_move = cursor.fetchone()
            apply_publishable_file_state(cursor, row_for_move, publishable_update, now)

        conn.commit()

        # 返回更新后的记录
        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        updated_row = cursor.fetchone()
        conn.close()

        return jsonify({
            'success': True,
            'item': serialize_preparation_item(updated_row)
        })

    except Exception as e:
        print(f"[Preparation] update error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/batch-update', methods=['POST'])
def batch_update_preparation_items():
    """
    批量更新多张成品图片的元数据

    功能描述：
        同时更新多张图片的指定字段（批量改平台、批量改评分、批量改文案）

    请求体 JSON:
        {
            "ids": ["id1", "id2", ...],
            "updates": {
                "platform": "可选，新平台",
                "score": 可选，新评分(0-100),
                "copy_text": "可选，新文案"
            }
        }

    返回：
        成功：{ "success": true, "updated_count": N, "results": [...] }
        部分失败：{ "success": true, "updated_count": N, "failed_count": M, "failed_ids": [...], "results": [...] }
        失败：{ "success": false, "error": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        ids = data.get('ids', [])
        updates = data.get('updates', {})

        if not ids:
            return jsonify({'success': False, 'error': '没有指定要更新的图片ID'}), 400
        if not updates:
            return jsonify({'success': False, 'error': '没有指定要更新的字段'}), 400

        # 校验字段
        allowed_fields = {
            'platform', 'score', 'copy_text', 'copy_title', 'is_usable',
            'is_publishable', 'social_copy', 'publish_code', 'person_in_charge', 'poster_copy'
        }
        for field in updates:
            if field not in allowed_fields:
                return jsonify({'success': False, 'error': f'不支持更新字段: {field}'}), 400

        # 校验评分
        if 'score' in updates:
            try:
                score = int(updates['score'])
                if score < 0 or score > 100:
                    return jsonify({'success': False, 'error': '评分必须在0-100之间'}), 400
                updates['score'] = score
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': '评分必须是数字'}), 400

        # 校验 is_publishable，并保持可发布从属于可用
        if 'is_publishable' in updates:
            try:
                publishable = int(updates['is_publishable'])
                if publishable not in (0, 1):
                    return jsonify({'success': False, 'error': '可发布状态值无效'}), 400
                updates['is_publishable'] = publishable
                if publishable == 1:
                    updates['is_usable'] = 1
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': '可发布状态必须是数字'}), 400

        # 校验 is_usable
        if 'is_usable' in updates:
            try:
                usable = int(updates['is_usable'])
                if usable not in (0, 1):
                    return jsonify({'success': False, 'error': '可用状态值无效'}), 400
                updates['is_usable'] = usable
                if usable == 0:
                    updates['is_publishable'] = 0
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': '可用状态必须是数字'}), 400

        if 'publish_code' in updates:
            updates['publish_code'] = (updates.get('publish_code') or '').strip()
        if 'social_copy' in updates:
            updates['social_copy'] = (updates.get('social_copy') or '').strip()

        publishable_update = updates.pop('is_publishable', None) if 'is_publishable' in updates else None

        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        updated_count = 0
        failed_ids = []
        results = []

        for item_id in ids:
            try:
                cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
                row = cursor.fetchone()
                if not row:
                    failed_ids.append(item_id)
                    results.append({'id': item_id, 'success': False, 'error': '记录不存在'})
                    continue

                update_fields = []
                update_values = []
                for field, value in updates.items():
                    update_fields.append(f'{field} = ?')
                    update_values.append(value)

                # 批量更新时自动分配负责人
                if 'person_in_charge' not in updates and ('poster_copy' in updates or 'copy_text' in updates):
                    current_person = row_get(row, 'person_in_charge')
                    if not current_person:
                        check_texts = []
                        if 'poster_copy' in updates:
                            check_texts.append(str(updates['poster_copy']))
                        if 'copy_text' in updates:
                            check_texts.append(str(updates['copy_text']))
                        for text in check_texts:
                            assigned = assign_person_in_charge(text)
                            if assigned:
                                update_fields.append('person_in_charge = ?')
                                update_values.append(assigned)
                                break

                if update_fields:
                    update_fields.append('updated_at = ?')
                    update_values.append(now)
                    update_values.append(item_id)

                    cursor.execute(f'''
                        UPDATE preparation_items
                        SET {', '.join(update_fields)}
                        WHERE id = ?
                    ''', update_values)

                if publishable_update is not None:
                    cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
                    row_for_move = cursor.fetchone()
                    apply_publishable_file_state(cursor, row_for_move, publishable_update, now)

                updated_count += 1
                results.append({'id': item_id, 'success': True})

            except Exception as item_error:
                failed_ids.append(item_id)
                results.append({'id': item_id, 'success': False, 'error': str(item_error)})

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'failed_count': len(failed_ids),
            'failed_ids': failed_ids if failed_ids else None,
            'results': results
        })

    except Exception as e:
        print(f"[Preparation] batch-update error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/generate-social-copy', methods=['POST'])
def generate_preparation_social_copy():
    """
    根据预备图片的海报文案生成朋友圈文案，并保存到 social_copy 字段。
    """
    try:
        data = request.get_json(silent=True) or {}
        item_id = (data.get('item_id') or '').strip()
        if not item_id:
            return jsonify({'success': False, 'error': 'item_id不能为空'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': '记录不存在'}), 404

        copy_text = (row_get(row, 'poster_copy') or '').strip()
        if not copy_text:
            conn.close()
            return jsonify({'success': False, 'error': '海报文案为空，无法生成朋友圈文案'}), 400

        from services.social_copy_service import generate_social_copy

        result = generate_social_copy(copy_text)
        if not result.get('success'):
            conn.close()
            return jsonify({'success': False, 'error': result.get('error') or '生成朋友圈文案失败'}), 502

        social_copy = result.get('social_copy') or ''
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE preparation_items
            SET social_copy = ?, updated_at = ?
            WHERE id = ?
        ''', (social_copy, now, item_id))
        conn.commit()

        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        updated_row = cursor.fetchone()
        conn.close()

        return jsonify({
            'success': True,
            'social_copy': social_copy,
            'item': serialize_preparation_item(updated_row)
        })
    except Exception as e:
        print(f"[Preparation] generate-social-copy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/rename/<item_id>', methods=['PUT'])
def rename_preparation_file(item_id):
    """
    重命名预备目录中的实际文件

    功能描述：
        1. 校验新文件名是否合法
        2. 检查新文件名是否已存在
        3. 执行实际文件重命名
        4. 更新数据库中的 filename 和 display_name

    请求体 JSON:
        {
            "new_filename": "新文件名（含扩展名，如 爱尔兰1-新版本.png）"
        }

    返回：
        成功：{ "success": true, "item": {...} }
        失败：{ "success": false, "error": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        new_filename = data.get('new_filename', '').strip()

        if not new_filename:
            return jsonify({'success': False, 'error': '新文件名不能为空'}), 400
        new_filename = os.path.basename(new_filename)
        if not is_image_file(new_filename):
            return jsonify({'success': False, 'error': '不支持的文件格式'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查记录是否存在
        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': '记录不存在'}), 404

        old_filename = row['filename']
        folder_path = normalize_folder_path(row_get(row, 'folder_path'))

        # 检查同一目录中的新文件名是否已存在
        cursor.execute(
            'SELECT id FROM preparation_items WHERE folder_path = ? AND filename = ? AND id != ?',
            (folder_path, new_filename, item_id)
        )
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': f'文件名 "{new_filename}" 已存在'}), 409

        old_path = get_item_abs_path(row)
        new_path = os.path.join(get_folder_abs_path(folder_path), new_filename)

        if not os.path.exists(old_path):
            conn.close()
            return jsonify({'success': False, 'error': '原文件不存在，可能已被外部删除'}), 404

        if os.path.exists(new_path):
            conn.close()
            return jsonify({'success': False, 'error': f'目标文件 "{new_filename}" 已存在于目录中'}), 409

        # 执行文件重命名
        os.rename(old_path, new_path)

        # 更新数据库
        name_without_ext = os.path.splitext(new_filename)[0]
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE preparation_items
            SET filename = ?, display_name = ?, updated_at = ?
            WHERE id = ?
        ''', (new_filename, name_without_ext, now, item_id))

        conn.commit()

        # 返回更新后的记录
        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        updated_row = cursor.fetchone()
        conn.close()

        return jsonify({
            'success': True,
            'item': serialize_preparation_item(updated_row)
        })

    except Exception as e:
        print(f"[Preparation] rename error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/sync', methods=['POST'])
def sync_preparation():
    """
    手动同步预备目录与数据库

    功能描述：
        1. 扫描预备目录，发现新文件自动添加到数据库
        2. 发现已删除文件自动从数据库移除
        3. 返回同步后的完整列表

    返回：
        成功：{ "success": true, "images": [...], "added": N, "removed": N }
        失败：{ "success": false, "error": "..." }
    """
    try:
        if not os.path.exists(PREPARATION_DIR):
            return jsonify({'success': True, 'images': [], 'added': 0, 'removed': 0})

        # 扫描目录中的图片文件
        dir_files = scan_preparation_images()

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM preparation_items')
        db_rows = cursor.fetchall()
        db_records = {}
        for row in db_rows:
            db_records[get_item_relative_path(row)] = dict(row)

        now = datetime.now().isoformat()
        added = 0
        removed = 0

        # 新增文件
        for relative_path in sorted(dir_files):
            file_info = dir_files[relative_path]
            filename = file_info['filename']
            folder_path = file_info['folder_path']
            if relative_path not in db_records:
                item_id = str(uuid.uuid4())
                name_without_ext = os.path.splitext(filename)[0]
                publish_date = get_publish_date_from_folder(folder_path) or ''
                is_publishable = 1 if publish_date else 0
                is_usable = 1 if publish_date else 0
                cursor.execute('''
                    INSERT INTO preparation_items (
                        id, filename, folder_path, display_name, platform, score, copy_text, copy_title,
                        is_usable, is_publishable, publish_date, social_copy, publish_code, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (item_id, filename, folder_path, name_without_ext, '', 0, '', '', is_usable, is_publishable, publish_date, '', '', now, now))
                db_records[relative_path] = {
                    'id': item_id,
                    'filename': filename,
                    'folder_path': folder_path,
                    'display_name': name_without_ext,
                    'platform': '',
                    'score': 0,
                    'copy_text': '',
                    'copy_title': '',
                    'is_usable': is_usable,
                    'is_publishable': is_publishable,
                    'publish_date': publish_date,
                    'social_copy': '',
                    'publish_code': '',
                    'created_at': now,
                    'updated_at': now
                }
                added += 1

        # 移除已删除文件
        deleted_filenames = set(db_records.keys()) - set(dir_files.keys())
        for relative_path in deleted_filenames:
            cursor.execute('DELETE FROM preparation_items WHERE id = ?', (db_records[relative_path]['id'],))
            del db_records[relative_path]
            removed += 1

        conn.commit()

        # 构建返回结果
        images = []
        for relative_path in sorted(dir_files):
            if relative_path in db_records:
                record = db_records[relative_path]
                images.append(serialize_preparation_item(record))

        conn.close()
        return jsonify({
            'success': True,
            'images': images,
            'added': added,
            'removed': removed
        })

    except Exception as e:
        print(f"[Preparation] sync error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/delete/<item_id>', methods=['DELETE'])
def delete_preparation_item(item_id):
    """
    删除预备成品图片记录和实际文件

    功能描述：
        1. 从数据库中删除记录
        2. 删除预备目录中的实际文件

    返回：
        成功：{ "success": true, "message": "已删除" }
        失败：{ "success": false, "error": "..." }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': '记录不存在'}), 404

        filename = row['filename']
        file_path = get_item_abs_path(row)

        # 删除数据库记录
        cursor.execute('DELETE FROM preparation_items WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()

        # 删除实际文件
        if os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({'success': True, 'message': f'已删除 {filename}'})

    except Exception as e:
        print(f"[Preparation] delete error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/open-folder/<item_id>', methods=['GET'])
def open_preparation_folder(item_id):
    """
    打开图片所在的文件夹（Windows Explorer）

    功能描述：
        根据图片ID查询其在磁盘上的实际位置，然后使用系统默认文件管理器打开其所在文件夹

    实现逻辑：
        1. 查询数据库获取图片记录
        2. 通过 get_item_abs_path 获取绝对路径
        3. 调用 os.startfile 打开文件夹
        4. 处理文件不存在等异常情况

    返回：
        成功：{ "success": true, "message": "已打开文件夹", "folder": "..." }
        失败：{ "success": false, "error": "..." }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'success': False, 'error': '记录不存在'}), 404

        file_path = get_item_abs_path(row)
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '文件不存在，可能已被外部删除'}), 404

        folder_path = os.path.dirname(file_path)
        os.startfile(folder_path)
        return jsonify({'success': True, 'message': '已打开文件夹', 'folder': folder_path})

    except Exception as e:
        print(f"[Preparation] open folder error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/publish-groups', methods=['GET'])
def get_publish_groups():
    """返回磁盘和数据库中已有的可发布日期分组。"""
    try:
        groups = set()
        publish_root = get_folder_abs_path(PUBLISH_ROOT_NAME)
        if os.path.exists(publish_root):
            for name in os.listdir(publish_root):
                abs_path = os.path.join(publish_root, name)
                if os.path.isdir(abs_path) and validate_publish_date(name):
                    groups.add(name)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT publish_date
            FROM preparation_items
            WHERE publish_date IS NOT NULL AND TRIM(publish_date) != ''
        """)
        for row in cursor.fetchall():
            date_value = validate_publish_date(row['publish_date'])
            if date_value:
                groups.add(date_value)
        conn.close()

        return jsonify({'success': True, 'groups': sorted(groups, reverse=True)})
    except Exception as e:
        print(f"[Preparation] get publish groups error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/publish-groups', methods=['POST'])
def create_publish_group():
    """创建可发布日期分组及对应目录。"""
    try:
        data = request.get_json(silent=True) or {}
        publish_date = validate_publish_date(data.get('publish_date'))
        if not publish_date:
            return jsonify({'success': False, 'error': '日期格式必须为 YYYY-MM-DD'}), 400

        os.makedirs(get_folder_abs_path(publish_folder_path(publish_date)), exist_ok=True)
        return jsonify({'success': True, 'publish_date': publish_date})
    except Exception as e:
        print(f"[Preparation] create publish group error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/move-publish-group', methods=['POST'])
def move_publish_group():
    """移动可发布图片到指定日期分组。"""
    try:
        data = request.get_json(silent=True) or {}
        item_id = (data.get('item_id') or '').strip()
        publish_date = validate_publish_date(data.get('publish_date'))
        if not item_id:
            return jsonify({'success': False, 'error': 'item_id不能为空'}), 400
        if not publish_date:
            return jsonify({'success': False, 'error': '日期格式必须为 YYYY-MM-DD'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': '记录不存在'}), 404

        filename, folder_path = move_or_compress_publish_file(row, publish_date)
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE preparation_items
            SET filename = ?, folder_path = ?, publish_date = ?,
                is_usable = 1, is_publishable = 1, updated_at = ?
            WHERE id = ?
        ''', (filename, folder_path, publish_date, now, item_id))
        conn.commit()

        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        updated_row = cursor.fetchone()
        conn.close()
        return jsonify({'success': True, 'item': serialize_preparation_item(updated_row)})
    except Exception as e:
        print(f"[Preparation] move publish group error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/compress-publish-group', methods=['POST'])
def compress_publish_group():
    """Compress all publishable images in one publish date group to JPEG files under 1MB."""
    try:
        data = request.get_json(silent=True) or {}
        publish_date = validate_publish_date(data.get('publish_date'))
        if not publish_date:
            return jsonify({'success': False, 'error': '日期格式必须为 YYYY-MM-DD'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT *
            FROM preparation_items
            WHERE is_publishable = 1 AND publish_date = ?
            ORDER BY created_at DESC
        ''', (publish_date,))
        rows = cursor.fetchall()

        now = datetime.now().isoformat()
        updated_items = []
        failed = []

        for row in rows:
            try:
                filename, folder_path = compress_item_file_to_publish(row, publish_date, force=True)
                cursor.execute('''
                    UPDATE preparation_items
                    SET filename = ?, folder_path = ?, publish_date = ?,
                        is_usable = 1, is_publishable = 1, updated_at = ?
                    WHERE id = ?
                ''', (filename, folder_path, publish_date, now, row['id']))
                cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (row['id'],))
                updated_items.append(serialize_preparation_item(cursor.fetchone()))
            except Exception as item_error:
                failed.append({
                    'id': row['id'],
                    'filename': row['filename'],
                    'error': str(item_error)
                })

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'total': len(rows),
            'compressed_count': len(updated_items),
            'failed_count': len(failed),
            'failed': failed,
            'items': updated_items
        })
    except Exception as e:
        print(f"[Preparation] compress publish group error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@preparation_bp.route('/api/preparation/copy-from', methods=['POST'])
def copy_image_to_preparation():
    """
    将图片复制到预备目录并创建数据库记录

    功能描述：
        1. 接收前端传来的图片 URL 和元数据
        2. 从 URL 下载/复制图片到预备目录
        3. 在 preparation_items 表中创建记录

    请求体 JSON:
        {
            "image_url": "图片URL",
            "display_name": "展示名称",
            "platform": "平台名称",
            "copy_text": "文案内容"
        }

    返回：
        成功：{ "success": true, "item": {...} }
        失败：{ "success": false, "error": "..." }
    """
    import requests
    import uuid
    from datetime import datetime
    from urllib.parse import unquote

    try:
        data = request.get_json(silent=True) or {}
        image_url = (data.get('image_url') or '').strip()
        display_name = (data.get('display_name') or '').strip()
        platform = (data.get('platform') or '').strip()
        copy_text = (data.get('copy_text') or '').strip()
        poster_copy = (data.get('poster_copy') or '').strip()

        if not image_url:
            return jsonify({'success': False, 'error': '图片URL不能为空'}), 400

        # 确定源文件路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        source_path = None

        # 处理本地静态文件 URL (/api/static/...)
        local_static_prefixes = {
            '/api/static/generated_images/': os.path.join(project_root, 'generated_images'),
            '/api/static/edit_images/': os.path.join(project_root, 'edit_folders'),
            '/api/static/material/': os.path.join(project_root, '素材'),
            '/api/static/preparation/': PREPARATION_DIR,
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

        # 确定目标文件名
        if source_path:
            original_filename = os.path.basename(source_path)
        else:
            original_filename = f"prep_{uuid.uuid4().hex[:8]}.png"

        name_without_ext, ext = os.path.splitext(original_filename)
        if not ext:
            ext = '.png'
        target_filename = original_filename
        target_path, target_filename = unique_destination_path(PREPARATION_DIR, target_filename)

        # 如果文件名已存在，添加时间戳后缀
        name_without_ext = os.path.splitext(target_filename)[0]

        os.makedirs(PREPARATION_DIR, exist_ok=True)

        if source_path:
            import shutil
            shutil.copy2(source_path, target_path)
        else:
            # 远程 URL，下载图片
            resp = requests.get(image_url, timeout=60, stream=True)
            resp.raise_for_status()
            with open(target_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

        # 创建数据库记录
        conn = get_db_connection()
        cursor = conn.cursor()
        item_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO preparation_items (
                id, filename, folder_path, display_name, platform, score, copy_text, copy_title,
                is_usable, is_publishable, publish_date, social_copy, publish_code, poster_copy, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (item_id, target_filename, '', display_name or name_without_ext, platform, 0, copy_text, '', 0, 0, '', '', '', poster_copy, now, now))

        conn.commit()

        cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'success': False, 'error': '创建记录失败'}), 500

        return jsonify({
            'success': True,
            'item': serialize_preparation_item(row),
            'message': f'已复制到预备目录'
        })

    except Exception as e:
        print(f"[Preparation] copy-from error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
