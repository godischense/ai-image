# 跨域图片代理路由
# 功能描述：
#   将远程图片 URL 通过后端代理返回给前端，避免浏览器 ORB 拦截
#   ORB (Opaque Response Blocking) 会阻止跨域图片加载，
#   通过后端代理可以将跨域请求转为同源请求
# 实现逻辑：
#   1. 接收 url 查询参数
#   2. 校验 URL 协议（仅允许 http/https）
#   3. 使用 requests.Session 发起流式请求，复用连接
#   4. 设置 connect/read 两个独立超时，避免一次性大文件超时
#   5. 通过生成器把上游二进制流原样转给前端，节省内存
#   6. 上游返回非 2xx 状态码时，透传真实状态码和错误信息
#   7. 临时性网络错误（超时/连接重置/DNS 失败）自动重试，最多 3 次
# 异常处理：
#   - URL 参数缺失或协议非法 → 400
#   - 重试耗尽仍失败 → 502，并返回最后一次的失败原因
#   - 上游 4xx/5xx → 透传原状态码

from flask import Blueprint, request, Response, stream_with_context
import requests as requests_lib
import time

image_proxy_bp = Blueprint('image_proxy', __name__)

# 复用全局 Session，自动管理连接池，避免每次新建 TCP/TLS 连接
_SESSION = requests_lib.Session()

# 上游请求参数：分段超时（建立连接 10s / 读取内容 60s），单次请求最多 3 次重试
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 60
_MAX_RETRIES = 3
# 兜底最大下载体积：50MB，超过则中断防止 OOM
_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
# 每次读取的流式块大小
_CHUNK_SIZE = 64 * 1024
# 重试等待的基准秒数，按 2 的幂退避
_RETRY_BACKOFF_BASE = 1.5


# 校验 URL 是否为允许代理的协议（仅 http/https）
# 功能描述：
#     防止 SSRF 与 file://、data:// 等危险协议被滥用
# 实现逻辑：
#     1. 协议前缀必须为 http:// 或 https://
#     2. 大小写不敏感
def _is_allowed_url(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return lowered.startswith('http://') or lowered.startswith('https://')


# 判断异常是否属于可重试的临时性错误
# 功能描述：
#     超时、连接重置、DNS 失败、远端断开等都属于可重试错误；
#     其他错误（如协议错误、SSL 错误）通常不可重试
def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (requests_lib.Timeout, requests_lib.ConnectionError)):
        return True
    # ChunkedEncodingError 出现在传输过程中断
    if isinstance(exc, requests_lib.exceptions.ChunkedEncodingError):
        return True
    return False


# 流式读取上游响应内容，逐块 yield 字节
# 功能描述：
#     使用 iter_content 防止一次性加载整个图片到内存；
#     同时累计字节数，超过限制则主动关闭上游连接；
#     客户端断开时优雅关闭上游，避免 socket 泄漏
# 实现逻辑：
#     1. 每次从上游读取 64KB 块
#     2. 累计下载量，超过 50MB 则抛错并关闭上游
#     3. 捕获 GeneratorExit（浏览器/前端断开），关闭上游后退出
#     4. finally 兜底关闭上游连接，防止连接泄漏
def _stream_upstream(resp):
    total = 0
    try:
        for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
            if not chunk:
                continue
            total += len(chunk)
            if total > _MAX_DOWNLOAD_BYTES:
                # 超大文件直接关闭上游，避免恶意/异常大图撑爆内存
                resp.close()
                raise requests_lib.exceptions.ContentDecodingError(
                    f'Upstream payload exceeds {_MAX_DOWNLOAD_BYTES} bytes'
                )
            yield chunk
    except GeneratorExit:
        # 浏览器断开连接：主动关闭上游，避免 socket 泄漏
        try:
            resp.close()
        except Exception:
            pass
        raise
    finally:
        # 正常结束也确保上游连接被关闭
        try:
            resp.close()
        except Exception:
            pass


# 代理远程图片：流式转发 + 自动重试
@image_proxy_bp.route('/api/proxy/image')
def proxy_image():
    image_url = request.args.get('url', '').strip()
    if not image_url:
        return Response('Missing url parameter', status=400)
    if not _is_allowed_url(image_url):
        return Response('Only http/https URLs are supported', status=400)

    last_error = None
    resp = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = _SESSION.get(
                image_url,
                timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
                stream=True,
                proxies={'http': None, 'https': None},
            )
            break
        except requests_lib.RequestException as e:
            last_error = e
            print(f'[image_proxy] Attempt {attempt}/{_MAX_RETRIES} failed for {image_url[:100]}... -> {e}')
            if not _is_retryable_error(e):
                # 非可重试错误（如 SSL 错误、协议错误）直接返回 502
                return Response(f'Failed to fetch remote image: {e}', status=502)
            if attempt < _MAX_RETRIES:
                # 指数退避：第 1 次失败等 1.5s，第 2 次失败等 3s
                time.sleep(_RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
    else:
        # 三次重试全部失败
        print(f'[image_proxy] Gave up proxying {image_url[:100]}... -> {last_error}')
        return Response(f'Failed to fetch remote image after {_MAX_RETRIES} attempts: {last_error}', status=502)

    # 上游返回 4xx/5xx：透传状态码
    if resp.status_code >= 400:
        reason = f'Upstream returned {resp.status_code} for {image_url[:100]}...'
        print(f'[image_proxy] {reason}')
        # 关闭上游连接，避免泄漏 socket
        try:
            resp.close()
        except Exception:
            pass
        return Response(reason, status=resp.status_code)

    # 仅透传与图片相关的响应头，避免缓存/编码相关头污染前端
    upstream_headers = {}
    content_type = resp.headers.get('Content-Type', 'image/png')
    upstream_headers['Content-Type'] = content_type
    content_length = resp.headers.get('Content-Length')
    if content_length:
        upstream_headers['Content-Length'] = content_length
    cache_control = resp.headers.get('Cache-Control')
    if cache_control:
        upstream_headers['Cache-Control'] = cache_control
    else:
        # 浏览器侧可缓存 5 分钟，缓解上游慢链接带来的卡顿
        upstream_headers['Cache-Control'] = 'public, max-age=300'

    return Response(
        stream_with_context(_stream_upstream(resp)),
        status=200,
        headers=upstream_headers,
    )
