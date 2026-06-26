# APIYI 图像生成 / 编辑同步服务
#
# 功能描述：
#     封装 APIYI（api.apiyi.com）的 gpt-image-2-vip 文生图与图片编辑接口，
#     全部为同步调用（典型 90–150s）。
#     后端 routes/images.py 会把该服务的调用丢进 ThreadPoolExecutor，
#     立即返回 task_id 给前端，由后台 worker 完成结果落库。
#
# 实现逻辑：
#     1. 认证方式：请求头 `Authorization: Bearer <API_KEY>`
#     2. 文生图：POST {base_url}/v1/images/generations，application/json
#        负载字段：model、prompt、size、response_format
#        禁用字段：quality、n、aspect_ratio（文档明确不接受，传了会报错或被忽略）
#     3. 图片编辑：POST {base_url}/v1/images/edits，multipart/form-data
#        data 字段：model、prompt、size、response_format
#        files 字段：同名 image 字段按上传顺序重复，对应 prompt 中「图1/图2/...」
#     4. 响应：data[0] 仅返回 url 或 b64_json 之一；b64_json 已含 data URL 前缀
#     5. 超时：300s 保守值，吸收长尾与图片上传/下载耗时
#
# 异常处理：
#     - HTTPError：把 status_code + body 截断带回，error_type='http_error'
#     - Timeout：error_type='timeout'
#     - RequestException：error_type='network_error'
#     - JSON 解析失败：error_type='invalid_json'
import json
import time
from typing import Any, Dict, List, Optional

import requests


class ApiyiImageService:
    """APIYI gpt-image-2-vip 文生图 / 图片编辑 同步客户端。"""

    # 服务级重试配置：429 / 5xx 触发；总尝试次数 = 1 + MAX_RETRIES
    # 退避策略：优先读 Retry-After 响应头（秒），否则指数退避 2s / 4s
    # 异常情况：4xx（非 429）不重试；超时按 status=200 但 body 异常处理
    MAX_RETRIES = 2
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(self, api_key: str, base_url: str = "https://api.apiyi.com"):
        # 文档明确：主域名 api.apiyi.com；备选 vip.apiyi.com / b.apiyi.com
        self.api_key = api_key
        self.base_url = (base_url or "https://api.apiyi.com").rstrip("/")
        # 文档：出图典型 90-150s，4K 偶发 500 需更长尾，保守按 300s
        self.timeout = 300
        self.session = requests.Session()
        # 与 gptsapi 服务保持一致：避免走系统代理导致本地调用被劫持
        self.session.trust_env = False

    # 构造请求头：仅带 Authorization（Content-Type 由 requests 根据 json/files 自动设置）
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

    # 退避等待：优先使用响应头 Retry-After（秒），否则按指数退避
    # 实现逻辑：
    #     1. 如果响应头存在 Retry-After 且为正整数，按该秒数等待（封顶 120s）
    #     2. 否则按 2^attempt 计算（attempt 从 1 开始），封顶 60s
    #     3. 失败时同样 sleep，确保重试生效
    # 异常处理：sleep 被中断不重抛，最大限度继续执行
    @staticmethod
    def _sleep_for_retry(response: Optional[requests.Response], attempt: int) -> None:
        wait_seconds = 0
        if response is not None:
            retry_after = response.headers.get("Retry-After", "").strip()
            if retry_after.isdigit():
                wait_seconds = min(int(retry_after), 120)
        if wait_seconds <= 0:
            wait_seconds = min(2 ** attempt, 60)
        print(f"[ApiyiImageService] retry backoff: sleep {wait_seconds}s (attempt={attempt})")
        try:
            time.sleep(wait_seconds)
        except Exception:
            pass

    # 带重试的内部 POST 发送
    # 功能描述：
    #     统一处理 429 / 5xx 的有限重试，避免 1 次 429 就把整个任务打死
    # 实现逻辑：
    #     1. 第一次尝试直接发送；非 200 响应时根据状态码判断是否进入重试
    #     2. 429 / 5xx 进入重试循环：读 Retry-After 退避后再次 POST
    #     3. 4xx（非 429）立即返回原 response，不再重试
    #     4. requests 抛网络/超时异常时也按 attempt 推进重试
    # 异常处理：重试耗尽后返回最后一次的 response（状态码非 200），由 _build_error 统一包装
    def _post_with_retry(self, url: str, *, json_body: Optional[Dict[str, Any]] = None,
                          data: Optional[Dict[str, Any]] = None,
                          files: Optional[List[Any]] = None) -> requests.Response:
        last_response: Optional[requests.Response] = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                if files is not None:
                    response = self.session.post(
                        url,
                        headers=self._headers(),
                        data=data,
                        files=files,
                        timeout=self.timeout,
                    )
                else:
                    response = self.session.post(
                        url,
                        headers=self._headers(),
                        json=json_body,
                        timeout=self.timeout,
                    )
                last_response = response
                if response.status_code == 200:
                    return response
                if response.status_code not in self.RETRYABLE_STATUS:
                    # 4xx（除 429）不重试
                    return response
                if attempt >= self.MAX_RETRIES:
                    return response
                self._sleep_for_retry(response, attempt + 1)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
                # 网络层异常同样进入退避重试
                print(f"[ApiyiImageService] network error attempt {attempt+1}: {net_err}")
                if attempt >= self.MAX_RETRIES:
                    raise
                self._sleep_for_retry(last_response, attempt + 1)
        # 兜底：理论不会到这里
        if last_response is None:
            raise RuntimeError("APIYI 请求未产生任何响应")
        return last_response

    # 通用错误响应构造：把异常统一收敛为 dict，方便上层解析
    def _build_error(self, err: Exception) -> Dict[str, Any]:
        # HTTP 错误：携带 status_code + 响应体片段，便于定位 400/401/429/500
        if isinstance(err, requests.exceptions.HTTPError):
            status_code = 0
            error_body = ""
            if err.response is not None:
                status_code = err.response.status_code
                error_body = (err.response.text or "")[:1000]
            return {
                "error": f"APIYI HTTP {status_code}: {error_body[:200]}",
                "status_code": status_code,
                "error_body": error_body,
                "error_type": "http_error",
            }
        # 超时：典型场景是 Codex 高峰 + 4K 长尾
        if isinstance(err, requests.exceptions.Timeout):
            return {
                "error": "APIYI 请求超时（>300s），建议降低 size 重试",
                "error_type": "timeout",
            }
        # 网络错误：DNS/连接失败/SSL 等
        if isinstance(err, requests.exceptions.RequestException):
            return {
                "error": f"APIYI 网络错误: {err}",
                "error_type": "network_error",
            }
        # JSON 解析失败
        if isinstance(err, ValueError):
            return {
                "error": f"APIYI 响应不是有效 JSON: {err}",
                "error_type": "invalid_json",
            }
        # 兜底
        return {
            "error": f"APIYI 未知错误: {err}",
            "error_type": "unknown",
        }

    # 文生图同步调用
    # 功能描述：
    #     按文档要求向 {base_url}/v1/images/generations 提交 JSON 请求。
    #     负载固定只传 model / prompt / size / response_format 四个字段。
    #     注意：文档严禁传 quality / n / aspect_ratio（不传即可）。
    def text_to_image(
        self,
        prompt: str,
        size: str = "auto",
        model: str = "gpt-image-2-vip",
        response_format: str = "b64_json",
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/images/generations"
        # size 默认 auto；按文档也可以传 30 档之一（如 "2048x1360"），半角小写 x
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "response_format": response_format,
        }
        print(f"[ApiyiImageService] POST {url}")
        print(f"[ApiyiImageService] payload: {json.dumps(payload, ensure_ascii=False)}")
        try:
            response = self._post_with_retry(url, json_body=payload)
            response.raise_for_status()
            return response.json()
        except Exception as err:
            print(f"[ApiyiImageService] text_to_image failed: {err}")
            return self._build_error(err)

    # 图片编辑同步调用（单图或多图融合）
    # 功能描述：
    #     按文档要求向 {base_url}/v1/images/edits 提交 multipart/form-data 请求。
    #     - data 字段：model、prompt、size、response_format
    #     - files 字段：同名 image 字段按 image_paths 顺序重复（按上传顺序对应 prompt 中「图1/图2/...」）
    #     文档建议输入图先压到 1.5MB 以内（路由层已通过 downscale_image 把超过 3840px 长边的图等比缩小）
    def image_edit(
        self,
        prompt: str,
        image_paths: List[str],
        size: str = "auto",
        model: str = "gpt-image-2-vip",
        response_format: str = "b64_json",
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/images/edits"
        data = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "response_format": response_format,
        }
        # 同名 image 字段重复：按 image_paths 顺序对应 prompt 中的「图1/图2/...」
        # 用 with 保证文件句柄在请求结束或异常时都能正确关闭
        opened_files = []
        files = []
        try:
            for path in image_paths:
                fp = open(path, "rb")
                opened_files.append(fp)
                # 用 (filename, fp, mime) 三元组，确保 multipart 字段名一致
                files.append(("image", (path.split("/")[-1].split("\\")[-1] or "image.png", fp, "image/png")))
            print(f"[ApiyiImageService] POST {url}")
            print(f"[ApiyiImageService] data: {json.dumps(data, ensure_ascii=False)}, files: {len(files)} image(s)")
            response = self._post_with_retry(url, data=data, files=files)
            response.raise_for_status()
            return response.json()
        except Exception as err:
            print(f"[ApiyiImageService] image_edit failed: {err}")
            return self._build_error(err)
        finally:
            # 关闭所有打开的文件句柄
            for fp in opened_files:
                try:
                    fp.close()
                except Exception:
                    pass
