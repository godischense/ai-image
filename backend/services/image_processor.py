import os
import base64
import uuid
from io import BytesIO
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image as PILImage


# 通用图片数据处理工具
# 功能描述：
#     提取 task_processor.py 和 images.py 中重复出现的图片处理逻辑到一个独立的类中
#     包括：b64_json 解码、图片本地保存、缩略图生成、URL 下载等
# 实现逻辑：
#     所有方法均为静态方法，无需实例化即可调用
#     每个方法独立处理一种图片格式，失败时返回明确的错误信息
class ImageDataProcessor:

    @staticmethod
    def save_b64_image(b64_data: str, output_dir: str, filename_prefix: str = '') -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        解码 base64 图片数据并保存为本地 PNG 文件

        功能描述：
            将 base64 编码的图片数据解码并保存到指定目录，返回本地路径和访问 URL

        实现逻辑：
            1. 解码 base64 字符串为二进制数据
            2. 生成唯一的文件名（uuid.hex）
            3. 确保目标目录存在
            4. 将图片数据写入本地文件（PNG 格式）
            5. 返回本地文件路径、静态访问 URL 和可能的错误信息

        参数：
            b64_data: base64 编码的图片数据字符串
            output_dir: 输出目录的绝对路径
            filename_prefix: 文件名前缀（可选）

        返回：
            (local_path, static_url, error) 三元组，成功时 error 为 None
        """
        if not b64_data:
            return None, None, 'b64_json 数据为空'

        try:
            image_bytes = base64.b64decode(b64_data)
        except Exception as e:
            return None, None, f'base64 解码失败: {str(e)}'

        try:
            os.makedirs(output_dir, exist_ok=True)
            prefix = f"{filename_prefix}_" if filename_prefix else ''
            filename = f"{prefix}{uuid.uuid4().hex}.png"
            local_path = os.path.join(output_dir, filename)

            with open(local_path, 'wb') as f:
                f.write(image_bytes)

            static_url = f"/api/static/generated_images/{filename}"

            return local_path, static_url, None

        except Exception as e:
            return None, None, f'保存图片文件失败: {str(e)}'

    @staticmethod
    def save_b64_image_with_thumbnail(
        b64_data: str,
        output_dir: str,
        generated_images_dir: str,
        filename_prefix: str = ''
    ) -> Dict[str, Any]:
        """
        解码 base64 图片数据，保存本地文件并生成缩略图

        功能描述：
            一次性完成 b64_json → 本地原图 + 本地缩略图的完整流程

        实现逻辑：
            1. 调用 save_b64_image 保存原图
            2. 调用 create_thumbnail_from_local 生成缩略图
            3. 聚合返回所有路径和 URL

        返回：
            包含 local_path、url、thumbnail_path、thumbnail_url 和 error 的字典
        """
        local_path, static_url, error = ImageDataProcessor.save_b64_image(
            b64_data, generated_images_dir, filename_prefix
        )

        if error:
            return {
                'local_path': None,
                'url': '',
                'thumbnail_path': None,
                'thumbnail_url': '',
                'error': error
            }

        thumbnail_url = ''
        thumbnail_path = None
        try:
            from services.thumbnail_service import create_thumbnail_from_local
            thumb_result = create_thumbnail_from_local(local_path)
            thumbnail_url = thumb_result.get('thumbnail_url', '')
            thumbnail_path = thumb_result.get('thumbnail_path')
        except Exception as thumb_err:
            print(f"[ImageDataProcessor] Thumbnail generation failed: {thumb_err}")

        return {
            'local_path': local_path,
            'url': static_url,
            'thumbnail_path': thumbnail_path,
            'thumbnail_url': thumbnail_url,
            'error': None
        }

    @staticmethod
    def process_data_items(
        data_items: List[Dict],
        output_dir: str,
        task_id: str = '',
        prefer_b64: bool = True
    ) -> List[Dict[str, Any]]:
        """
        批量处理 API 返回的图片数据项

        功能描述：
            遍历 data 数组中的每张图片，提取 url 或 b64_json，统一转为本地路径

        实现逻辑：
            1. 优先处理 b64_json（prefer_b64=True 时），因为本地化速度更快
            2. 不包含 b64_json 时提取 url
            3. 每项处理失败时记录错误但继续处理后续项
            4. 返回所有成功处理的图片信息列表

        参数：
            data_items: API 返回的 data 数组
            output_dir: 图片输出目录
            task_id: 关联的任务 ID（用于日志）
            prefer_b64: 是否优先使用 b64_json

        返回：
            图片信息字典列表，每项包含 type(b64_json/url)、url、local_path、error 等
        """
        results = []

        if not isinstance(data_items, list):
            data_items = [data_items] if data_items else []

        for idx, item in enumerate(data_items):
            if not isinstance(item, dict):
                continue

            item_b64 = item.get('b64_json', '') or ''
            item_url = item.get('url', '') or ''

            if prefer_b64 and item_b64:
                local_path, static_url, error = ImageDataProcessor.save_b64_image(
                    item_b64, output_dir, f"task_{task_id}_{idx}"
                )
                results.append({
                    'index': idx,
                    'type': 'b64_json',
                    'url': static_url or '',
                    'local_path': local_path,
                    'original_b64': item_b64,
                    'error': error
                })
                if error:
                    print(f"[ImageDataProcessor] Item {idx} b64_json save failed: {error}")
            elif item_url:
                results.append({
                    'index': idx,
                    'type': 'url',
                    'url': item_url,
                    'local_path': None,
                    'error': None
                })
            elif item_b64:
                local_path, static_url, error = ImageDataProcessor.save_b64_image(
                    item_b64, output_dir, f"task_{task_id}_{idx}"
                )
                results.append({
                    'index': idx,
                    'type': 'b64_json',
                    'url': static_url or '',
                    'local_path': local_path,
                    'original_b64': item_b64,
                    'error': error
                })
            else:
                results.append({
                    'index': idx,
                    'type': 'empty',
                    'url': '',
                    'local_path': None,
                    'error': '图片数据项既无 url 也无 b64_json'
                })

        return results

    @staticmethod
    def process_single_image_item(
        item: Dict,
        output_dir: str,
        task_id: str = ''
    ) -> Optional[Tuple[str, str]]:
        """
        处理单个图片数据项，返回 (url, local_path)

        功能描述：
            简化版处理器，只取第一个可用的图片（b64_json 优先，其次 url）

        实现逻辑：
            1. 检查 b64_json 字段，有则解码保存
            2. 没有 b64_json 则取 url 字段
            3. 都没有返回 None

        返回：
            (url_or_static_url, local_path_or_None) 元组，失败返回 None
        """
        if not isinstance(item, dict):
            return None

        b64_data = item.get('b64_json', '') or ''
        image_url = item.get('url', '') or ''

        if b64_data:
            local_path, static_url, error = ImageDataProcessor.save_b64_image(
                b64_data, output_dir, f"task_{task_id}"
            )
            if error:
                print(f"[ImageDataProcessor] Single item b64 save failed: {error}")
                return None
            return (static_url, local_path)

        if image_url:
            return (image_url, None)

        return None

    @staticmethod
    def get_output_dir() -> str:
        """
        获取 generated_images 目录的绝对路径

        功能描述：
            统一计算 generated_images 目录路径，避免各模块重复写路径拼接逻辑
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(project_root, 'generated_images')

    @staticmethod
    def strip_b64_prefix(b64_data: str) -> str:
        """
        剥离 base64 Data URL 前缀

        功能描述：
            某些 API 返回的 b64_json 带有 data:image/...;base64, 前缀，直接解码会失败
            需要先剥离此前缀，只保留纯 base64 数据
            参照 openai兼容，image-2尺寸遮罩参考.md 中的 _decode_b64_url_one 方法

        实现逻辑：
            1. 检查是否以 "data:" 开头
            2. 寻找 ";base64," 分隔符，取其后部分
            3. 也兼容 "data:image/png;base64," 格式直接切片
            4. 无前缀则原样返回
        """
        if not b64_data:
            return b64_data

        if b64_data.startswith("data:"):
            if ";base64," in b64_data:
                return b64_data.split(";base64,", 1)[-1]
            comma_idx = b64_data.find(",")
            if comma_idx != -1:
                return b64_data[comma_idx + 1:]

        if b64_data.startswith("data:image/png;base64,"):
            return b64_data[len("data:image/png;base64,"):]

        return b64_data

    @staticmethod
    def downscale_image(image_path: str, max_edge: int = 3840) -> Tuple[Optional[str], Optional[str]]:
        """
        对超过指定长边的图片进行等比缩小

        功能描述：
            参照 openai兼容，image-2尺寸遮罩参考.md 中的 downscale_input 函数
            gpt-image-2 API 要求输入图片长边 ≤ 3840px，本方法自动缩放超限图片

        实现逻辑：
            1. 用 PIL 打开图片获取原始尺寸
            2. 如果长边 ≤ max_edge，直接返回原路径
            3. 超过时计算缩小比例，使用 LANCZOS 算法缩放
            4. 保存到临时目录（backend/temp/）并返回新路径

        参数：
            image_path: 原始图片路径
            max_edge: 最大允许的长边像素

        返回：
            (output_path, error) 元组，成功时 error 为 None
        """
        if not image_path or not os.path.isfile(image_path):
            return image_path, None

        try:
            img = PILImage.open(image_path)
            width, height = img.size
            max_dim = max(width, height)

            if max_dim <= max_edge:
                return image_path, None

            scale = max_edge / max_dim
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = img.resize((new_width, new_height), PILImage.LANCZOS)

            temp_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'backend', 'temp'
            )
            os.makedirs(temp_dir, exist_ok=True)

            output_filename = f"downscaled_{uuid.uuid4().hex}.png"
            output_path = os.path.join(temp_dir, output_filename)
            img.save(output_path, format='PNG')

            print(f"[ImageDataProcessor] Downscaled image {width}x{height} → {new_width}x{new_height}")
            return output_path, None

        except Exception as e:
            return image_path, f'图片缩小失败: {str(e)}'

    @staticmethod
    def validate_gpt_image2_size(size_str: str) -> Tuple[bool, Optional[str]]:
        """
        验证图片尺寸是否符合 gpt-image-2 API 要求

        功能描述：
            参照 openai兼容，image-2尺寸遮罩参考.md 中的 _validate_gpt_image2_size 方法
            gpt-image-2 要求：长边 ≤ 3840，宽高比 ≤ 3:1，总像素在 [655360, 8294400] 之间

        实现逻辑：
            1. "auto" 直接通过
            2. 解析 "WxH" 格式字符串
            3. 依次检查长边上限、宽高比上限、总像素范围

        参数：
            size_str: 尺寸字符串，格式如 "1024x1024" 或 "auto"

        返回：
            (valid, error_message) 元组
        """
        if size_str == "auto":
            return True, None

        import re
        m = re.match(r"^(\d+)x(\d+)$", size_str.strip())
        if not m:
            return False, f"size 格式须为 宽x高，例如 1024x1024，当前值: {size_str}"

        w, h = int(m.group(1)), int(m.group(2))

        if max(w, h) > 3840:
            return False, f"长边须 ≤ 3840px，当前: {max(w, h)}px"

        lo, hi = min(w, h), max(w, h)
        if hi / lo > 3.0 + 1e-9:
            return False, f"长边:短边 不得超过 3:1，当前: {hi}:{lo}"

        px = w * h
        if px < 655360 or px > 8294400:
            return False, f"总像素须在 655,360～8,294,400 之间，当前: {px}"

        return True, None
