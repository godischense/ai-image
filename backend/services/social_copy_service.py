import json
from typing import Any, Dict

import requests

from models.config_model import get_single_config


FALLBACK_SYSTEM_PROMPT = (
    '请根据用户提供的海报文案，生成适合朋友圈发布的中文文案。'
    '要求自然、有吸引力、不过度夸张，直接返回文案内容。'
)


def generate_social_copy(copy_text: str) -> Dict[str, Any]:
    text = (copy_text or '').strip()
    if not text:
        return {'success': False, 'error': '海报文案为空，无法生成朋友圈文案'}

    config = get_single_config('social_copy_api')
    base_url = (config.get('baseUrl') or '').strip().rstrip('/')
    api_key = config.get('apiKey') or ''
    model = (config.get('model') or '').strip()
    system_prompt = (config.get('systemPrompt') or '').strip() or FALLBACK_SYSTEM_PROMPT

    if not base_url or not api_key or not model:
        return {'success': False, 'error': '朋友圈文案API配置不完整，请在设置页面完善配置'}

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': text}
        ]
    }

    session = requests.Session()
    session.trust_env = False

    try:
        response = session.post(
            f'{base_url}/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=120
        )
    except requests.exceptions.Timeout:
        return {'success': False, 'error': '朋友圈文案API调用超时，请稍后重试'}
    except requests.exceptions.RequestException as exc:
        return {'success': False, 'error': f'朋友圈文案API网络错误：{exc}'}

    if response.status_code != 200:
        error_message = response.text[:1000]
        try:
            error_data = response.json()
            error_value = error_data.get('error')
            if isinstance(error_value, dict):
                error_message = error_value.get('message') or json.dumps(error_value, ensure_ascii=False)
            elif error_value:
                error_message = str(error_value)
        except ValueError:
            pass
        return {'success': False, 'error': f'朋友圈文案API返回错误 HTTP {response.status_code}：{error_message}'}

    try:
        result = response.json()
    except ValueError:
        return {'success': False, 'error': '朋友圈文案API响应不是有效 JSON'}

    try:
        content = result['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        return {'success': False, 'error': '朋友圈文案API响应解析失败，缺少生成内容'}

    social_copy = (content or '').strip()
    if not social_copy:
        return {'success': False, 'error': '朋友圈文案API返回内容为空'}

    return {'success': True, 'social_copy': social_copy}
