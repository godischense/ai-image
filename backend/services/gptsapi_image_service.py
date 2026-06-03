import json
import time
from typing import Any, Dict, List, Optional

import requests


class GptsApiImageService:
    """
    GPTsAPI gpt-image-2 text-to-image / image-edit service.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.gptsapi.net"):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.gptsapi.net").rstrip("/")
        self.timeout = 600
        self.session = requests.Session()
        self.session.trust_env = False

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # 执行 POST 请求，不轮询，返回原始响应
    # 用于异步模式：调用方自己处理轮询
    def _post_init(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        print(f"\n[GptsApiImageService] POST {url}")
        print(f"[GptsApiImageService] Payload: {json.dumps(self._redact_payload(payload), ensure_ascii=False, indent=2)}")
        try:
            response = self.session.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            status_code = err.response.status_code if err.response is not None else 0
            error_body = err.response.text[:1000] if err.response is not None else ""
            print(f"[GptsApiImageService] HTTP {status_code}: {error_body[:300]}")
            return {
                "error": str(err),
                "status_code": status_code,
                "error_body": error_body,
            }
        except requests.exceptions.Timeout:
            return {"error": "请求超时，请稍后重试", "error_type": "timeout"}
        except requests.exceptions.RequestException as err:
            return {"error": str(err), "error_type": "network_error"}
        except ValueError as err:
            return {"error": f"响应不是有效 JSON: {str(err)}"}

    # 执行 POST 并同步轮询直到完成（同步模式）
    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self._post_init(endpoint, payload)
        if 'error' in result:
            return result

        # GPTsAPI 的 POST 响应总是 data.status="created" + outputs=[]，
        # 需要通过 data.urls.get 查询获取完整结果
        data = result.get('data', {}) or {}
        if isinstance(data, dict) and data.get('status') in ('created', 'processing') and data.get('urls', {}).get('get'):
            poll_url = data['urls']['get']
            print(f"[GptsApiImageService] Task created, polling: {poll_url}")
            return self._poll_until_result(poll_url)

        return result

    def _poll_until_result(self, poll_url: str) -> Dict[str, Any]:
        url = poll_url if poll_url.startswith("http") else f"{self.base_url}{poll_url}"
        max_attempts = 120
        for attempt in range(max_attempts):
            try:
                resp = self.session.get(url, headers=self._headers(), timeout=30)
                resp.raise_for_status()
                query_result = resp.json()
                data = query_result.get('data', {}) or {}
                status = data.get('status', '')
                if status == 'completed':
                    print(f"[GptsApiImageService] Poll completed after {attempt + 1} attempts")
                    return query_result
                if status in ('failed', 'error') or data.get('error'):
                    error_msg = data.get('error') or 'GPTsAPI 处理失败'
                    print(f"[GptsApiImageService] Poll failed: {error_msg}")
                    return {'error': error_msg, 'raw_query_result': query_result}
                print(f"[GptsApiImageService] Poll attempt {attempt + 1}/{max_attempts}: status={status}")
            except requests.exceptions.RequestException as err:
                print(f"[GptsApiImageService] Poll error: {err}")
            time.sleep(2)
        print(f"[GptsApiImageService] Poll timeout after {max_attempts} attempts")
        return {'error': 'GPTsAPI 查询超时，请稍后重试', 'error_type': 'poll_timeout'}

    @staticmethod
    def _redact_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        redacted = dict(payload)
        if isinstance(redacted.get("input_urls"), list):
            redacted["input_urls"] = f"[{len(redacted['input_urls'])} image URLs]"
        return redacted

    def text_to_image(self, prompt: str, aspect_ratio: str = "1:1", resolution: str = "2K") -> Dict[str, Any]:
        return self._post(
            "/api/v3/openai/gpt-image-2/text-to-image",
            {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio or "1:1",
                "resolution": resolution or "2K",
            },
        )

    # 创建文生图任务（异步模式），只提交不轮询，返回 poll_url 供后台 TaskProcessor 使用
    def create_text_to_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "2K",
    ) -> Dict[str, Any]:
        result = self._post_init(
            "/api/v3/openai/gpt-image-2/text-to-image",
            {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio or "1:1",
                "resolution": resolution or "2K",
            },
        )
        if 'error' in result:
            return result
        data = result.get('data', {}) or {}
        if isinstance(data, dict) and data.get('urls', {}).get('get'):
            poll_url = data['urls']['get']
            print(f"[GptsApiImageService] Async text-to-image created, poll_url: {poll_url}")
            return {'poll_url': poll_url, 'status': data.get('status', 'created'), 'raw_response': result}
        error_data = data if isinstance(data, dict) else {}
        return {'error': error_data.get('error') or 'GPTsAPI 未返回轮询地址', 'raw_response': result}

    def image_edit(
        self,
        prompt: str,
        input_urls: List[str],
        aspect_ratio: str = "auto",
        resolution: str = "1K",
    ) -> Dict[str, Any]:
        return self._post(
            "/api/v3/openai/gpt-image-2/image-edit",
            {
                "prompt": prompt,
                "input_urls": input_urls,
                "aspect_ratio": aspect_ratio or "auto",
                "resolution": resolution or "1K",
            },
        )

    # 创建编辑任务（异步模式），只提交不轮询，返回 poll_url 供后台 TaskProcessor 使用
    def create_image_edit(
        self,
        prompt: str,
        input_urls: List[str],
        aspect_ratio: str = "auto",
        resolution: str = "1K",
    ) -> Dict[str, Any]:
        result = self._post_init(
            "/api/v3/openai/gpt-image-2/image-edit",
            {
                "prompt": prompt,
                "input_urls": input_urls,
                "aspect_ratio": aspect_ratio or "auto",
                "resolution": resolution or "1K",
            },
        )
        if 'error' in result:
            return result
        data = result.get('data', {}) or {}
        if isinstance(data, dict) and data.get('urls', {}).get('get'):
            poll_url = data['urls']['get']
            print(f"[GptsApiImageService] Async task created, poll_url: {poll_url}")
            return {'poll_url': poll_url, 'status': data.get('status', 'created'), 'raw_response': result}
        error_data = data if isinstance(data, dict) else {}
        return {'error': error_data.get('error') or 'GPTsAPI 未返回轮询地址', 'raw_response': result}

    def query_result(self, poll_url: str) -> Dict[str, Any]:
        url = poll_url if poll_url.startswith("http") else f"{self.base_url}{poll_url}"
        print(f"\n[GptsApiImageService] GET {url}")
        try:
            response = self.session.get(url, headers=self._headers(), timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as err:
            print(f"[GptsApiImageService] Query failed: {err}")
            return {"error": str(err)}
