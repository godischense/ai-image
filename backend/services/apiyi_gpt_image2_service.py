import json
import mimetypes
import os
import time
from typing import Any, Dict, List, Optional

import requests


class ApiyiGptImage2Service:
    """APIYI gpt-image-2 client using the official image endpoints."""

    MAX_RETRIES = 2
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(self, api_key: str, base_url: str = "https://api.apiyi.com"):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.apiyi.com").rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    @staticmethod
    def _sleep_for_retry(response: Optional[requests.Response], attempt: int) -> None:
        wait_seconds = 0
        if response is not None:
            retry_after = response.headers.get("Retry-After", "").strip()
            if retry_after.isdigit():
                wait_seconds = min(int(retry_after), 120)
        if wait_seconds <= 0:
            wait_seconds = min(2 ** attempt, 60)
        print(f"[ApiyiGptImage2Service] retry backoff: sleep {wait_seconds}s (attempt={attempt})")
        try:
            time.sleep(wait_seconds)
        except Exception:
            pass

    def _post_with_retry(
        self,
        url: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[List[Any]] = None,
        timeout: int = 600,
    ) -> requests.Response:
        last_response: Optional[requests.Response] = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                if files is not None:
                    response = self.session.post(
                        url,
                        headers=self._headers(),
                        data=data,
                        files=files,
                        timeout=timeout,
                    )
                else:
                    response = self.session.post(
                        url,
                        headers=self._headers(),
                        json=json_body,
                        timeout=timeout,
                    )
                last_response = response
                if response.status_code == 200:
                    return response
                if response.status_code not in self.RETRYABLE_STATUS:
                    return response
                if attempt >= self.MAX_RETRIES:
                    return response
                self._sleep_for_retry(response, attempt + 1)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt >= self.MAX_RETRIES:
                    raise
                self._sleep_for_retry(last_response, attempt + 1)
        if last_response is None:
            raise RuntimeError("APIYI gpt-image-2 request produced no response")
        return last_response

    def _build_error(self, err: Exception) -> Dict[str, Any]:
        if isinstance(err, requests.exceptions.HTTPError):
            status_code = 0
            error_body = ""
            if err.response is not None:
                status_code = err.response.status_code
                error_body = (err.response.text or "")[:1000]
            return {
                "error": f"APIYI gpt-image-2 HTTP {status_code}: {error_body[:200]}",
                "status_code": status_code,
                "error_body": error_body,
                "error_type": "http_error",
            }
        if isinstance(err, requests.exceptions.Timeout):
            return {
                "error": "APIYI gpt-image-2 request timed out",
                "error_type": "timeout",
            }
        if isinstance(err, requests.exceptions.RequestException):
            return {
                "error": f"APIYI gpt-image-2 network error: {err}",
                "error_type": "network_error",
            }
        if isinstance(err, ValueError):
            return {
                "error": f"APIYI gpt-image-2 response is not valid JSON: {err}",
                "error_type": "invalid_json",
            }
        return {
            "error": f"APIYI gpt-image-2 unknown error: {err}",
            "error_type": "unknown",
        }

    @staticmethod
    def _clean_common_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        params = dict(params or {})
        params.setdefault("background", "auto")
        if params.get("background") == "transparent":
            params["background"] = "opaque"
        if params.get("output_format") == "png":
            params.pop("output_compression", None)
        return {k: v for k, v in params.items() if v not in (None, "")}

    @staticmethod
    def _timeout_for_quality(params: Optional[Dict[str, Any]]) -> int:
        quality = str((params or {}).get("quality") or "auto").strip().lower()
        return {
            "low": 120,
            "medium": 240,
            "high": 600,
        }.get(quality, 600)

    def text_to_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        model: str = "gpt-image-2",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/images/generations"
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        payload.update(self._clean_common_params(params))
        print(f"[ApiyiGptImage2Service] POST {url}")
        print(f"[ApiyiGptImage2Service] payload: {json.dumps(payload, ensure_ascii=False)}")
        try:
            response = self._post_with_retry(url, json_body=payload, timeout=self._timeout_for_quality(payload))
            response.raise_for_status()
            return response.json()
        except Exception as err:
            print(f"[ApiyiGptImage2Service] text_to_image failed: {err}")
            return self._build_error(err)

    def image_edit(
        self,
        prompt: str,
        image_paths: List[str],
        mask_path: Optional[str] = None,
        size: str = "1024x1024",
        model: str = "gpt-image-2",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/images/edits"
        data = {
            "model": model,
            "prompt": prompt,
            "size": size,
        }
        edit_params = self._clean_common_params(params)
        edit_params.pop("moderation", None)
        edit_params.pop("n", None)
        data.update(edit_params)

        opened_files = []
        files = []
        try:
            for path in image_paths[:16]:
                fp = open(path, "rb")
                opened_files.append(fp)
                filename = os.path.basename(path) or "image.png"
                mime = mimetypes.guess_type(filename)[0] or "image/png"
                files.append(("image[]", (filename, fp, mime)))
            if mask_path:
                mask_fp = open(mask_path, "rb")
                opened_files.append(mask_fp)
                files.append(("mask", (os.path.basename(mask_path) or "mask.png", mask_fp, "image/png")))
            print(f"[ApiyiGptImage2Service] POST {url}")
            print(f"[ApiyiGptImage2Service] data: {json.dumps(data, ensure_ascii=False)}, images: {len(image_paths)}, mask: {bool(mask_path)}")
            response = self._post_with_retry(url, data=data, files=files, timeout=self._timeout_for_quality(data))
            response.raise_for_status()
            return response.json()
        except Exception as err:
            print(f"[ApiyiGptImage2Service] image_edit failed: {err}")
            return self._build_error(err)
        finally:
            for fp in opened_files:
                try:
                    fp.close()
                except Exception:
                    pass
