# 参考图上传接口
# 功能描述：
#     接收前端传来的 base64 Data URL 参考图，将其上传到文件 API（/v1/files）获取 HTTP URL，
#     返回 URL 供前端存储，统一 Fal 和 OpenAI 双模式的参考图传递方式。
# 实现逻辑：
#     1. POST /api/files/upload-reference 接收 { "image": "data:image/...;base64,..." }
#     2. 从数据库 file_upload 配置读取 baseUrl 和 apiKey
#     3. 解码 base64 → 二进制 → POST multipart 到 {baseUrl}/v1/files
#     4. 成功返回 URL，失败返回错误信息
import base64
import logging

import requests
from flask import Blueprint, request, jsonify

from models.config_model import get_single_config

logger = logging.getLogger(__name__)
file_upload_bp = Blueprint('file_upload', __name__)


@file_upload_bp.route('/api/files/upload-reference', methods=['POST'])
def upload_reference_image():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'error', 'message': '请求体不能为空'}), 400

    image_b64 = data.get('image', '')
    if not image_b64:
        return jsonify({'status': 'error', 'message': '缺少 image 参数'}), 400

    if not isinstance(image_b64, str) or not image_b64.startswith('data:'):
        return jsonify({'status': 'error', 'message': 'image 必须是有效的 base64 Data URL'}), 400

    # 读取 file_upload 数据库配置
    file_upload_config = get_single_config('file_upload')
    base_url = (file_upload_config.get('baseUrl', '') or '').rstrip('/')
    api_key = file_upload_config.get('apiKey', '') or ''

    if not base_url or not api_key:
        return jsonify({'status': 'error', 'message': '文件上传服务未配置，请先在设置中配置 baseUrl 和 apiKey'}), 400

    # 解码 base64 → 二进制
    try:
        header, b64_part = image_b64.split(',', 1)
        img_bytes = base64.b64decode(b64_part)
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'base64 解码失败: {str(e)}'}), 400

    # 上传到文件 API
    try:
        files = {'file': ('reference.png', img_bytes, 'image/png')}
        headers = {'Authorization': f'Bearer {api_key}'}
        resp = requests.post(
            f'{base_url}/v1/files',
            headers=headers,
            files=files,
            timeout=120,
            proxies={'http': None, 'https': None}
        )
        resp.raise_for_status()
        result = resp.json()

        # 文档返回示例中包含 url 字段（POST 直接返回 url+id，无需额外 GET 请求）
        if 'url' in result and result['url']:
            file_url = result['url']
        elif 'id' in result and result['id']:
            file_url = f'{base_url}/v1/files/{result["id"]}/content'
        else:
            print(f"[file_upload] 上传响应缺少 url 和 id: {result}")
            return jsonify({'status': 'error', 'message': '文件上传成功但响应中缺少文件链接'}), 502

        print(f"[file_upload] 参考图上传成功: {file_url[:80]}...")
        return jsonify({'status': 'success', 'url': file_url}), 200

    except requests.exceptions.RequestException as e:
        print(f"[file_upload] 上传请求失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'文件上传失败: {str(e)}'}), 502
    except Exception as e:
        print(f"[file_upload] 上传异常: {str(e)}")
        return jsonify({'status': 'error', 'message': f'文件上传异常: {str(e)}'}), 500
