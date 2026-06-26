import requests
import base64
import json
from typing import Optional, List, Dict, Any


def _format_http_error(error: requests.exceptions.RequestException) -> str:
    """
    Build a concise error string that preserves upstream response details.
    """
    response = getattr(error, "response", None)
    if response is None:
        return str(error)

    body = (response.text or "").strip()
    if len(body) > 1000:
        body = body[:1000] + "..."
    return f"HTTP {response.status_code}: {body or str(error)}"


class FalImageService:
    """
    fal.ai 图片生成与编辑服务

    功能描述：
        通过用户在设置中配置的代理地址与 fal.ai 队列 API 通信（不再提供硬编码兜底），
        支持提交生图任务、编辑任务、查询任务状态以及获取任务结果。
        所有请求使用 Bearer 开头的 Authorization 头进行鉴权。

    实现逻辑：
        1. 提交任务时 POST 到 /fal/{model}，携带 sync_mode: false 确保异步执行
        2. 任务提交成功后返回 request_id 和 response_url，通过该 ID 进行后续查询
        3. 查询状态和结果时优先使用 API 返回的 response_url（做代理地址替换），回退到手动构造 URL
        4. 所有 HTTP 请求均包含 try/except 兜底，失败时返回 {"error": str(e)}
        5. 支持 base64 和 image_url 两种图片传参方式
        6. 若调用方未提供有效 base_url，构造时直接抛错，避免在请求阶段才发现配置缺失
    """

    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        # 不再提供硬编码兜底：base_url 为空时直接抛错，由调用方在配置缺失时给出明确提示
        cleaned_base_url = (base_url or "").strip().rstrip("/")
        if not cleaned_base_url:
            raise ValueError("FAL Base URL 未配置，请在【设置 -> Fal API 设置】中填写")
        self.base_url = cleaned_base_url
        self.timeout = 300

    # 解析轮询 URL，优先使用 API 返回的 response_url
    # 功能描述：
    #     将 API 返回的 response_url 进行代理地址替换（queue.fal.run → 用户配置的 base_url）
    #     如果 response_url 无效，回退到手动构造 URL
    def _resolve_poll_url(self, response_url: str, model: str, request_id: str, suffix: str = "") -> str:
        if response_url:
            url = response_url.replace("https://queue.fal.run", self.base_url)
            if suffix:
                url = f"{url}{suffix}"
            return url
        url = f"{self.base_url}/{model}/requests/{request_id}"
        if suffix:
            url = f"{url}{suffix}"
        return url

    # 上传图片到 /v1/files API 获取临时 URL（image_url 模式）
    # 功能描述：
    #     将图片二进制数据上传到代理的 /v1/files 接口，获取临时访问 URL
    #     用于替代 base64 data URL，减少 JSON 请求体大小，避免大图请求超时
    #     注意：此方法已废弃，推荐使用独立的 FileUploadService
    # 实现逻辑：
    #     1. 读取图片文件二进制数据
    #     2. 以 multipart/form-data 方式 POST 到 /v1/files
    #     3. 返回响应中的 url 字段，或根据 id 构造 URL
    def upload_image_to_url(self, image_data: bytes, filename: str = "image.png") -> Optional[str]:
        try:
            # 从 self.base_url 中提取基础域名（去掉 /fal 结尾）
            # 例如 https://your-host.com/fal → https://your-host.com
            upload_base = self.base_url.rstrip('/')
            if upload_base.endswith('/fal'):
                upload_base = upload_base[:-4]
            files = {'file': (filename, image_data, 'image/png')}
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.post(
                f"{upload_base}/v1/files",
                headers=headers,
                files=files,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )
            response.raise_for_status()
            result = response.json()
            if 'url' in result:
                print(f"[FalImageService] Image uploaded to URL: {result['url'][:80]}...")
                return result['url']
            if 'id' in result:
                constructed_url = f"{upload_base}/v1/files/{result['id']}/content"
                print(f"[FalImageService] Image uploaded, constructed url from id {result['id']}: {constructed_url[:80]}...")
                return constructed_url
            print(f"[FalImageService] Unexpected file upload response: {result}")
            return None
        except Exception as e:
            print(f"[FalImageService] Error uploading image: {str(e)}")
            return None

    # 提交图片生成任务到 fal.ai 队列
    # 功能描述：
    #     sync_mode=True 时 Fal API 会直接返回 {"images": [...]} 即时结果
    #     sync_mode=False 时 Fal API 返回 {"request_id": "..."} 进入队列
    #     提交成功后统一包装：即时结果放入 data 字段，队列结果保留 request_id
    def submit_generation(
        self,
        prompt: str,
        model: str = "openai/gpt-image-2",
        image_size: Any = "square_hd",
        quality: str = "auto",
        num_images: int = 1,
        output_format: str = "png",
        image_urls: Optional[List[str]] = None,
        seed: int = 0,
        sync_mode: bool = False
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{model}"

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        payload = {
            'prompt': prompt,
            'image_size': image_size,
            'quality': quality,
            'num_images': num_images,
            'output_format': output_format,
            'sync_mode': sync_mode
        }

        if image_urls:
            payload['image_urls'] = image_urls

        if seed > 0:
            payload['seed'] = seed

        print(f"\n[FalImageService] Submit generation request to: {url}")
        print(f"[FalImageService] Headers: {json.dumps({k: v for k, v in headers.items() if k != 'Authorization'})}")
        print_info = payload.copy()
        if 'image_urls' in print_info:
            print_info['image_urls'] = f"[{len(print_info['image_urls'])} reference images]"
        print(f"[FalImageService] Payload: {json.dumps(print_info, ensure_ascii=False, indent=2)}\n")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120, proxies={'http': None, 'https': None})
            response.raise_for_status()
            result = response.json()

            # sync_mode=True 且 Fal API 直接返回了 images → 即时同步结果
            if sync_mode and isinstance(result.get('images'), list) and len(result['images']) > 0:
                print(f"[FalImageService] Sync mode: received immediate images ({len(result['images'])} images)")
                image_urls_result = []
                for img_info in result['images']:
                    img_url = img_info.get('url', '') if isinstance(img_info, dict) else str(img_info)
                    if img_url:
                        image_urls_result.append({'url': img_url})
                return {
                    'data': image_urls_result,
                    'sync_mode': True,
                    'raw_result': result
                }

            print(f"[FalImageService] Submit generation response: request_id={result.get('request_id', 'N/A')}, "
                  f"has_response_url={'response_url' in result}")
            return result
        except requests.exceptions.RequestException as e:
            error_message = _format_http_error(e)
            print(f"[FalImageService] Submit generation error: {error_message}")
            return {'error': error_message}

    # 提交图片编辑任务到 fal.ai 队列
    # 功能描述：
    #     sync_mode=True 时 Fal API 会直接返回 {"images": [...]} 即时结果
    #     sync_mode=False 时 Fal API 返回 {"request_id": "..."} 进入队列
    def submit_edit(
        self,
        prompt: str,
        image_urls: List[str],
        model: str = "openai/gpt-image-2/edit",
        mask_image_url: Optional[str] = None,
        image_size: Any = "auto",
        quality: str = "auto",
        num_images: int = 1,
        output_format: str = "png",
        seed: int = 0,
        sync_mode: bool = False
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{model}"

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        payload = {
            'prompt': prompt,
            'image_urls': image_urls,
            'image_size': image_size,
            'quality': quality,
            'num_images': num_images,
            'output_format': output_format,
            'sync_mode': sync_mode
        }

        if mask_image_url:
            payload['mask_url'] = mask_image_url

        if seed > 0:
            payload['seed'] = seed

        print(f"\n[FalImageService] Submit edit request to: {url}")
        print(f"[FalImageService] Headers: {json.dumps({k: v for k, v in headers.items() if k != 'Authorization'})}")
        print_info = payload.copy()
        print_info['image_urls'] = f"[{len(print_info['image_urls'])} image URLs]"
        if 'mask_url' in print_info:
            print_info['mask_url'] = print_info['mask_url'][:60] + '...' if len(print_info['mask_url']) > 60 else print_info['mask_url']
        print(f"[FalImageService] Payload: {json.dumps(print_info, ensure_ascii=False, indent=2)}\n")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120, proxies={'http': None, 'https': None})
            response.raise_for_status()
            result = response.json()
            print(f"[FalImageService] Submit edit response: request_id={result.get('request_id', 'N/A')}, "
                  f"has_response_url={'response_url' in result}")
            return result
        except requests.exceptions.RequestException as e:
            error_message = _format_http_error(e)
            print(f"[FalImageService] Submit edit error: {error_message}")
            return {'error': error_message}

    # 查询任务在 fal.ai 队列中的当前状态
    # 改进：不再使用 raise_for_status() 吞噬响应体
    # 非 200 时尝试解析 body 中的 status 字段，
    # IN_QUEUE/IN_PROGRESS 返回正常结果继续轮询，
    # FAILED/FAILURE/CANCELLED 返回完整状态供调用方标记失败，
    # list 响应或含 detail 字段视为 API 错误
    def query_task_status(self, model: str, request_id: str, response_url: str = "") -> Dict[str, Any]:
        url = self._resolve_poll_url(response_url, model, request_id, "/status")

        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }

        print(f"\n[FalImageService] Query task status: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=30, proxies={'http': None, 'https': None})

            # 200 正常响应，直接解析返回
            if response.status_code == 200:
                result = response.json()
                status_raw = result.get('status', 'UNKNOWN')
                print(f"[FalImageService] Task {request_id} raw status: {status_raw}, queue_position: {result.get('queue_position', 'N/A')}")
                return result

            # 404 表示任务不存在
            if response.status_code == 404:
                print(f"[FalImageService] Task {request_id} not found (404)")
                return {'error': f'task not found (404), request_id={request_id}'}

            # 非 200 / 非 404：尝试解析响应体获取真实状态
            err_body = response.text[:1000]
            print(f"[FalImageService] Task {request_id} HTTP {response.status_code}: {err_body[:200]}")

            try:
                err_json = json.loads(err_body)
            except (json.JSONDecodeError, ValueError):
                err_json = None

            # 如果是 list 格式的错误响应
            if isinstance(err_json, list):
                err_detail = json.dumps(err_json[:1])[:300] if err_json else 'empty list'
                print(f"[FalImageService] Task {request_id} error list response: {err_detail}")
                return {'error': f'API error (list): {err_detail}'}

            # 如果是 dict 格式
            if isinstance(err_json, dict):
                # 包含 detail 字段（fal 标准错误格式）
                if 'detail' in err_json:
                    detail = str(err_json['detail'])[:500]
                    print(f"[FalImageService] Task {request_id} API error detail: {detail}")
                    return {'error': f'API error: {detail}'}

                # 提取 status 字段
                status_raw = err_json.get('status', '')

                # IN_QUEUE / IN_PROGRESS → 任务仍在队列中，返回正常结果让调用方继续轮询
                if status_raw in ('IN_QUEUE', 'IN_PROGRESS'):
                    print(f"[FalImageService] Task {request_id} HTTP {response.status_code} but status={status_raw}, continuing poll")
                    err_json['_http_status'] = response.status_code
                    return err_json

                # FAILED / FAILURE / CANCELLED → 任务已失败，返回完整状态
                if status_raw in ('FAILED', 'FAILURE', 'CANCELLED'):
                    print(f"[FalImageService] Task {request_id} terminal failure: status={status_raw}")
                    err_json['_http_status'] = response.status_code
                    return err_json

                # 有其他字段但非已知状态，尝试保留
                if status_raw:
                    print(f"[FalImageService] Task {request_id} unknown status in error body: {status_raw}")
                    err_json['_http_status'] = response.status_code
                    return err_json

            # 无法解析或没有可用状态信息
            return {'error': f'HTTP {response.status_code}: {err_body[:300]}'}

        except requests.exceptions.RequestException as e:
            print(f"[FalImageService] Query task status network error: {str(e)}")
            return {'error': str(e)}

    # 获取已完成任务的结果数据（包含生成的图片）
    def get_task_result(self, model: str, request_id: str, response_url: str = "") -> Dict[str, Any]:
        url = self._resolve_poll_url(response_url, model, request_id, "")

        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }

        print(f"\n[FalImageService] Get task result: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=120, proxies={'http': None, 'https': None})
            response.raise_for_status()
            result = response.json()
            image_count = len(result.get('images', [])) if isinstance(result.get('images'), list) else 0
            print(f"[FalImageService] Task {request_id} result: images={image_count}, prompt={result.get('prompt', 'N/A')[:50]}...")
            return result
        except requests.exceptions.RequestException as e:
            error_message = _format_http_error(e)
            print(f"[FalImageService] Get task result error: {error_message}")
            return {'error': error_message}

    # 将 fal.ai 原始状态映射为标准化状态字符串
    @staticmethod
    def normalize_status(status_str: str) -> str:
        status_map = {
            'IN_QUEUE': 'pending',
            'IN_PROGRESS': 'processing',
            'COMPLETED': 'success'
        }
        if not isinstance(status_str, str):
            return 'fail'
        return status_map.get(status_str, 'fail')
