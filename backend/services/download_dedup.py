"""
图片下载去重模块

功能描述：
    在最底层拦截"同 URL 在短时间内被下载多次"导致的重复文件问题。
    解决 task_processor / background_download_service 幂等保护在跨进程/重启场景下失效时，
    同一 URL 仍被多次下载到不同文件名（不同 uuid）的孤儿文件堆积问题。

实现逻辑：
    1. 接收远程图片 URL、生成本次预期的新文件名（包含 url_hash + uuid）。
    2. 扫描存储目录下文件名以 url_hash 开头的近期文件，命中则直接复用，
       不再发 HTTP 请求；返回的 local_path 与新生成的 local_path 语义等价。
    3. 默认窗口 120 秒（覆盖 task_processor 重试/重启/竞态的时间跨度）。
    4. 任意步骤异常走 fail-open：返回 None 让调用方走正常下载流程，
       避免因本模块异常把整个下载流程卡住。

异常处理：
    - 目录不存在：返回 None，不创建目录（download 流程会自己创建）
    - 单个文件 stat 异常：跳过该文件继续扫描
    - URL 异常（非字符串）：返回 None
    - 文件大小为 0（下载未完成）：跳过该文件
"""
import os
import re
import hashlib
import time
from typing import Optional


# 默认去重时间窗口（秒）：覆盖一次任务的完整生命周期（提交→轮询→下载）
DEFAULT_DEDUP_WINDOW_SECONDS = 120

# 文件名格式：generated_<YYYYMMDD>_<HHMMSS>_<url_hash>_<uuid>.<ext>
# 共 4 段：date 8 位 + time 6 位 + url_hash 8 位 hex + uuid 8 位 hex
URL_HASH_PATTERN = re.compile(r'^generated_(\d{8})_(\d{6})_([0-9a-f]+)_([0-9a-f]+)\.[A-Za-z0-9]+$')


def extract_url_hash_from_url(image_url: str) -> Optional[str]:
    """
    从远程图片 URL 提取 url_hash（与 DownloadService._generate_filename 保持一致）

    参数：
        image_url: 远程图片 URL

    返回：
        url_hash 前 8 位，无法计算时返回 None
    """
    if not isinstance(image_url, str) or not image_url.strip():
        return None
    try:
        return hashlib.md5(image_url.encode()).hexdigest()[:8]
    except Exception:
        return None


def _parse_file_timestamp(filename: str) -> Optional[int]:
    """
    从文件名解析时间戳（秒级）

    参数：
        filename: 形如 generated_20260609_140147_<url_hash>_<uuid>.<ext>

    返回：
        Unix 时间戳，无法解析时返回 None
    """
    match = URL_HASH_PATTERN.match(filename)
    if not match:
        return None
    date_part, time_part = match.group(1), match.group(2)
    try:
        # 文件名时间戳精度只到秒
        return int(time.mktime(time.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")))
    except Exception:
        return None


def find_recent_same_url_file(
    image_url: str,
    storage_dir: str,
    window_seconds: int = DEFAULT_DEDUP_WINDOW_SECONDS,
    current_timestamp: Optional[int] = None
) -> Optional[str]:
    """
    查找存储目录下、文件名含相同 url_hash 且在指定时间窗口内的本地文件

    参数：
        image_url: 远程图片 URL
        storage_dir: 本地存储目录（绝对路径）
        window_seconds: 去重时间窗口秒数
        current_timestamp: 当前时间戳（秒），为 None 时使用 time.time()

    返回：
        命中的本地文件绝对路径；无命中返回 None
    """
    url_hash = extract_url_hash_from_url(image_url)
    if not url_hash:
        return None

    if not storage_dir or not os.path.isdir(storage_dir):
        return None

    now_ts = current_timestamp if current_timestamp is not None else int(time.time())
    window_start = now_ts - window_seconds

    try:
        # 一次性读出目录项；listdir 失败时直接返回 None
        with os.scandir(storage_dir) as entries:
            candidates = []
            for entry in entries:
                if not entry.is_file(follow_symlinks=False):
                    continue
                filename = entry.name
                # 仅检查与 url_hash 完全匹配的文件，跳过其它无关文件
                file_hash = _extract_url_hash_from_filename(filename)
                if file_hash != url_hash:
                    continue
                # 文件大小为 0 视为下载未完成的中间产物，跳过
                try:
                    if entry.stat().st_size <= 0:
                        continue
                except Exception:
                    continue
                file_ts = _parse_file_timestamp(filename)
                if file_ts is None:
                    continue
                # 必须在时间窗口内（避免命中太老的同名 url_hash 文件）
                if file_ts < window_start:
                    continue
                candidates.append((file_ts, entry.path))
    except Exception:
        return None

    if not candidates:
        return None

    # 选时间戳最大的（最新一次下载的产物），最符合"同一次任务最近一次结果"语义
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_url_hash_from_filename(filename: str) -> Optional[str]:
    """
    从文件名中解析出 url_hash 段（第 3 段，8 位 hex）

    参数：
        filename: 文件名

    返回：
        url_hash 字符串，不匹配返回 None
    """
    match = URL_HASH_PATTERN.match(filename)
    if not match:
        return None
    return match.group(3)
