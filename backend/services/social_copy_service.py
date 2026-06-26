import json
import logging
from typing import Any, Dict

import requests

from models.config_model import get_single_config


logger = logging.getLogger(__name__)


FALLBACK_SYSTEM_PROMPT = (
    '请根据用户提供的海报文案，生成适合朋友圈发布的中文文案。'
    '要求自然、有吸引力、不过度夸张，直接返回文案内容。'
)

# 火山引擎 Responses API 结构化输出 schema：仅定义一个 social_copy 字段，
# 让模型直接返回结构化结果，避免模型在回复中夹杂思考、解释等无关内容
SOCIAL_COPY_JSON_SCHEMA = {
    'name': 'social_copy',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'social_copy': {
                'type': 'string',
                'description': '适合发布到朋友圈的中文文案内容'
            }
        },
        'required': ['social_copy'],
        'additionalProperties': False
    }
}

SOCIAL_COPY_CONTENT_KEYS = (
    'social_copy',
    'copy',
    'content',
    'text',
    'output_text',
    'generated_text',
    'final_answer',
    'answer',
    'result',
)

INVALID_SOCIAL_COPY_PREFIXES = (
    'resp_',
    'response_',
    'chatcmpl-',
)


def _extract_error_message(response: requests.Response) -> str:
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
    return error_message


def _extract_text_from_content(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for key in SOCIAL_COPY_CONTENT_KEYS:
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
            if isinstance(text, (dict, list)):
                nested_text = _extract_text_from_content(text)
                if nested_text:
                    return nested_text
        return ''

    if isinstance(value, list):
        chunks = []
        for part in value:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict):
                text = _extract_text_from_content(part)
                if text:
                    chunks.append(text)
        return ''.join(chunks).strip()

    return ''


def _extract_social_copy_from_json_text(content: str) -> str:
    text = (content or '').strip()
    if not text:
        return ''

    if text.startswith('```'):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = '\n'.join(lines[1:-1]).strip()
            if text.lower().startswith('json'):
                text = text[4:].strip()

    if not text.startswith(('{', '[')):
        return ''

    try:
        data = json.loads(text)
    except ValueError:
        return ''

    return _extract_text_from_content(data)


def _normalize_social_copy_content(content: Any) -> str:
    text = _extract_text_from_content(content)
    if not text:
        return ''

    structured_text = _extract_social_copy_from_json_text(text)
    return structured_text or text


def _is_invalid_social_copy_text(text: str) -> bool:
    value = (text or '').strip()
    if not value:
        return True

    lower_value = value.lower()
    if any(lower_value.startswith(prefix) for prefix in INVALID_SOCIAL_COPY_PREFIXES):
        return True

    compact_value = value.replace('-', '').replace('_', '')
    if len(value) >= 24 and compact_value.isalnum() and ' ' not in value and '\n' not in value:
        return True

    return False


def _extract_chat_content(result: Dict[str, Any]) -> str:
    choices = result.get('choices')
    if not isinstance(choices, list):
        return ''

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get('message')
        if isinstance(message, dict):
            content = _normalize_social_copy_content(message.get('content'))
            if content and not _is_invalid_social_copy_text(content):
                return content

        content = _normalize_social_copy_content(choice.get('text') or choice.get('content'))
        if content and not _is_invalid_social_copy_text(content):
            return content

    return ''


def _extract_responses_content(result: Dict[str, Any]) -> str:
    output_text = result.get('output_text')
    if isinstance(output_text, str) and output_text.strip() and not _is_invalid_social_copy_text(output_text):
        text = output_text.strip()
        # 结构化输出场景：output_text 直接就是 JSON 字符串，需要从 JSON 中解析出 social_copy
        structured_text = _extract_social_copy_from_json_text(text)
        if structured_text:
            return structured_text
        return text

    output = result.get('output', [])
    if not isinstance(output, list):
        return ''

    for item in output:
        if not isinstance(item, dict):
            continue
        # 过滤掉非文本类型的 output 条目（reasoning、function_call、web_search_call 等），
        # 只保留 message、summary、output_text 等可能包含文案内容的类型
        item_type = item.get('type')
        if item_type not in ('message', 'summary', 'output_text', None):
            continue

        content_list = item.get('content')
        if isinstance(content_list, list):
            parts = []
            for part in content_list:
                if not isinstance(part, dict):
                    continue
                # 仅提取 output_text / text 类型的片段，跳过 input_text、refusal 等
                part_type = part.get('type')
                if part_type not in ('output_text', 'text', None):
                    continue
                text = (part.get('text') or '').strip()
                if text and not _is_invalid_social_copy_text(text):
                    parts.append(text)
            if parts:
                joined = ''.join(parts).strip()
                structured_text = _extract_social_copy_from_json_text(joined)
                if structured_text:
                    return structured_text
                if not _is_invalid_social_copy_text(joined):
                    return joined

        # 兼容部分模型直接返回 summary 字段字符串的场景
        summary_text = (item.get('summary') or '').strip()
        if summary_text and not _is_invalid_social_copy_text(summary_text):
            structured_text = _extract_social_copy_from_json_text(summary_text)
            if structured_text:
                return structured_text
            return summary_text

        text = _normalize_social_copy_content(item.get('text'))
        if text and not _is_invalid_social_copy_text(text):
            return text

    return ''


def _describe_response_shape(result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return type(result).__name__

    top_keys = list(result.keys())[:10]
    parts = [f'top-level keys={top_keys}']

    choices = result.get('choices')
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            parts.append(f'choices[0] keys={list(first_choice.keys())[:10]}')
            message = first_choice.get('message')
            if isinstance(message, dict):
                parts.append(f'choices[0].message keys={list(message.keys())[:10]}')

    output = result.get('output')
    if isinstance(output, list) and output:
        first_output = output[0]
        if isinstance(first_output, dict):
            parts.append(f'output[0] keys={list(first_output.keys())[:10]}')

    return '; '.join(parts)


def _mask_api_key(api_key: str) -> str:
    value = (api_key or '').strip()
    if len(value) <= 8:
        return '***' if value else ''
    return f'{value[:4]}...{value[-4:]}'


def _truncate_text(value: Any, limit: int = 300) -> str:
    if value is None:
        return ''
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace('\r', '\\r').replace('\n', '\\n')
    if len(text) <= limit:
        return text
    return f'{text[:limit]}...<truncated {len(text) - limit} chars>'


def generate_social_copy(copy_text: str) -> Dict[str, Any]:
    text = (copy_text or '').strip()
    if not text:
        logger.warning('[SocialCopy] empty poster copy, skip generation')
        return {'success': False, 'error': '海报文案为空，无法生成朋友圈文案'}

    config = get_single_config('social_copy_api')
    provider = (config.get('provider') or 'openai').strip()
    is_volcengine = provider == 'volcengine'
    base_url = (
        (config.get('volcengineBaseUrl') if is_volcengine else config.get('baseUrl')) or ''
    ).strip()
    api_key = (config.get('volcengineApiKey') if is_volcengine else config.get('apiKey')) or ''
    model = (
        (config.get('volcengineModel') if is_volcengine else config.get('model')) or ''
    ).strip()
    system_prompt = (config.get('systemPrompt') or '').strip() or FALLBACK_SYSTEM_PROMPT

    logger.info(
        '[SocialCopy] start generate provider=%s model=%s base_url=%s api_key=%s poster_copy_len=%d prompt_len=%d',
        provider,
        model,
        base_url,
        _mask_api_key(api_key),
        len(text),
        len(system_prompt),
    )

    if not base_url or not api_key or not model:
        logger.warning(
            '[SocialCopy] config incomplete provider=%s has_base_url=%s has_api_key=%s has_model=%s',
            provider,
            bool(base_url),
            bool(api_key),
            bool(model),
        )
        return {'success': False, 'error': '朋友圈文案API配置不完整，请在设置页面完善配置'}

    if is_volcengine:
        # 火山引擎 Responses API（/v3/responses）：
        # 1) text.format=json_schema 强制模型按 JSON 结构输出（注意：Responses API 用的是 text.format，不是 response_format）
        # 2) thinking=disabled 关闭深度思考，避免模型输出大量思考内容干扰提取
        # 3) input 必须是 message 数组，不是字符串
        url = base_url
        payload = {
            'model': model,
            'input': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': text}
            ],
            'max_output_tokens': 2048,
            'thinking': {
                'type': 'disabled'
            },
            'text': {
                'format': {
                    'type': 'json_schema',
                    'name': SOCIAL_COPY_JSON_SCHEMA['name'],
                    'strict': SOCIAL_COPY_JSON_SCHEMA['strict'],
                    'schema': SOCIAL_COPY_JSON_SCHEMA['schema']
                }
            }
        }
    else:
        url = f'{base_url.rstrip("/")}/v1/chat/completions'
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': text}
            ]
        }

    logger.info(
        '[SocialCopy] request url=%s payload=%s',
        url,
        _truncate_text(payload, limit=600),
    )

    session = requests.Session()
    session.trust_env = False

    try:
        response = session.post(
            url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=120
        )
    except requests.exceptions.Timeout:
        logger.exception('[SocialCopy] request timeout url=%s model=%s', url, model)
        return {'success': False, 'error': '朋友圈文案API调用超时，请稍后重试'}
    except requests.exceptions.RequestException as exc:
        logger.exception('[SocialCopy] request network error url=%s model=%s error=%s', url, model, exc)
        return {'success': False, 'error': f'朋友圈文案API网络错误：{exc}'}

    logger.info(
        '[SocialCopy] response status=%s headers.content_type=%s body=%s',
        response.status_code,
        response.headers.get('Content-Type'),
        _truncate_text(response.text, limit=1000),
    )

    if response.status_code != 200:
        error_message = _extract_error_message(response)
        logger.warning(
            '[SocialCopy] non-200 response status=%s error=%s',
            response.status_code,
            _truncate_text(error_message),
        )
        return {'success': False, 'error': f'朋友圈文案API返回错误 HTTP {response.status_code}：{error_message}'}

    try:
        result = response.json()
    except ValueError:
        logger.exception('[SocialCopy] invalid json response body=%s', _truncate_text(response.text, limit=1000))
        return {'success': False, 'error': '朋友圈文案API响应不是有效 JSON'}

    logger.info(
        '[SocialCopy] parsed response shape=%s',
        _describe_response_shape(result),
    )

    if is_volcengine:
        content = _extract_responses_content(result)
        if not content:
            shape = _describe_response_shape(result)
            logger.warning('[SocialCopy] content extraction failed provider=%s shape=%s', provider, shape)
            return {'success': False, 'error': f'朋友圈文案API响应解析失败，缺少生成内容。{shape}'}
    else:
        content = _extract_chat_content(result)
        if not content:
            shape = _describe_response_shape(result)
            logger.warning('[SocialCopy] content extraction failed provider=%s shape=%s', provider, shape)
            return {'success': False, 'error': f'朋友圈文案API响应解析失败，缺少生成内容。{shape}'}

    social_copy = (content or '').strip()
    if not social_copy:
        logger.warning('[SocialCopy] extracted content empty after strip')
        return {'success': False, 'error': '朋友圈文案API返回内容为空'}

    if _is_invalid_social_copy_text(social_copy):
        logger.warning('[SocialCopy] extracted invalid content preview=%s', _truncate_text(social_copy, limit=200))
        return {'success': False, 'error': '朋友圈文案API返回的是响应ID，不是文案内容'}

    logger.info(
        '[SocialCopy] extraction success social_copy_len=%d preview=%s',
        len(social_copy),
        _truncate_text(social_copy, limit=300),
    )

    return {'success': True, 'social_copy': social_copy}
