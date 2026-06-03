import requests
import time
import json
import os
from io import BytesIO
from typing import Optional, Dict, Any, List


def find_nested_status(payload: Any) -> str:
    """
    递归提取任务状态

    功能描述：
        兼容第三方查询结果中状态不在顶层的情况，用于日志输出和排障

    实现逻辑：
        1. 字典先读取当前层 status
        2. 当前层没有时递归 value
        3. 列表则逐项递归查找
        4. 未找到时返回 UNKNOWN，避免误导为终态
    """
    if isinstance(payload, dict):
        status = payload.get('status')
        if isinstance(status, str) and status.strip():
            return status.strip()

        for value in payload.values():
            nested_status = find_nested_status(value)
            if nested_status != 'UNKNOWN':
                return nested_status

    if isinstance(payload, list):
        for item in payload:
            nested_status = find_nested_status(item)
            if nested_status != 'UNKNOWN':
                return nested_status

    return 'UNKNOWN'


class ImageService:
    # OpenAI 兼容图片生成/编辑 API 服务封装
    # 功能描述：
    #     封装与 OpenAI 兼容图片 API 的通信，使用 Session 连接池复用 TCP 连接
    # 实现逻辑：
    #     1. 初始化时创建 requests.Session，复用 TCP 连接
    #     2. 所有重试逻辑由 _make_request_with_retry 统一处理，避免 urllib3 与手动重试的双重重试
    #     3. 所有请求通过 self.session 发出，复用 TCP 连接
    def __init__(self, api_base_url: str, api_key: str, webhook_url: str = ''):
        self.api_base_url = api_base_url.rstrip('/')
        self.api_key = api_key
        self.webhook_url = webhook_url

        self.session = requests.Session()
        # 忽略系统代理环境变量，避免 Windows 系统代理不可用时导致请求失败
        self.session.trust_env = False

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def _json_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    # 带重试的 HTTP 请求发送方法
    # 功能描述：
    #     发送请求并在临时网络错误/服务器错误时自动重试
    #     参照 openai兼容，image-2尺寸遮罩参考.md 中的 make_request_with_retry 实现
    # 实现逻辑：
    #     1. 使用 Session（已配置 Retry adapter）发送请求
    #     2. 超时采用递增策略：首次 120s，每次重试×1.5，最大 300s
    #     3. 429 和 5xx 由 Retry adapter 自动处理
    #     4. Timeout 和 ConnectionError 由本方法手动重试
    # 异常处理：
    #     - 所有重试耗尽后仍失败时抛出原始异常，由调用方处理
    def _make_request_with_retry(self, url, data=None, files=None, json_data=None, method='POST', max_retries=3, initial_timeout=120):
        for attempt in range(1, max_retries + 1):
            current_timeout = min(int(initial_timeout * (1.5 ** (attempt - 1))), 300)
            try:
                if method == 'GET':
                    response = self.session.get(url, headers=self._auth_headers(), timeout=current_timeout)
                elif files is not None:
                    response = self.session.post(
                        url,
                        headers=self._auth_headers(),
                        data=data,
                        files=files,
                        timeout=current_timeout
                    )
                elif json_data is not None:
                    response = self.session.post(
                        url,
                        headers=self._json_headers(),
                        json=json_data,
                        timeout=current_timeout
                    )
                else:
                    response = self.session.post(
                        url,
                        headers=self._json_headers(),
                        timeout=current_timeout
                    )
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                if attempt == max_retries:
                    raise
                time.sleep(min(2 ** (attempt - 1), 60))
            except requests.exceptions.ConnectionError:
                if attempt == max_retries:
                    raise
                time.sleep(min(2 ** (attempt - 1), 60))
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code in (400, 401, 403):
                    raise
                if attempt == max_retries:
                    raise
                time.sleep(min(2 ** (attempt - 1), 60))

    # 提交图片生成请求到 OpenAI 兼容 API
    # 功能描述：
    #     向 /v1/images/generations 端点提交生图请求，支持同步和异步两种模式
    #     参照 openai 接入参考.md 中的参数规范，补充了 n、seed、moderation、background、output_format、output_compression 参数
    # 实现逻辑：
    #     1. 构建请求 URL，异步模式附加 ?async=true 查询参数
    #     2. 构建 JSON 请求体，所有可选参数仅在非默认值时发送
    #     3. 使用 Session + 重试机制发送请求
    #     4. 区分 HTTP 状态码错误和网络异常，提供精细化的 error_type
    # 异常处理：
    #     - HTTP 4xx：标记为 client_error，记录状态码
    #     - HTTP 5xx：标记为 server_error
    #     - 网络超时/连接异常：标记为 network_error
    #     - 所有异常都返回包含 error_type 的字典，不抛异常
    def generate_image(
        self,
        prompt: str,
        model: str = 'gpt-image-2',
        size: str = '1024x1024',
        quality: str = 'auto',
        response_format: str = 'url',
        async_mode: bool = False,
        n: int = 1,
        seed: int = 0,
        moderation: str = 'auto',
        background: str = 'auto',
        output_format: str = 'png',
        output_compression: int = 100,
        image: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        url = f"{self.api_base_url}/v1/images/generations"

        if async_mode:
            url += "?async=true"
        elif self.webhook_url:
            url += "?webhook=" + self.webhook_url

        payload = {
            'prompt': prompt,
            'model': model,
            'size': size,
            'response_format': response_format,
            'quality': quality,
        }

        if n > 1:
            payload['n'] = n

        if seed > 0:
            payload['seed'] = seed

        if moderation and moderation != 'auto':
            payload['moderation'] = moderation

        if background and background != 'auto':
            payload['background'] = background

        if output_format and output_format != 'png':
            payload['output_format'] = output_format

        if output_compression != 100 and output_format in ('jpeg', 'webp'):
            payload['output_compression'] = output_compression

        if self.webhook_url and not async_mode:
            payload['webhook'] = self.webhook_url

        if image:
            payload['image'] = image

        print(f"\n[ImageService] Making generation request to: {url}")
        print_info = {**payload, 'image': f"[{len(payload['image'])} reference images]"} if 'image' in payload else payload
        print(f"[ImageService] Payload: {json.dumps(print_info, ensure_ascii=False, indent=2)}\n")

        try:
            response = self._make_request_with_retry(url, json_data=payload, max_retries=3, initial_timeout=120)
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            error_body = ''
            try:
                error_body = e.response.text[:500] if e.response is not None else ''
            except Exception:
                pass
            error_type = 'rate_limit' if status_code == 429 else ('client_error' if 400 <= status_code < 500 else 'server_error')
            print(f"[ImageService] HTTP {status_code} error: {error_body}")
            return {'error': str(e), 'error_type': error_type, 'status_code': status_code, 'error_body': error_body}
        except requests.exceptions.Timeout:
            print(f"[ImageService] Request timeout for generation")
            return {'error': '请求超时，请稍后重试', 'error_type': 'timeout'}
        except requests.exceptions.ConnectionError as e:
            print(f"[ImageService] Connection error: {str(e)}")
            return {'error': '网络连接失败，请检查网络或 API 地址', 'error_type': 'network_error'}
        except requests.exceptions.RequestException as e:
            print(f"[ImageService] Request error: {str(e)}")
            return {'error': str(e), 'error_type': 'unknown'}

    # 提交图片编辑请求到 OpenAI 兼容 API
    # 功能描述：
    #     向 /v1/images/edits 端点提交图片编辑请求，支持同步和异步两种模式
    #     参照 openai 接入参考.md 中 img2img 模式的参数规范
    # 实现逻辑：
    #     1. 构建 multipart/form-data 请求体
    #     2. 参照 openai 接入参考.md：background、output_format、moderation、n 始终发送，response_format 和 seed 条件发送
    #     3. 多张参考图时使用 image[] 数组格式（与官方一致）
    #     4. 无输入图时自动发送白色空白图片作为占位图
    #     5. 异步模式附加 ?async=true 查询参数
    #     6. 使用 Session + 重试机制发送请求
    # 异常处理：
    #     - HTTP 4xx：标记为 client_error
    #     - HTTP 5xx：标记为 server_error
    #     - 429：标记为 rate_limit
    #     - 超时/连接异常：分别标记为 timeout/network_error
    def edit_image(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        mask_path: Optional[str] = None,
        model: str = 'gpt-image-2',
        size: str = 'auto',
        response_format: str = 'url',
        quality: str = 'auto',
        async_mode: bool = False,
        n: int = 1,
        seed: int = 0,
        moderation: str = 'auto',
        background: str = 'auto',
        output_format: str = 'png',
        reference_image_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        url = f"{self.api_base_url}/v1/images/edits"
        if async_mode:
            url += "?async=true"

        reference_image_paths = reference_image_paths or []
        request_meta = {
            'prompt': prompt,
            'model': model,
            'size': size,
            'quality': quality,
            'response_format': response_format,
            'async_mode': async_mode,
            'n': n,
            'seed': seed,
            'moderation': moderation,
            'background': background,
            'output_format': output_format,
            'has_mask': bool(mask_path),
            'has_main_image': bool(image_path),
            'reference_image_count': len(reference_image_paths)
        }
        print(f"\n[ImageService] Making edit request to: {url}")
        print(f"[ImageService] Payload: {json.dumps(request_meta, ensure_ascii=False, indent=2)}")

        opened_files = []

        # 如果没有提供主图，创建一个白色空白占位图
        if not image_path:
            from PIL import Image
            blank_img = Image.new('RGB', (1024, 1024), color='white')
            blank_buf = BytesIO()
            blank_img.save(blank_buf, format='PNG')
            blank_buf.seek(0)
            image_file = blank_buf
            image_filename = 'blank.png'
            image_mime = 'image/png'
        else:
            image_file = open(image_path, 'rb')
            opened_files.append(image_file)
            image_filename = os.path.basename(image_path)
            image_mime = 'image/png'

        try:
            # 参照 openai 接入参考.md：background、output_format、moderation、n 始终发送
            data = {
                'prompt': prompt,
                'model': model,
                'quality': quality,
                'size': size,
                'background': background,
                'output_format': output_format,
                'moderation': moderation,
                'n': str(n),
            }

            # 参照 openai 接入参考.md：response_format 和 seed 条件发送
            if response_format:
                data['response_format'] = response_format

            if seed > 0:
                data['seed'] = str(seed)

            # 构建文件列表
            # 多张参考图时使用 image[] 数组格式（与官方实现一致）
            if len(reference_image_paths) > 0:
                multipart_files = []
                multipart_files.append(('image', (image_filename, image_file, image_mime)))
                for ref_path in reference_image_paths:
                    ref_file = open(ref_path, 'rb')
                    opened_files.append(ref_file)
                    multipart_files.append(('image', (os.path.basename(ref_path), ref_file, 'image/png')))
            else:
                multipart_files = [
                    ('image', (image_filename, image_file, image_mime)),
                ]

            if mask_path:
                mask_file = open(mask_path, 'rb')
                opened_files.append(mask_file)
                multipart_files.append(('mask', (os.path.basename(mask_path), mask_file, 'image/png')))

            response = self._make_request_with_retry(
                url,
                data=data,
                files=multipart_files,
                max_retries=3,
                initial_timeout=120
            )
            result = response.json()
            print(f"[ImageService] Edit response status: {find_nested_status(result)}")
            print(f"[ImageService] Edit response keys: {list(result.keys())}")
            return result
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            error_body = ''
            try:
                error_body = e.response.text[:500] if e.response is not None else ''
            except Exception:
                pass
            error_type = 'rate_limit' if status_code == 429 else ('client_error' if 400 <= status_code < 500 else 'server_error')
            print(f"[ImageService] Edit HTTP {status_code} error: {error_body}")
            return {'error': str(e), 'error_type': error_type, 'status_code': status_code, 'error_body': error_body}
        except requests.exceptions.Timeout:
            print(f"[ImageService] Edit request timeout")
            return {'error': '请求超时，请稍后重试', 'error_type': 'timeout'}
        except requests.exceptions.ConnectionError as e:
            print(f"[ImageService] Edit connection error: {str(e)}")
            return {'error': '网络连接失败，请检查网络或 API 地址', 'error_type': 'network_error'}
        except requests.exceptions.RequestException as e:
            print(f"[ImageService] Edit request error: {str(e)}")
            return {'error': str(e), 'error_type': 'unknown'}
        finally:
            for opened_file in opened_files:
                try:
                    opened_file.close()
                except Exception:
                    pass

    # 查询异步任务状态
    # 功能描述：
    #     通过 task_id 查询图片生成任务的当前状态，支持轮询获取异步任务结果
    # 实现逻辑：
    #     1. 使用正确的 API 端点 /v1/images/tasks/{task_id} 查询任务状态
    #     2. 返回任务状态 (IN_PROGRESS / FAILURE / SUCCESS) 和相关数据
    #     3. 当状态为 SUCCESS 时，响应中包含生成的图片 URL 或 b64_json 数据
    #     4. 使用 Session + 重试机制发送请求
    # 异常处理：
    #     - HTTP 错误：返回包含 error_type 的字典
    #     - 网络异常：返回包含 error_type 的字典
    def query_task(self, task_id: str) -> Dict[str, Any]:
        url = f"{self.api_base_url}/v1/images/tasks/{task_id}"

        print(f"\n[ImageService] Querying task status: {url}")

        try:
            response = self._make_request_with_retry(
                url,
                method='GET',
                max_retries=3,
                initial_timeout=30
            )
            result = response.json()

            task_status = find_nested_status(result)
            print(f"[ImageService] Task {task_id} status: {task_status}")

            return result
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            error_body = ''
            try:
                error_body = e.response.text[:500] if e.response is not None else ''
            except Exception:
                pass
            error_type = 'rate_limit' if status_code == 429 else ('client_error' if 400 <= status_code < 500 else 'server_error')
            print(f"[ImageService] Query task HTTP {status_code} error: {error_body}")
            return {'error': str(e), 'error_type': error_type, 'status_code': status_code}
        except requests.exceptions.Timeout:
            print(f"[ImageService] Query task timeout for task {task_id}")
            return {'error': '查询超时', 'error_type': 'timeout'}
        except requests.exceptions.ConnectionError as e:
            print(f"[ImageService] Query task connection error: {str(e)}")
            return {'error': '网络连接失败', 'error_type': 'network_error'}
        except requests.exceptions.RequestException as e:
            print(f"[ImageService] Query task error: {str(e)}")
            return {'error': str(e), 'error_type': 'unknown'}

    def compress_image(self, image_url: str, quality: int = 90) -> Dict[str, Any]:
        return {
            'status': 'placeholder',
            'message': '无损压缩功能预留接口',
            'image_url': image_url,
            'quality': quality
        }
