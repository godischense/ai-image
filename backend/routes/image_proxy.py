# 跨域图片代理路由
# 功能描述：
#   将远程图片 URL 通过后端代理返回给前端，避免浏览器 ORB 拦截
#   ORB (Opaque Response Blocking) 会阻止跨域图片加载，
#   通过后端代理可以将跨域请求转为同源请求
# 实现逻辑：
#   1. 接收 url 查询参数
#   2. 使用 requests 下载远程图片
#   3. 以原始 Content-Type 转发给前端
#   4. 上游返回非 2xx 状态码时，透传真实状态码和错误信息
# 异常处理：
#   - URL 参数缺失 → 400
#   - 上游 4xx/5xx → 透传原状态码
#   - 连接/超时 → 502

from flask import Blueprint, request, Response
import requests as requests_lib

image_proxy_bp = Blueprint('image_proxy', __name__)


@image_proxy_bp.route('/api/proxy/image')
def proxy_image():
    image_url = request.args.get('url', '').strip()
    if not image_url:
        return Response('Missing url parameter', status=400)

    try:
        resp = requests_lib.get(image_url, timeout=30, proxies={'http': None, 'https': None})
        if resp.status_code >= 400:
            reason = f'Upstream returned {resp.status_code} for {image_url[:100]}...'
            print(f'[image_proxy] {reason}')
            return Response(reason, status=resp.status_code)
        content_type = resp.headers.get('Content-Type', 'image/png')
        return Response(resp.content, status=200, content_type=content_type)
    except requests_lib.RequestException as e:
        print(f'[image_proxy] Failed to proxy image: {image_url[:100]}... -> {e}')
        return Response(f'Failed to fetch remote image: {e}', status=502)
