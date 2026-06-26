import base64
import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

from services.thumbnail_service import ThumbnailService


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORAGE_DIR = os.path.join(PROJECT_ROOT, 'backend', 'storage')
TEMPLATE_FILE = os.path.join(STORAGE_DIR, 'prompt_templates.json')
EXAMPLE_DIR = os.path.join(PROJECT_ROOT, 'template_examples')
THUMBNAIL_DIR = os.path.join(PROJECT_ROOT, 'template_example_thumbnails')
EXAMPLE_STATIC_PREFIX = '/api/static/template_examples'
THUMBNAIL_STATIC_PREFIX = '/api/static/template_example_thumbnails'


def _now() -> str:
    return datetime.now().isoformat()


def _ensure_dirs() -> None:
    os.makedirs(STORAGE_DIR, exist_ok=True)
    os.makedirs(EXAMPLE_DIR, exist_ok=True)
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)


def _default_data() -> Dict[str, Any]:
    now = _now()
    category_id = 'default'
    return {
        'categories': [
            {
                'id': category_id,
                'name': '默认分类',
                'sortOrder': 0,
                'createdAt': now,
                'updatedAt': now
            }
        ],
        'templates': []
    }


def _read_data() -> Dict[str, Any]:
    _ensure_dirs()
    if not os.path.exists(TEMPLATE_FILE):
        data = _default_data()
        _write_data(data)
        return data
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = _default_data()
    if not isinstance(data.get('categories'), list):
        data['categories'] = _default_data()['categories']
    if not isinstance(data.get('templates'), list):
        data['templates'] = []
    if not data['categories']:
        data['categories'] = _default_data()['categories']
    if _repair_template_data(data):
        _write_data(data)
    return data


def _write_data(data: Dict[str, Any]) -> None:
    _ensure_dirs()
    tmp_path = f'{TEMPLATE_FILE}.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, TEMPLATE_FILE)


def _clean_str(value: Any, fallback: str = '') -> str:
    if value is None:
        return fallback
    return str(value).strip()


def _repair_template_data(data: Dict[str, Any]) -> bool:
    changed = False
    seen_template_ids = set()
    category_ids = {
        _clean_str(item.get('id'))
        for item in data.get('categories', [])
        if isinstance(item, dict) and _clean_str(item.get('id'))
    }
    default_category_id = _clean_str(data['categories'][0].get('id'), 'default')

    for item in data.get('templates', []):
        if not isinstance(item, dict):
            continue
        template_id = _clean_str(item.get('id'))
        if not template_id or template_id in seen_template_ids:
            item['id'] = uuid.uuid4().hex
            template_id = item['id']
            changed = True
        seen_template_ids.add(template_id)

        category_id = _clean_str(item.get('categoryId'))
        if not category_id or category_id not in category_ids:
            item['categoryId'] = default_category_id
            changed = True

    return changed


def _clean_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _normalize_reference_images(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    refs = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        url = _clean_str(item.get('url'))
        if not url:
            continue
        refs.append({
            'id': _clean_str(item.get('id'), f'ref_{index}_{uuid.uuid4().hex[:8]}'),
            'url': url,
            'name': _clean_str(item.get('name'), '参考图'),
            'thumbnail': _clean_str(item.get('thumbnail') or item.get('thumbnailUrl') or item.get('url')),
            'size': item.get('size') or 0,
            'type': _clean_str(item.get('type'), 'image/png')
        })
    return refs


def _normalize_template(payload: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    existing = existing or {}
    now = _now()
    raw_template_id = _clean_str(existing.get('id') or payload.get('id'))
    template_id = raw_template_id or uuid.uuid4().hex
    return {
        'id': template_id,
        'categoryId': _clean_str(payload.get('categoryId'), existing.get('categoryId') or 'default'),
        'name': _clean_str(payload.get('name'), existing.get('name') or '未命名模版')[:80],
        'prompt': _clean_str(payload.get('prompt'), existing.get('prompt') or ''),
        'apiProvider': _clean_str(payload.get('apiProvider'), existing.get('apiProvider') or ''),
        'model': _clean_str(payload.get('model'), existing.get('model') or ''),
        'aspectRatio': _clean_str(payload.get('aspectRatio'), existing.get('aspectRatio') or ''),
        'resolution': _clean_str(payload.get('resolution'), existing.get('resolution') or ''),
        'quality': _clean_str(payload.get('quality'), existing.get('quality') or ''),
        'outputFormat': _clean_str(payload.get('outputFormat'), existing.get('outputFormat') or ''),
        'outputCompression': _clean_int(payload.get('outputCompression'), _clean_int(existing.get('outputCompression'), 100)),
        'background': _clean_str(payload.get('background'), existing.get('background') or ''),
        'moderation': _clean_str(payload.get('moderation'), existing.get('moderation') or ''),
        'referenceImages': _normalize_reference_images(payload.get('referenceImages', existing.get('referenceImages', []))),
        'exampleImage': _clean_str(payload.get('exampleImage'), existing.get('exampleImage') or ''),
        'exampleThumbnail': _clean_str(payload.get('exampleThumbnail'), existing.get('exampleThumbnail') or ''),
        'createdAt': existing.get('createdAt') or now,
        'updatedAt': now
    }


def list_templates() -> Dict[str, Any]:
    data = _read_data()
    data['categories'] = sorted(data['categories'], key=lambda item: item.get('sortOrder', 0))
    data['templates'] = sorted(data['templates'], key=lambda item: item.get('updatedAt', ''), reverse=True)
    return data


def create_category(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _read_data()
    now = _now()
    category = {
        'id': uuid.uuid4().hex,
        'name': _clean_str(payload.get('name'), '新分类')[:40],
        'sortOrder': _clean_int(payload.get('sortOrder'), len(data['categories'])),
        'createdAt': now,
        'updatedAt': now
    }
    data['categories'].append(category)
    _write_data(data)
    return category


def update_category(category_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _read_data()
    for category in data['categories']:
        if category.get('id') == category_id:
            if 'name' in payload:
                category['name'] = _clean_str(payload.get('name'), category.get('name') or '分类')[:40]
            if 'sortOrder' in payload:
                category['sortOrder'] = _clean_int(payload.get('sortOrder'), category.get('sortOrder', 0))
            category['updatedAt'] = _now()
            _write_data(data)
            return category
    raise ValueError('分类不存在')


def delete_category(category_id: str) -> None:
    data = _read_data()
    if len(data['categories']) <= 1:
        raise ValueError('至少保留一个分类')
    if any(item.get('categoryId') == category_id for item in data['templates']):
        raise ValueError('分类下还有模版，不能删除')
    next_categories = [item for item in data['categories'] if item.get('id') != category_id]
    if len(next_categories) == len(data['categories']):
        raise ValueError('分类不存在')
    data['categories'] = next_categories
    _write_data(data)


def create_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _read_data()
    category_ids = {item.get('id') for item in data['categories']}
    payload_id = _clean_str(payload.get('id'))
    payload_created_at = _clean_str(payload.get('createdAt'))

    if not payload_id and payload_created_at:
        for index, item in enumerate(data['templates']):
            if _clean_str(item.get('createdAt')) == payload_created_at:
                template = _normalize_template(payload, item)
                if template['categoryId'] not in category_ids:
                    template['categoryId'] = data['categories'][0]['id']
                data['templates'][index] = template
                _write_data(data)
                return template

    template = _normalize_template(payload)
    if template['categoryId'] not in category_ids:
        template['categoryId'] = data['categories'][0]['id']
    data['templates'].append(template)
    _write_data(data)
    return template


def update_template(template_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _read_data()
    category_ids = {item.get('id') for item in data['categories']}
    for index, item in enumerate(data['templates']):
        if item.get('id') == template_id:
            template = _normalize_template(payload, item)
            if template['categoryId'] not in category_ids:
                template['categoryId'] = data['categories'][0]['id']
            data['templates'][index] = template
            _write_data(data)
            return template
    raise ValueError('模版不存在')


def delete_template(template_id: str) -> None:
    data = _read_data()
    next_templates = [item for item in data['templates'] if item.get('id') != template_id]
    if len(next_templates) == len(data['templates']):
        raise ValueError('模版不存在')
    data['templates'] = next_templates
    _write_data(data)


def get_template(template_id: str) -> Dict[str, Any]:
    data = _read_data()
    for item in data['templates']:
        if item.get('id') == template_id:
            return item
    raise ValueError('模版不存在')


def _extension_from_mime(mime: str) -> str:
    mime = (mime or '').lower()
    if 'jpeg' in mime or 'jpg' in mime:
        return '.jpg'
    if 'webp' in mime:
        return '.webp'
    return '.png'


def _save_data_url(data_url: str, prefix: str) -> str:
    if not data_url.startswith('data:') or ',' not in data_url:
        raise ValueError('图片必须是 base64 Data URL')
    header, b64_part = data_url.split(',', 1)
    mime = header.split(';', 1)[0].replace('data:', '')
    ext = _extension_from_mime(mime)
    filename = f'{prefix}_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:8]}{ext}'
    path = os.path.join(EXAMPLE_DIR, filename)
    with open(path, 'wb') as f:
        f.write(base64.b64decode(b64_part))
    return path


def _save_remote_image(image_url: str, prefix: str) -> str:
    ext = '.png'
    url_without_query = image_url.split('?', 1)[0]
    if '.' in url_without_query:
        candidate = '.' + url_without_query.rsplit('.', 1)[-1].lower()
        if candidate in ('.png', '.jpg', '.jpeg', '.webp'):
            ext = candidate
    filename = f'{prefix}_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:8]}{ext}'
    path = os.path.join(EXAMPLE_DIR, filename)
    resp = requests.get(image_url, timeout=120, stream=True, proxies={'http': None, 'https': None})
    resp.raise_for_status()
    with open(path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return path


def _generate_thumbnail(source_path: str) -> Dict[str, str]:
    service = ThumbnailService(storage_dir=THUMBNAIL_DIR, max_size=(512, 512))
    result = service.generate_from_local(source_path)
    thumbnail_path = result.get('thumbnail_path') or ''
    thumbnail_name = os.path.relpath(thumbnail_path, THUMBNAIL_DIR).replace(os.sep, '/') if thumbnail_path else ''
    image_name = os.path.relpath(source_path, EXAMPLE_DIR).replace(os.sep, '/')
    return {
        'exampleImage': f'{EXAMPLE_STATIC_PREFIX}/{image_name}',
        'exampleThumbnail': f'{THUMBNAIL_STATIC_PREFIX}/{thumbnail_name}'
    }


def save_example_image(template_id: str, image_data: str) -> Dict[str, Any]:
    template = get_template(template_id)
    if image_data.startswith('data:'):
        local_path = _save_data_url(image_data, f'template_{template_id[:8]}')
    elif image_data.startswith('http://') or image_data.startswith('https://'):
        local_path = _save_remote_image(image_data, f'template_{template_id[:8]}')
    elif image_data.startswith('/api/static/'):
        local_path = _static_url_to_path(image_data)
        if not local_path:
            raise ValueError('无法解析本地图片路径')
        copied_path = os.path.join(EXAMPLE_DIR, f'template_{template_id[:8]}_{uuid.uuid4().hex[:8]}{os.path.splitext(local_path)[1] or ".png"}')
        shutil.copy2(local_path, copied_path)
        local_path = copied_path
    else:
        raise ValueError('不支持的示例图格式')
    updates = _generate_thumbnail(local_path)
    return update_template(template_id, {**template, **updates})


def _static_url_to_path(url: str) -> str:
    mappings = {
        '/api/static/generated_images/': os.path.join(PROJECT_ROOT, 'generated_images'),
        '/api/static/generated_thumbnails/': os.path.join(PROJECT_ROOT, 'generated_thumbnails'),
        '/api/static/material/': os.path.join(PROJECT_ROOT, '素材'),
        '/api/static/material_thumbnails/': os.path.join(PROJECT_ROOT, '素材缩略图'),
        '/api/static/edit_images/': os.path.join(PROJECT_ROOT, 'edit_folders'),
        '/api/static/edit_thumbnails/': os.path.join(PROJECT_ROOT, 'edit_thumbnails'),
        EXAMPLE_STATIC_PREFIX + '/': EXAMPLE_DIR,
        THUMBNAIL_STATIC_PREFIX + '/': THUMBNAIL_DIR,
    }
    for prefix, root in mappings.items():
        if url.startswith(prefix):
            relative = url.replace(prefix, '', 1).replace('/', os.sep)
            path = os.path.abspath(os.path.join(root, relative))
            root_abs = os.path.abspath(root)
            if path.startswith(root_abs) and os.path.isfile(path):
                return path
    return ''


def save_generated_example(template_id: str, image_url: str = '', b64_json: str = '') -> Dict[str, Any]:
    if b64_json:
        payload = b64_json
        if not payload.startswith('data:'):
            payload = f'data:image/png;base64,{payload}'
        return save_example_image(template_id, payload)
    if image_url:
        return save_example_image(template_id, image_url)
    raise ValueError('生成结果没有图片数据')
