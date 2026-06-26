# 用户余额查询接口
#
# 功能描述：
#     代理外部平台（与 T8 平台图像生成 API 同域名）的"获取用户信息"接口，
#     从响应中读取硬编码字段 quota（单位 1/500000 美元），
#     返回 { platformName, amount, raw } 给前端展示在设置页 T8 卡片头部。
#     同时承担设置页"测试连接"按钮的逻辑。
#
# 实现逻辑：
#     1. 从数据库 image_api 配置读取 baseUrl（与生图共用）/ balanceToken / balanceUserId
#     2. 任一关键字段缺失 → 返回 400，提示用户前往设置页填写
#     3. 用 requests 调 {baseUrl}/api/user/self，携带 Bearer Token 与 New-API-User 头
#     4. 解析响应：硬编码查找 data.quota 或顶层 quota 字段
#     5. 余额换算：展示金额 = 原始 quota / 500000（硬编码除数）
#     6. 异常分支：网络/解析/字段缺失三类错误均返回结构化 status='error'，
#        避免前端误判为致命错误影响 UI 体验
import logging

import requests
from flask import Blueprint, current_app, jsonify

from models.config_model import get_single_config

logger = logging.getLogger(__name__)
user_balance_bp = Blueprint('user_balance', __name__)

# 外部接口路径：根据 API 文档（获取用户余额.md），固定为 /api/user/self
# 单独定义为常量便于未来调整或抽取为配置
BALANCE_PATH = '/api/user/self'

# 余额字段名硬编码为 'quota'（依据 查询余额.md 第 69 行）
# 不再让用户配置；如未来需扩展多种字段，再放开
BALANCE_FIELD = 'quota'

# 余额换算除数硬编码为 500000
# 依据 查询余额.md：quota 是 1/500000 美元单位，除以 500000 才得到"网站额度"
BALANCE_DIVIDER = 500000

# 平台名称固定为 "T8"（与设置页 T8 平台图像生成 API 卡片标题一致）
# 如未来需扩展多平台，再放宽为可配置字段
PLATFORM_NAME = 'T8'


# 从响应 JSON 中提取硬编码字段的金额
#
# 参数：
#     obj - 待查找的 Python 对象（dict / list / 标量）
#     depth - 当前递归深度，防止异常嵌套数据导致栈溢出
#
# 返回：
#     (命中的字段路径字符串, 命中的数值) ；未命中返回 (None, None)
def _extract_quota(obj, depth=0):
    if depth > 6:
        return None, None
    if isinstance(obj, dict):
        if BALANCE_FIELD in obj:
            value = obj[BALANCE_FIELD]
            if isinstance(value, (int, float)):
                return BALANCE_FIELD, value
            if isinstance(value, str):
                try:
                    return BALANCE_FIELD, float(value)
                except ValueError:
                    pass
        for key, value in obj.items():
            found_key, found_val = _extract_quota(value, depth + 1)
            if found_val is not None:
                return found_key, found_val
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            found_key, found_val = _extract_quota(item, depth + 1)
            if found_val is not None:
                return found_key, found_val
    return None, None


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


# 从 Base URL 中提取 host 用作 platformName 兜底
# 形如 https://ai.t8star.cn → ai.t8star.cn
def _host_from_base_url(base_url):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        return parsed.netloc or base_url
    except Exception:
        return base_url


# GET /api/user/balance
#
# 返回：
#     成功：{ status:'success', platformName, displayAmount, amount, rawAmount, matchedField, divider, raw }
#     失败（未配置）：400 { status:'error', message:'请先在 T8 平台图像生成 API 配置中填写余额 Token、用户 ID' }
#     失败（外部接口）：200 { status:'error', message, raw } 或 502
#
# 异常处理：
#     - 数据库读不到配置 → 500
#     - 网络/超时错误 → 502 { status:'error', message }
#     - HTTP 非 2xx → 502 { status:'error', message, raw }
#     - 响应非 JSON / 字段找不到 → 200 { status:'error', message:'响应中未找到余额字段 quota' }
@user_balance_bp.route('/api/user/balance', methods=['GET'])
def get_user_balance():
    try:
        # 与生图 API 共用 image_api 配置的 baseUrl，余额专用字段也走同一张表
        image_api_config = get_single_config('image_api') or {}
    except Exception as e:
        logger.error('[UserBalance] 读取 image_api 配置失败: %s', str(e), exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'读取配置失败: {str(e)}'
        }), 500

    base_url = (image_api_config.get('baseUrl') or '').strip()
    token = (image_api_config.get('balanceToken') or '').strip()
    user_id = (image_api_config.get('balanceUserId') or '').strip()
    # platformName 固定为 T8；若用户想看 host，可从 baseUrl 提取后回退
    platform_name = PLATFORM_NAME or _host_from_base_url(base_url)

    if not base_url or not token or not user_id:
        return jsonify({
            'status': 'error',
            'message': '请先在 T8 平台图像生成 API 配置中填写余额 Token、用户 ID（Base URL 与生图共用）'
        }), 400

    full_url = base_url.rstrip('/') + BALANCE_PATH
    headers = {
        'Authorization': f'Bearer {token}',
        'New-API-User': user_id,
        'Accept': 'application/json'
    }

    try:
        response = requests.get(
            full_url,
            headers=headers,
            timeout=10,
            proxies={'http': None, 'https': None}
        )
    except requests.exceptions.Timeout:
        logger.warning('[UserBalance] 外部接口超时: %s', full_url)
        return jsonify({
            'status': 'error',
            'message': '外部余额接口请求超时（10s）',
            'platformName': platform_name
        }), 502
    except requests.exceptions.RequestException as e:
        logger.error('[UserBalance] 外部接口请求失败: %s', str(e))
        return jsonify({
            'status': 'error',
            'message': f'外部余额接口请求失败: {str(e)}',
            'platformName': platform_name
        }), 502

    # 解析响应体：JSON 优先，失败回退为文本，避免直接崩溃
    raw_text = response.text
    raw_data = None
    try:
        raw_data = response.json()
    except ValueError:
        raw_data = None

    if not response.ok:
        logger.warning(
            '[UserBalance] 外部接口返回非 2xx: status=%s body=%s',
            response.status_code, raw_text[:200]
        )
        return jsonify({
            'status': 'error',
            'message': f'外部接口返回 HTTP {response.status_code}',
            'platformName': platform_name,
            'raw': raw_data if raw_data is not None else raw_text
        }), 502

    # 解析响应：硬编码查找 quota 字段（含 data 嵌套）
    matched_field, raw_amount = _extract_quota(raw_data) if raw_data is not None else (None, None)
    if raw_amount is None:
        return jsonify({
            'status': 'error',
            'message': f'响应中未找到余额字段 {BALANCE_FIELD}',
            'platformName': platform_name,
            'raw': raw_data
        }), 200

    # 换算为展示数字：quota 字段是 1/500000 美元单位，
    # 需要除以硬编码的 BALANCE_DIVIDER 才是"网站额度"。
    display_amount = raw_amount / BALANCE_DIVIDER

    return jsonify({
        'status': 'success',
        'platformName': platform_name,
        'amount': display_amount,
        'rawAmount': raw_amount,
        'matchedField': matched_field,
        'divider': BALANCE_DIVIDER,
        'displayAmount': _format_amount(display_amount),
        'raw': raw_data
    }), 200
