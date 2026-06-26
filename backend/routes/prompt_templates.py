import logging

from flask import Blueprint, jsonify, request

from services import prompt_template_service as templates


prompt_templates_bp = Blueprint('prompt_templates', __name__)
logger = logging.getLogger(__name__)


def _json_payload():
    return request.get_json(silent=True) or {}


@prompt_templates_bp.route('/api/prompt-templates', methods=['GET'])
def list_prompt_templates():
    logger.info('[PromptTemplates] GET list')
    return jsonify({'status': 'success', **templates.list_templates()}), 200


@prompt_templates_bp.route('/api/prompt-templates/categories', methods=['POST'])
def create_prompt_template_category():
    try:
        logger.info('[PromptTemplates] POST category create')
        category = templates.create_category(_json_payload())
        return jsonify({'status': 'success', 'category': category}), 201
    except ValueError as err:
        return jsonify({'error': str(err)}), 400


@prompt_templates_bp.route('/api/prompt-templates/categories/<category_id>', methods=['PUT'])
def update_prompt_template_category(category_id):
    try:
        logger.info('[PromptTemplates] PUT category id=%s', category_id)
        category = templates.update_category(category_id, _json_payload())
        return jsonify({'status': 'success', 'category': category}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 404


@prompt_templates_bp.route('/api/prompt-templates/categories/<category_id>', methods=['DELETE'])
def delete_prompt_template_category(category_id):
    try:
        logger.info('[PromptTemplates] DELETE category id=%s', category_id)
        templates.delete_category(category_id)
        return jsonify({'status': 'success'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400


@prompt_templates_bp.route('/api/prompt-templates', methods=['POST'])
def create_prompt_template():
    try:
        payload = _json_payload()
        logger.info(
            '[PromptTemplates] POST template create name=%s category=%s prompt_len=%s refs=%s',
            (payload.get('name') or '')[:40],
            payload.get('categoryId') or '',
            len(payload.get('prompt') or ''),
            len(payload.get('referenceImages') or [])
        )
        template = templates.create_template(payload)
        return jsonify({'status': 'success', 'template': template}), 201
    except ValueError as err:
        return jsonify({'error': str(err)}), 400


@prompt_templates_bp.route('/api/prompt-templates/<template_id>', methods=['PUT'])
def update_prompt_template(template_id):
    try:
        payload = _json_payload()
        logger.info(
            '[PromptTemplates] PUT template id=%s name=%s category=%s prompt_len=%s refs=%s',
            template_id,
            (payload.get('name') or '')[:40],
            payload.get('categoryId') or '',
            len(payload.get('prompt') or ''),
            len(payload.get('referenceImages') or [])
        )
        template = templates.update_template(template_id, payload)
        return jsonify({'status': 'success', 'template': template}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 404


@prompt_templates_bp.route('/api/prompt-templates/<template_id>', methods=['DELETE'])
def delete_prompt_template(template_id):
    try:
        logger.info('[PromptTemplates] DELETE template id=%s', template_id)
        templates.delete_template(template_id)
        return jsonify({'status': 'success'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 404


@prompt_templates_bp.route('/api/prompt-templates/<template_id>/example-image', methods=['POST'])
def upload_prompt_template_example(template_id):
    data = _json_payload()
    image_data = data.get('image', '')
    if not image_data:
        return jsonify({'error': '缺少 image 参数'}), 400
    try:
        logger.info(
            '[PromptTemplates] POST template example upload id=%s image_type=%s payload_len=%s',
            template_id,
            'data-url' if isinstance(image_data, str) and image_data.startswith('data:') else 'url',
            len(image_data) if isinstance(image_data, str) else 0
        )
        template = templates.save_example_image(template_id, image_data)
        return jsonify({'status': 'success', 'template': template}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    except Exception as err:
        return jsonify({'error': f'示例图保存失败: {err}'}), 500


@prompt_templates_bp.route('/api/prompt-templates/<template_id>/generate-example', methods=['POST'])
def generate_prompt_template_example(template_id):
    try:
        template = templates.get_template(template_id)
    except ValueError as err:
        return jsonify({'error': str(err)}), 404

    defaults = _json_payload()
    prompt = (template.get('prompt') or '').strip()
    if not prompt:
        return jsonify({'error': '模版提示词为空'}), 400

    api_provider = (template.get('apiProvider') or defaults.get('apiProvider') or 'openai').strip()
    model = (template.get('model') or defaults.get('model') or 'gpt-image-2').strip()
    merged_template = {**defaults, **{k: v for k, v in template.items() if v not in (None, '')}}
    size = _resolve_template_size(merged_template)
    quality = (merged_template.get('quality') or 'auto').strip()
    logger.info(
        '[PromptTemplates] POST generate-example id=%s api=%s model=%s size=%s quality=%s ratio=%s resolution=%s output=%s prompt_len=%s refs=%s',
        template_id,
        api_provider,
        model,
        size,
        quality,
        merged_template.get('aspectRatio') or '',
        merged_template.get('resolution') or '',
        merged_template.get('outputFormat') or '',
        len(prompt),
        len(merged_template.get('referenceImages') or [])
    )

    try:
        if api_provider == 'fal':
            image_url, b64_json = _generate_with_fal(merged_template, prompt, model, size, quality)
        elif api_provider == 'gptsapi':
            image_url, b64_json = _generate_with_gptsapi(merged_template, prompt)
        elif api_provider == 'apiyi':
            image_url, b64_json = _generate_with_apiyi(merged_template, prompt, model, size)
        else:
            image_url, b64_json = _generate_with_openai(merged_template, prompt, model, size, quality)

        updated = templates.save_generated_example(template_id, image_url=image_url, b64_json=b64_json)
        return jsonify({'status': 'success', 'template': updated}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    except Exception as err:
        return jsonify({'error': f'示例图生成失败: {err}'}), 500


def _resolve_template_size(template):
    size_map = {
        '1:1': {'1K': '1024x1024', '2K': '2048x2048', '4K': '2880x2880'},
        '16:9': {'1K': '1280x720', '2K': '2560x1440', '4K': '3840x2160'},
        '9:16': {'1K': '720x1280', '2K': '1440x2560', '4K': '2160x3840'},
        '4:3': {'1K': '1152x864', '2K': '2304x1728', '4K': '3264x2448'},
        '3:4': {'1K': '864x1152', '2K': '1728x2304', '4K': '2448x3264'},
        '3:2': {'1K': '1248x832', '2K': '2496x1664', '4K': '3504x2336'},
        '2:3': {'1K': '832x1248', '2K': '1664x2496', '4K': '2336x3504'},
        '5:4': {'1K': '1120x896', '2K': '2240x1792', '4K': '3200x2560'},
        '4:5': {'1K': '896x1120', '2K': '1792x2240', '4K': '2560x3200'},
        '21:9': {'1K': '1456x624', '2K': '3024x1296', '4K': '3696x1584'},
        '9:21': {'1K': '624x1456', '2K': '1296x3024', '4K': '1584x3696'},
        '2:1': {'1K': '2048x1024', '2K': '2688x1344', '4K': '3840x1920'},
        '1:2': {'1K': '1024x2048', '2K': '1344x2688', '4K': '1920x3840'},
        'wechat-cover': {'1K': '1456x624', '2K': '1456x624', '4K': '1456x624'},
        'fullscreen': {'1K': '688x1488', '2K': '1072x2336', '4K': '1760x3840'},
    }
    ratio = template.get('aspectRatio') or '9:16'
    resolution = template.get('resolution') or '1K'
    return size_map.get(ratio, size_map['9:16']).get(resolution, size_map['9:16']['1K'])


def _first_generated_image(result):
    data_items = result.get('data', [])
    if isinstance(data_items, dict):
        data_items = [data_items]
    if isinstance(data_items, list):
        for item in data_items:
            if isinstance(item, dict):
                if item.get('url') or item.get('b64_json'):
                    return item.get('url', ''), item.get('b64_json', '')
    images = result.get('images', [])
    if isinstance(images, list):
        for item in images:
            if isinstance(item, dict) and item.get('url'):
                return item.get('url', ''), ''
    return '', ''


def _generate_with_openai(template, prompt, model, size, quality):
    from routes.images import get_image_service
    service = get_image_service()
    payload_info = {
        'model': model,
        'size': size,
        'quality': quality,
        'output_format': template.get('outputFormat') or 'png',
        'background': template.get('background') or 'auto',
        'moderation': template.get('moderation') or 'auto',
        'reference_count': len(template.get('referenceImages', []) or [])
    }
    logger.info('[PromptTemplates] SEND example OpenAI payload=%s', payload_info)
    result = service.generate_image(
        prompt=prompt,
        model=model,
        size=size,
        quality=quality,
        response_format='url',
        async_mode=False,
        n=1,
        seed=0,
        moderation=template.get('moderation') or 'auto',
        background=template.get('background') or 'auto',
        output_format=template.get('outputFormat') or 'png',
        output_compression=template.get('outputCompression') or 100,
        image=[item.get('url') for item in template.get('referenceImages', []) if item.get('url')] or None
    )
    if 'error' in result:
        raise RuntimeError(result.get('error'))
    image_url, b64_json = _first_generated_image(result)
    if not image_url and not b64_json:
        raise RuntimeError('接口未返回图片')
    return image_url, b64_json


def _parse_size_to_fal_size(size):
    if isinstance(size, dict):
        return size
    if isinstance(size, str) and 'x' in size:
        w, h = size.lower().split('x', 1)
        return {'width': int(w), 'height': int(h)}
    return size


def _generate_with_fal(template, prompt, model, size, quality):
    from routes.images import get_fal_image_service
    service = get_fal_image_service()
    image_urls = [item.get('url') for item in template.get('referenceImages', []) if item.get('url')]
    fal_model = model or 'openai/gpt-image-2'
    if image_urls and not fal_model.endswith('/edit'):
        fal_model = f'{fal_model}/edit'
    payload_info = {
        'model': fal_model,
        'image_size': _parse_size_to_fal_size(size),
        'quality': quality,
        'output_format': template.get('outputFormat') or 'png',
        'num_images': 1,
        'reference_count': len(image_urls)
    }
    logger.info('[PromptTemplates] SEND example Fal payload=%s', payload_info)
    result = service.submit_generation(
        prompt=prompt,
        model=fal_model,
        image_size=_parse_size_to_fal_size(size),
        quality=quality,
        num_images=1,
        output_format=template.get('outputFormat') or 'png',
        image_urls=image_urls or None,
        seed=0,
        sync_mode=True
    )
    if 'error' in result:
        raise RuntimeError(result.get('error'))
    image_url, b64_json = _first_generated_image(result)
    if not image_url and not b64_json:
        raise RuntimeError('接口未返回图片')
    return image_url, b64_json


def _extract_url_from_any_result(result):
    def walk(value):
        if isinstance(value, dict):
            for key in ('url', 'image_url', 'output_url'):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.startswith(('http://', 'https://')):
                    return candidate
            for nested in value.values():
                found = walk(nested)
                if found:
                    return found
        if isinstance(value, list):
            for item in value:
                found = walk(item)
                if found:
                    return found
        return ''
    return walk(result)


def _generate_with_gptsapi(template, prompt):
    from routes.images import get_gptsapi_image_service
    service = get_gptsapi_image_service()
    aspect_ratio = template.get('aspectRatio') or '9:16'
    resolution = template.get('resolution') or '1K'
    refs = [item.get('url') for item in template.get('referenceImages', []) if item.get('url')]
    payload_info = {
        'aspect_ratio': aspect_ratio,
        'resolution': resolution,
        'reference_count': len(refs),
        'endpoint': 'image-edit' if refs else 'text-to-image'
    }
    logger.info('[PromptTemplates] SEND example GPTsAPI payload=%s', payload_info)
    if refs:
        result = service.image_edit(prompt=prompt, input_urls=refs, aspect_ratio=aspect_ratio, resolution=resolution)
    else:
        result = service.text_to_image(prompt=prompt, aspect_ratio=aspect_ratio, resolution=resolution)
    if 'error' in result:
        raise RuntimeError(result.get('error'))
    image_url = _extract_url_from_any_result(result)
    if not image_url:
        raise RuntimeError('GPTsAPI 未返回图片 URL')
    return image_url, ''


def _generate_with_apiyi(template, prompt, model, size):
    if template.get('referenceImages'):
        raise ValueError('APIYI 带参考图的自动示例图暂不支持，请上传示例图')
    from routes.images import get_apiyi_image_service
    api_model = (model or 'gpt-image-2-vip').replace('apiyi/', '')
    if api_model == 'gpt-image-2':
        service_base = get_apiyi_image_service()
        from services.apiyi_gpt_image2_service import ApiyiGptImage2Service
        service = ApiyiGptImage2Service(api_key=service_base.api_key, base_url=service_base.base_url)
        params = {
            'quality': template.get('quality') or 'auto',
            'output_format': template.get('outputFormat') or 'png',
            'background': template.get('background') or 'auto',
            'moderation': template.get('moderation') or 'auto',
        }
        if template.get('outputFormat') in ('jpeg', 'webp'):
            params['output_compression'] = template.get('outputCompression') or 100
        logger.info('[PromptTemplates] SEND example APIYI gpt-image-2 payload=%s', {
            'model': api_model,
            'size': size,
            **params
        })
        result = service.text_to_image(prompt=prompt, size=size, model=api_model, params=params)
    else:
        service = get_apiyi_image_service()
        logger.info('[PromptTemplates] SEND example APIYI vip payload=%s', {
            'model': api_model,
            'size': size,
            'response_format': 'b64_json'
        })
        result = service.text_to_image(prompt=prompt, size=size, model=api_model, response_format='b64_json')
    if 'error' in result:
        raise RuntimeError(result.get('error'))
    image_url, b64_json = _first_generated_image(result)
    if not image_url and not b64_json:
        raise RuntimeError('APIYI 未返回图片')
    return image_url, b64_json
