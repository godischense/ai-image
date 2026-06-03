import requests
import json
from typing import Optional


class FileUploadService:
    """
    文件上传服务

    功能描述：
        将图片文件上传到 /v1/files API，获取临时访问 URL。
        用于替代 base64 Data URL，减少 JSON 请求体大小。

    实现逻辑：
        1. POST {base_url}/v1/files，multipart/form-data 方式上传
        2. 响应有 url 字段 → 直接返回 url
        3. 响应只有 id → 构造 {base_url}/v1/files/{id}/content 作为文件访问 URL
        4. 任何失败返回 None，由调用方 fallback 到 base64
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = 120

    # 上传图片到 /v1/files API，返回可访问的 URL
    # 功能描述：
    #     以 multipart/form-data 方式上传图片二进制数据
    #     优先取响应中的 url 字段，回退到用 id 构造 URL
    def upload(self, image_data: bytes, filename: str = "image.png") -> Optional[str]:
        try:
            files = {'file': (filename, image_data, 'image/png')}
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.post(
                f"{self.base_url}/v1/files",
                headers=headers,
                files=files,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )
            response.raise_for_status()
            result = response.json()

            if 'url' in result and result['url']:
                print(f"[FileUploadService] Uploaded, got url: {result['url'][:80]}...")
                return result['url']

            if 'id' in result and result['id']:
                constructed_url = f"{self.base_url}/v1/files/{result['id']}/content"
                print(f"[FileUploadService] Uploaded, constructed url from id {result['id']}: {constructed_url[:80]}...")
                return constructed_url

            print(f"[FileUploadService] Unexpected upload response (no url or id): {json.dumps(result, ensure_ascii=False)[:200]}")
            return None
        except Exception as e:
            print(f"[FileUploadService] Upload failed: {str(e)}")
            return None
