# APIYI 余额查询接口
#
# 功能描述：
#     代理 APIYI 平台"获取用户信息"接口，从响应中提取账户余额（剩余额度），
#     返回与 T8 路由同构的结构化数据给前端展示在设置页 APIYI 卡片的余额 chip。
#     仅在用户已配置 accessToken 时工作；accessToken 与生图 apiKey 是两个
#     不同的字段（余额查询 Authorization 不带 Bearer 前缀）。
#
# 实现逻辑：
#     1. 从数据库 apiyi_api 配置读取 baseUrl（与生图共用）和 accessToken
#     2. 关键字段缺失 → 返回 400，提示用户填写
#     3. 调 {baseUrl}/api/user/self，Authorization 直接写 token 字符串（无 Bearer 前缀）
#     4. 解析响应：优先 data.quota（嵌套字段），兜底递归搜 quota
#     5. 按硬编码除数 500000 把"额度"换算成"美元展示值"
#     6. 异常分支：超时 / 网络错误 / HTTP 非 2xx / 字段缺失四类均返回结构化 status='error'
#
# 接口规范：严格按 e:\AI-image\新建文件夹\apiyi\查询余额.md
#     - URL: https://api.apiyi.com/api/user/self
#     - 认证: Authorization: <token>（无 Bearer 前缀）
#     - 响应字段: data.quota（嵌套在 data 下）
#     - 换算: 500000 额度 = 1.00 USD
import logging

import requests
from flask import Blueprint, jsonify

from models.config_model import get_single_config

logger = logging.getLogger(__name__)
apiyi_balance_bp = Blueprint('apiyi_balance', __name__)

# 外部接口路径：根据 API 文档（查询余额.md），固定为 /api/user/self
BALANCE_PATH = '/api/user/self'

# 响应中作为"余额"的字段路径（嵌套在 data 下），按文档第 73 行
FIELD_PATH = 'data.quota'

# 余额换算除数：500,000 额度 = $1.00 USD（按文档第 102-108 行）
# 用户已确认"只填写 AccessToken"，后端硬编码，不暴露为可配置项
DIVIDER = 500000

# 请求超时（秒）：按文档第 319-323 行"建议设置合理的请求超时时间（推荐10秒）"
REQUEST_TIMEOUT = 10
REQUEST_RETRIES = 3
FALLBACK_BASE_URLS = ('https://vip.apiyi.com', 'https://b.apiyi.com')


def _unique_base_urls(primary_base_url):
    seen = set()
    urls = []
    for item in (primary_base_url, *FALLBACK_BASE_URLS):
        value = (item or '').strip().rstrip('/')
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            urls.append(value)
    return urls


def _request_apiyi_balance(base_url, headers):
    errors = []
    for candidate_base_url in _unique_base_urls(base_url):
        full_url = candidate_base_url + BALANCE_PATH
        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                response = requests.get(
                    full_url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    proxies={'http': None, 'https': None}
                )
                return response, full_url, errors
            except requests.exceptions.RequestException as e:
                message = f'{full_url} 第 {attempt}/{REQUEST_RETRIES} 次失败: {str(e)}'
                errors.append(message)
                logger.warning('[ApiyiBalance] %s', message)
    return None, None, errors


# 格式化金额数字为可读字符串
#
# 实现逻辑：
#     - 整数显示为不带小数的形式（如 5000 -> "5000"）
#     - 浮点数保留 2 位小数，去除无意义的尾零
#     - 失败 / None 时返回 "获取失败"
def _format_amount(amount):
    if amount is None:
        return '获取失败'
    if isinstance(amount, int) or (isinstance(amount, float) and amount.is_integer()):
        return str(int(amount))
    return ('%.2f' % float(amount)).rstrip('0').rstrip('.')


# 在响应 JSON 中递归查找 quota 字段（兜底）
#
# 参数：
#     obj - 待查找的 Python 对象（dict / list / 标量）
#     depth - 当前递归深度，防止异常嵌套数据导致栈溢出
#
# 返回：
#     (命中的字段路径字符串, 命中的数值) ；未命中返回 (None, None)
def _recursive_find_quota(obj, depth=0):
    if depth > 6:
        return None, None
    if isinstance(obj, dict):
        # 优先匹配 quota
        if 'quota' in obj:
            value = obj['quota']
            if isinstance(value, (int, float)):
                return 'quota', value
            if isinstance(value, str):
                try:
                    return 'quota', float(value)
                except ValueError:
                    pass
        for key, value in obj.items():
            found_key, found_val = _recursive_find_quota(value, depth + 1)
            if found_val is not None:
                return found_key, found_val
    elif isinstance(obj, list):
        for item in obj:
            found_key, found_val = _recursive_find_quota(item, depth + 1)
            if found_val is not None:
                return found_key, found_val
    return None, None


# 从 APIYI 响应中提取余额
#
# 实现逻辑：
#     1. 优先按文档固定结构提取 payload.data.quota（嵌套字段）
#     2. 兜底递归搜 quota（防御响应结构微调）
#
# 返回：
#     (命中的字段路径字符串, 命中的数值)
def _extract_apiyi_quota(payload):
    if not isinstance(payload, dict):
        return None, None
    data = payload.get('data')
    # 优先提取嵌套的 data.quota（文档第 73 行固定结构）
    if isinstance(data, dict):
        if isinstance(data.get('quota'), (int, float)):
            return FIELD_PATH, data['quota']
        if isinstance(data.get('quota'), str):
            try:
                return FIELD_PATH, float(data['quota'])
            except ValueError:
                pass
    # 兜底递归（防御响应结构微调）
    return _recursive_find_quota(payload)


# GET /api/apiyi/balance
#
# 返回：
#     成功：{ status:'success', platformName, displayAmount, amount, rawAmount, matchedField, divider, raw }
#     失败（未配置）：400 { status:'error', message:'请先在 APIYI 设置中填写 AccessToken' }
#     失败（外部接口）：502 { status:'error', message, platformName, raw? }
#     失败（响应字段缺失）：200 { status:'error', message:'响应中未找到 data.quota 字段', platformName, raw }
#
# 异常处理：
#     - 数据库读不到配置 → 500
#     - accessToken 缺失 → 400
#     - 网络/超时错误 → 502 { status:'error', message }
#     - HTTP 非 2xx → 502 { status:'error', message, raw }
#     - 响应非 JSON / 字段找不到 → 200 { status:'error', message, raw }
def _build_apiyi_balance_response(response, full_url, divider):
    raw_text = response.text
    raw_data = None
    try:
        raw_data = response.json()
    except ValueError:
        raw_data = None

    if not response.ok:
        logger.warning(
            '[ApiyiBalance] 外部接口返回非 2xx: url=%s status=%s body=%s',
            full_url, response.status_code, raw_text[:200]
        )
        friendly_message = ''
        if isinstance(raw_data, dict) and isinstance(raw_data.get('message'), str):
            friendly_message = f"（{raw_data['message']}）"
        return jsonify({
            'status': 'error',
            'message': f'外部接口返回 HTTP {response.status_code}{friendly_message}',
            'platformName': 'APIYI',
            'raw': raw_data if raw_data is not None else raw_text
        }), 502

    matched_field, raw_amount = _extract_apiyi_quota(raw_data) if raw_data is not None else (None, None)
    if raw_amount is None:
        return jsonify({
            'status': 'error',
            'message': f'响应中未找到 {FIELD_PATH} 字段',
            'platformName': 'APIYI',
            'raw': raw_data
        }), 200

    display_amount = raw_amount / divider
    return jsonify({
        'status': 'success',
        'platformName': 'APIYI',
        'amount': display_amount,
        'rawAmount': raw_amount,
        'matchedField': matched_field,
        'divider': divider,
        'displayAmount': _format_amount(display_amount),
        'raw': raw_data
    }), 200


@apiyi_balance_bp.route('/api/apiyi/balance', methods=['GET'])
def get_apiyi_balance():
    # 1. 读取配置
    try:
        config = get_single_config('apiyi_api') or {}
    except Exception as e:
        logger.error('[ApiyiBalance] 读取配置失败: %s', str(e), exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'读取 APIYI 配置失败: {str(e)}'
        }), 500

    # 2. 提取关键字段
    # baseUrl 与生图共用同一域名（APIYI 文档里 /api/user/self 与生图是同源）
    base_url = (config.get('baseUrl') or '').strip()
    access_token = (config.get('accessToken') or '').strip()
    # 余额换算除数取自配置以兼容未来调整，默认 500000
    raw_divider = config.get('balanceDivider', DIVIDER)
    try:
        divider = float(raw_divider)
        if not (divider > 0):
            divider = float(DIVIDER)
    except (TypeError, ValueError):
        divider = float(DIVIDER)

    if not base_url:
        return jsonify({
            'status': 'error',
            'message': '请先在 APIYI 设置中填写 Base URL'
        }), 400

    if not access_token:
        return jsonify({
            'status': 'error',
            'message': '请先在 APIYI 设置中填写 AccessToken'
        }), 400

    full_url = base_url.rstrip('/') + BALANCE_PATH
    response, full_url, request_errors = _request_apiyi_balance(base_url, {
        'Authorization': access_token,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    })
    if response is None:
        logger.error('[ApiyiBalance] 外部接口请求失败: %s', ' | '.join(request_errors))
        return jsonify({
            'status': 'error',
            'message': '外部余额接口请求失败，已重试主域名和备用域名: ' + (request_errors[-1] if request_errors else '未知网络错误'),
            'platformName': 'APIYI',
            'attempts': request_errors
        }), 502
    return _build_apiyi_balance_response(response, full_url, divider)
    # 关键：Authorization 直接写 token 字符串（无 Bearer 前缀）
    # 文档第 48 行明确：API访问令牌，格式：直接填写token字符串
    headers = {
        'Authorization': access_token,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # 3. 发送请求
    try:
        response = requests.get(
            full_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            proxies={'http': None, 'https': None}
        )
    except requests.exceptions.Timeout:
        logger.warning('[ApiyiBalance] 外部接口超时: %s', full_url)
        return jsonify({
            'status': 'error',
            'message': f'外部余额接口请求超时（{REQUEST_TIMEOUT}s）',
            'platformName': 'APIYI'
        }), 502
    except requests.exceptions.RequestException as e:
        logger.error('[ApiyiBalance] 外部接口请求失败: %s', str(e))
        return jsonify({
            'status': 'error',
            'message': f'外部余额接口请求失败: {str(e)}',
            'platformName': 'APIYI'
        }), 502

    # 4. 解析响应体
    raw_text = response.text
    raw_data = None
    try:
        raw_data = response.json()
    except ValueError:
        raw_data = None

    if not response.ok:
        logger.warning(
            '[ApiyiBalance] 外部接口返回非 2xx: status=%s body=%s',
            response.status_code, raw_text[:200]
        )
        # 401/403 时尝试从 payload.message 中提取更友好的错误（文档第 117-132 行）
        friendly_message = ''
        if isinstance(raw_data, dict) and isinstance(raw_data.get('message'), str):
            friendly_message = f"（{raw_data['message']}）"
        return jsonify({
            'status': 'error',
            'message': f'外部接口返回 HTTP {response.status_code}{friendly_message}',
            'platformName': 'APIYI',
            'raw': raw_data if raw_data is not None else raw_text
        }), 502

    # 5. 提取余额字段
    matched_field, raw_amount = _extract_apiyi_quota(raw_data) if raw_data is not None else (None, None)
    if raw_amount is None:
        return jsonify({
            'status': 'error',
            'message': f'响应中未找到 {FIELD_PATH} 字段',
            'platformName': 'APIYI',
            'raw': raw_data
        }), 200

    # 6. 换算为展示数字：500,000 额度 = $1.00 USD（文档第 102-108 行）
    display_amount = raw_amount / divider

    return jsonify({
        'status': 'success',
        'platformName': 'APIYI',
        'amount': display_amount,
        'rawAmount': raw_amount,
        'matchedField': matched_field,
        'divider': divider,
        'displayAmount': _format_amount(display_amount),
        'raw': raw_data
    }), 200
