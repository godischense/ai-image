"""
文案文件管理服务

功能描述：
    提供文案目录下HTML文件的列表扫描和内容读取功能。
    不负责HTML解析，解析工作在前端浏览器端完成。
"""
import json
import os
import uuid
from datetime import datetime


# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
# 文案目录
COPY_DIR = os.path.join(PROJECT_ROOT, '文案')
ROOT_BOARD_GROUP_NAME = '原生卡片'
ROOT_BOARD_COUNTRY = '__root__'
COUNTRY_NOTES_FILENAME = '.country-notes.json'
COUNTRY_NOTES_PATH = os.path.join(COPY_DIR, COUNTRY_NOTES_FILENAME)


def _resolve_copy_path(relative_path, required_suffix=None):
    if not relative_path:
        return None, '文件路径不能为空'

    safe_path = os.path.normpath(relative_path)
    if safe_path.startswith('..') or os.path.isabs(safe_path):
        return None, '非法的文件路径'

    if required_suffix and not safe_path.lower().endswith(required_suffix):
        return None, f'只能保存{required_suffix}文件'

    file_path = os.path.join(COPY_DIR, safe_path)
    real_path = os.path.realpath(file_path)
    real_copy_dir = os.path.realpath(COPY_DIR)
    try:
        if os.path.commonpath([real_path, real_copy_dir]) != real_copy_dir:
            return None, '非法的文件路径'
    except ValueError:
        return None, '非法的文件路径'

    return file_path, None


def _resolve_copy_html_path(relative_path):
    return _resolve_copy_path(relative_path, '.html')


def _resolve_copy_board_path(relative_path):
    return _resolve_copy_path(relative_path, '.copy.json')


def _get_country_dir(country):
    country_name = (country or '').strip()
    if not country_name:
        return None, None, '国家不能为空'

    safe_name = os.path.normpath(country_name)
    if safe_name.startswith('..') or os.path.isabs(safe_name) or os.sep in safe_name or (os.altsep and os.altsep in safe_name):
        return None, None, '非法的国家名称'

    country_dir = os.path.join(COPY_DIR, safe_name)
    real_country_dir = os.path.realpath(country_dir)
    real_copy_dir = os.path.realpath(COPY_DIR)
    try:
        if os.path.commonpath([real_country_dir, real_copy_dir]) != real_copy_dir:
            return None, None, '非法的国家名称'
    except ValueError:
        return None, None, '非法的国家名称'

    if not os.path.isdir(country_dir):
        return None, None, '国家目录不存在'

    return safe_name, country_dir, None


def _read_html_with_encoding(file_path):
    for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue
    return None, None


def _is_valid_html_content(content):
    if not isinstance(content, str) or not content.strip():
        return False
    lowered = content.lower()
    return '<html' in lowered or '<body' in lowered or '<!doctype html' in lowered


def _make_file_payload(country, filename, file_path, file_type):
    relative_path = filename if country == ROOT_BOARD_COUNTRY else os.path.join(country, filename)
    return {
        'name': filename,
        'relative_path': relative_path,
        'modified_at': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
        'type': file_type
    }


def _read_country_notes():
    if not os.path.exists(COUNTRY_NOTES_PATH):
        return {}
    try:
        with open(COUNTRY_NOTES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[CopyService] read country notes error: {e}")
        return {}


def _write_country_notes(notes):
    os.makedirs(COPY_DIR, exist_ok=True)
    with open(COUNTRY_NOTES_PATH, 'w', encoding='utf-8', newline='') as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


def _get_country_note(notes, country_key):
    note = notes.get(country_key, '')
    return note if isinstance(note, str) else ''


def save_country_note(country, note):
    try:
        country_key = (country or '').strip()
        if not country_key:
            return {'success': False, 'error': '缺少country参数'}
        if not isinstance(note, str):
            return {'success': False, 'error': 'note必须是字符串'}

        if country_key != ROOT_BOARD_COUNTRY:
            _, _, error = _get_country_dir(country_key)
            if error:
                return {'success': False, 'error': error}

        notes = _read_country_notes()
        next_note = note
        if next_note.strip():
            notes[country_key] = next_note
        else:
            notes.pop(country_key, None)
        _write_country_notes(notes)
        return {'success': True, 'country': country_key, 'note': next_note}

    except Exception as e:
        print(f"[CopyService] save_country_note error: {e}")
        return {'success': False, 'error': str(e)}


def _normalize_board_cards(cards):
    if not isinstance(cards, list):
        return None, 'cards必须是数组'

    now = datetime.now().isoformat()
    normalized = []
    for card in cards:
        if not isinstance(card, dict):
            return None, '卡片格式不正确'

        content = card.get('content')
        if not isinstance(content, str):
            return None, '卡片内容必须是字符串'

        normalized.append({
            'id': str(card.get('id') or uuid.uuid4()),
            'content': content,
            'created_at': str(card.get('created_at') or now),
            'updated_at': str(card.get('updated_at') or now),
            'made': bool(card.get('made', False)),
            'reviewed': bool(card.get('reviewed', False))
        })

    return normalized, None


def list_copy_files():
    """
    扫描文案目录，返回按国家分组的HTML文件列表

    功能描述：
        遍历 文案/ 目录下的所有子目录（每个子目录代表一个国家），
        收集其中的 .html 文件，忽略 .WeDrive 文件。
        每次调用都实时扫描磁盘，不缓存。

    返回：
        {
            "success": True,
            "countries": [
                {
                    "name": "土耳其",
                    "files": [
                        {
                            "name": "土耳其2026年5月13日（已完善）.html",
                            "relative_path": "土耳其/土耳其2026年5月13日（已完善）.html",
                            "modified_at": "2026-05-13T12:00:00"
                        }
                    ]
                }
            ]
        }
    """
    try:
        if not os.path.exists(COPY_DIR):
            return {'success': True, 'countries': []}

        countries = []
        root_board_files = []
        country_notes = _read_country_notes()

        for filename in sorted(os.listdir(COPY_DIR)):
            file_path = os.path.join(COPY_DIR, filename)
            if not os.path.isfile(file_path):
                continue
            if not filename.lower().endswith('.copy.json'):
                continue
            root_board_files.append(_make_file_payload(ROOT_BOARD_COUNTRY, filename, file_path, 'copy_board'))

        if root_board_files:
            countries.append({
                'name': ROOT_BOARD_GROUP_NAME,
                'country': ROOT_BOARD_COUNTRY,
                'note': _get_country_note(country_notes, ROOT_BOARD_COUNTRY),
                'files': root_board_files
            })

        # 遍历文案目录下的所有子目录
        for entry in sorted(os.listdir(COPY_DIR)):
            country_path = os.path.join(COPY_DIR, entry)
            # 只处理目录，跳过文件和非目录项
            if not os.path.isdir(country_path):
                continue

            files = []
            for filename in sorted(os.listdir(country_path)):
                file_path = os.path.join(country_path, filename)
                # 跳过非HTML文件和非文件项
                if not os.path.isfile(file_path):
                    continue
                lower_filename = filename.lower()
                if not (lower_filename.endswith('.html') or lower_filename.endswith('.copy.json')):
                    continue

                # 获取文件修改时间
                file_type = 'copy_board' if lower_filename.endswith('.copy.json') else 'html'
                files.append(_make_file_payload(entry, filename, file_path, file_type))

            if files:
                countries.append({
                    'name': entry,
                    'note': _get_country_note(country_notes, entry),
                    'files': files
                })

        return {'success': True, 'countries': countries}

    except Exception as e:
        print(f"[CopyService] list_copy_files error: {e}")
        return {'success': False, 'error': str(e)}


def read_copy_html(relative_path):
    """
    根据相对路径读取HTML文件的原始内容

    功能描述：
        1. 拼接完整文件路径
        2. 安全检查：防止路径遍历攻击
        3. 读取文件内容，返回原始HTML字符串

    参数：
        relative_path: 相对于 文案/ 目录的文件路径，如 "土耳其/xxx.html"

    返回：
        成功：{"success": True, "content": "HTML字符串", "encoding": "utf-8"}
        失败：{"success": False, "error": "错误信息"}
    """
    try:
        file_path, error = _resolve_copy_html_path(relative_path)
        if error:
            return {'success': False, 'error': error}

        if not os.path.exists(file_path):
            return {'success': False, 'error': f'文件不存在: {relative_path}'}

        if not os.path.isfile(file_path):
            return {'success': False, 'error': f'不是一个文件: {relative_path}'}

        # 尝试多种编码读取文件
        content, used_encoding = _read_html_with_encoding(file_path)

        if content is None:
            return {'success': False, 'error': '无法识别文件编码'}

        return {
            'success': True,
            'content': content,
            'encoding': used_encoding
        }

    except Exception as e:
        print(f"[CopyService] read_copy_html error: {e}")
        return {'success': False, 'error': str(e)}


def save_copy_html(relative_path, content):
    """
    保存编辑后的HTML文案文件。前端负责移除运行时编辑控件，
    后端只做路径、文件类型和基础HTML内容校验。
    """
    try:
        file_path, error = _resolve_copy_html_path(relative_path)
        if error:
            return {'success': False, 'error': error}

        if not os.path.exists(file_path):
            return {'success': False, 'error': f'文件不存在: {relative_path}'}

        if not os.path.isfile(file_path):
            return {'success': False, 'error': f'不是一个文件: {relative_path}'}

        if not _is_valid_html_content(content):
            return {'success': False, 'error': 'HTML内容为空或格式不正确'}

        _, used_encoding = _read_html_with_encoding(file_path)
        if not used_encoding:
            used_encoding = 'utf-8'

        with open(file_path, 'w', encoding=used_encoding, newline='') as f:
            f.write(content)

        return {
            'success': True,
            'encoding': used_encoding,
            'modified_at': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
        }

    except Exception as e:
        print(f"[CopyService] save_copy_html error: {e}")
        return {'success': False, 'error': str(e)}


def create_copy_board(country):
    try:
        is_root_board = (country or '').strip() == ROOT_BOARD_COUNTRY
        if is_root_board:
            country_name = ROOT_BOARD_GROUP_NAME
            country_dir = COPY_DIR
        else:
            country_name, country_dir, error = _get_country_dir(country)
            if error:
                return {'success': False, 'error': error}

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        base_name = f'{country_name}-{timestamp}'
        filename = f'{base_name}.copy.json'
        file_path = os.path.join(country_dir, filename)
        counter = 1
        while os.path.exists(file_path):
            filename = f'{base_name}-{counter}.copy.json'
            file_path = os.path.join(country_dir, filename)
            counter += 1

        now = datetime.now().isoformat()
        payload = {
            'version': 1,
            'type': 'copy_board',
            'country': '' if is_root_board else country_name,
            'cards': [],
            'created_at': now,
            'updated_at': now
        }
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return {
            'success': True,
            'file': _make_file_payload(ROOT_BOARD_COUNTRY if is_root_board else country_name, filename, file_path, 'copy_board')
        }

    except Exception as e:
        print(f"[CopyService] create_copy_board error: {e}")
        return {'success': False, 'error': str(e)}


def read_copy_board(relative_path):
    try:
        file_path, error = _resolve_copy_board_path(relative_path)
        if error:
            return {'success': False, 'error': error}

        if not os.path.isfile(file_path):
            return {'success': False, 'error': f'文件不存在: {relative_path}'}

        with open(file_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)

        cards, error = _normalize_board_cards(payload.get('cards', []))
        if error:
            return {'success': False, 'error': error}

        return {
            'success': True,
            'cards': cards,
            'updated_at': payload.get('updated_at', ''),
            'created_at': payload.get('created_at', '')
        }

    except json.JSONDecodeError:
        return {'success': False, 'error': '文案页JSON格式不正确'}
    except Exception as e:
        print(f"[CopyService] read_copy_board error: {e}")
        return {'success': False, 'error': str(e)}


def save_copy_board(relative_path, cards):
    try:
        file_path, error = _resolve_copy_board_path(relative_path)
        if error:
            return {'success': False, 'error': error}

        if not os.path.isfile(file_path):
            return {'success': False, 'error': f'文件不存在: {relative_path}'}

        normalized_cards, error = _normalize_board_cards(cards)
        if error:
            return {'success': False, 'error': error}

        existing = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = {}

        now = datetime.now().isoformat()
        normalized_path = os.path.normpath(relative_path)
        country = '' if os.sep not in normalized_path else normalized_path.split(os.sep)[0]
        payload = {
            'version': 1,
            'type': 'copy_board',
            'country': existing.get('country') or country,
            'cards': normalized_cards,
            'created_at': existing.get('created_at') or now,
            'updated_at': now
        }

        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return {
            'success': True,
            'cards': normalized_cards,
            'modified_at': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
        }

    except Exception as e:
        print(f"[CopyService] save_copy_board error: {e}")
        return {'success': False, 'error': str(e)}


def delete_copy_board(relative_path):
    try:
        file_path, error = _resolve_copy_board_path(relative_path)
        if error:
            return {'success': False, 'error': error}

        if not os.path.isfile(file_path):
            return {'success': False, 'error': f'文件不存在: {relative_path}'}

        os.remove(file_path)
        return {
            'success': True,
            'deleted_path': relative_path,
            'deleted_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[CopyService] delete_copy_board error: {e}")
        return {'success': False, 'error': str(e)}


def rename_copy_board(relative_path, new_name):
    try:
        file_path, error = _resolve_copy_board_path(relative_path)
        if error:
            return {'success': False, 'error': error}

        if not os.path.isfile(file_path):
            return {'success': False, 'error': f'文件不存在: {relative_path}'}

        clean_name = (new_name or '').strip()
        if not clean_name:
            return {'success': False, 'error': '新文件名不能为空'}

        if clean_name.lower().endswith('.copy.json'):
            filename = clean_name
        else:
            filename = f'{clean_name}.copy.json'

        safe_filename = os.path.normpath(filename)
        if safe_filename != filename or os.path.isabs(safe_filename) or os.sep in safe_filename or (os.altsep and os.altsep in safe_filename):
            return {'success': False, 'error': '非法的文件名'}
        if not filename.lower().endswith('.copy.json'):
            return {'success': False, 'error': '只能重命名原生卡片页'}

        target_path = os.path.join(os.path.dirname(file_path), filename)
        target_real_path = os.path.realpath(target_path)
        real_copy_dir = os.path.realpath(COPY_DIR)
        try:
            if os.path.commonpath([target_real_path, real_copy_dir]) != real_copy_dir:
                return {'success': False, 'error': '非法的文件名'}
        except ValueError:
            return {'success': False, 'error': '非法的文件名'}

        if os.path.exists(target_path):
            return {'success': False, 'error': '同名文件已存在'}

        os.rename(file_path, target_path)

        parent_dir = os.path.dirname(target_path)
        is_root_board = os.path.realpath(parent_dir) == os.path.realpath(COPY_DIR)
        country = ROOT_BOARD_COUNTRY if is_root_board else os.path.basename(parent_dir)

        return {
            'success': True,
            'file': _make_file_payload(country, filename, target_path, 'copy_board'),
            'old_path': relative_path,
            'renamed_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[CopyService] rename_copy_board error: {e}")
        return {'success': False, 'error': str(e)}
