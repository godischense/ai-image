"""
数据库配置模型模块

功能描述：
    负责将设置页的配置统一存储到 SQLite 数据库中。
    数据库是唯一数据源，不存在任何文件到数据库的自动迁移。

实现逻辑：
    1. 通过 app_config 表按模块保存配置 JSON
    2. 读取时直接从数据库获取，数据库为空时使用默认值填充
    3. 对外暴露统一的获取、保存方法，供路由层和业务层复用
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any

from .database import get_db_connection

logger = logging.getLogger(__name__)

CONFIG_KEYS = ('image_api', 'server', 'prompt_optimize', 'fal_api', 'gptsapi_api', 'file_upload', 'social_copy_api', 'topaz_gigapixel')
DEFAULT_CONFIGS = {
    'image_api': {
        'baseUrl': 'https://api.openai.com',
        'apiKey': '',
        'isAsync': False,
        'imageModels': ['gpt-image-2', 'dall-e-3']
    },
    'server': {
        'port': 5678
    },
    'prompt_optimize': {
        'baseUrl': 'https://api.openai.com',
        'apiKey': '',
        'model': 'gpt-4o',
        'systemPrompt': '你是一个专业的图像提示词优化专家。请将用户输入的提示词优化为更详细、更适合图像生成的描述。优化后的提示词应该：1. 更具体清晰 2. 包含更多细节描述 3. 适合作为图像生成的输入。请直接返回JSON格式：{"optimized_prompt": "优化后的提示词内容"}，不要包含任何其他内容或解释。',
        'systemPrompts': [
            {
                'id': 'default',
                'name': '默认优化',
                'content': '你是一个专业的图像提示词优化专家。请将用户输入的提示词优化为更详细、更适合图像生成的描述。优化后的提示词应该：1. 更具体清晰 2. 包含更多细节描述 3. 适合作为图像生成的输入。请直接返回JSON格式：{"optimized_prompt": "优化后的提示词内容"}，不要包含任何其他内容或解释。'
            }
        ],
        'selectedSystemPromptId': 'default'
    },
    'fal_api': {
        'apiKey': '',
        'falModels': ['openai/gpt-image-2', 'openai/gpt-image-2/edit']
    },
    'gptsapi_api': {
        'baseUrl': 'https://api.gptsapi.net',
        'apiKey': ''
    },
    'file_upload': {
        'baseUrl': 'https://ai.t8star.cn',
        'apiKey': ''
    },
    'social_copy_api': {
        'baseUrl': '',
        'apiKey': '',
        'model': '',
        'systemPrompt': ''
    },
    'topaz_gigapixel': {
        # Topaz Gigapixel AI 本地可执行文件路径（Windows）
        'exePath': r'C:\Program Files\Topaz Labs LLC\Topaz Gigapixel AI\gigapixel.exe',
        # 是否使用 'gigapixel' 系统命令（已加入 PATH），否则用完整 exe 路径
        'useSystemCommand': False,
        # 单图放大默认参数（与 ComfyUI-GigapixelAI 节点 GigapixelUpscaleSettings 字段一一对应）
        # 重要：gigapixel.exe 命令行只有当参数 > 0 时才会真正传递；设为 0 等同于「不传该参数，使用 Topaz 内部默认」
        'defaultScale': 2.0,
        'defaultModel': 'Standard',
        'defaultEnabled': True,
        # 官方节点默认 sharpen=1 / denoise=1 / compression=67 / fr=50 / pre_downscaling=75
        'defaultSharpen': 1,
        'defaultDenoise': 1,
        'defaultCompression': 67,
        'defaultFr': 50,
        'defaultPreDownscaling': 75,
        # 后台 worker 并发数（Topaz 吃 GPU/CPU，默认 1 串行更稳）
        'maxParallel': 1,
        # 单图处理超时（秒）
        'timeout': 600
    }
}


def get_default_config(config_key: str) -> Dict[str, Any]:
    """
    获取配置默认值

    功能描述：
        返回指定配置模块的默认结构，避免数据库空值导致调用方字段缺失。
    """
    return json.loads(json.dumps(DEFAULT_CONFIGS.get(config_key, {})))


# 归一化配置结构
#
# 功能描述：
#     使用默认值补齐数据库缺失字段，保证接口和业务层拿到稳定结构。
def normalize_config_value(config_key: str, config_value: Dict[str, Any]) -> Dict[str, Any]:
    default_config = get_default_config(config_key)
    normalized_config = {**default_config}
    if isinstance(config_value, dict):
        normalized_config.update(config_value)
    return normalized_config


# 读取单个数据库配置
#
# 功能描述：
#     从 app_config 表读取指定模块配置，未找到时返回空字典。
def get_db_config(config_key: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT config_value FROM app_config WHERE config_key = ?',
        (config_key,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {}

    try:
        return json.loads(row['config_value']) if row['config_value'] else {}
    except json.JSONDecodeError as e:
        logger.error('[ConfigModel] 解析配置 [%s] JSON 失败: %s, 原始值: %s', config_key, str(e), row['config_value'])
        return {}


# 保存单个数据库配置
#
# 功能描述：
#     将指定模块配置写入数据库，使用 UPSERT 保证重复保存时覆盖旧值。
#
# 异常处理：
#     - 非法配置键时抛出 ValueError
#     - 非字典配置时抛出 ValueError
def save_db_config(config_key: str, config_value: Dict[str, Any]) -> Dict[str, Any]:
    if config_key not in CONFIG_KEYS:
        raise ValueError(f'Invalid config key: {config_key}')
    if not isinstance(config_value, dict):
        raise ValueError('Config value must be a dictionary')

    normalized_value = normalize_config_value(config_key, config_value)
    now = datetime.now().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO app_config (config_key, config_value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET
            config_value = excluded.config_value,
            updated_at = excluded.updated_at
    ''', (
        config_key,
        json.dumps(normalized_value, ensure_ascii=False),
        now
    ))
    conn.commit()
    conn.close()
    return normalized_value


# 合并并保存数据库配置
#
# 功能描述：
#     将局部更新数据和已有数据库配置合并后保存，避免前端只提交部分字段时丢失其他项。
def merge_and_save_db_config(config_key: str, partial_value: Dict[str, Any]) -> Dict[str, Any]:
    current_value = get_single_config(config_key)
    merged_value = {**current_value, **(partial_value or {})}
    return save_db_config(config_key, merged_value)


# 判断数据库中是否已有任意配置
#
# 功能描述：
#     用于诊断和日志输出，判断数据库配置表是否已有数据。
def has_any_db_config() -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(1) AS total FROM app_config')
    row = cursor.fetchone()
    conn.close()
    return bool(row and row['total'] > 0)


# 确保数据库配置就绪
#
# 功能描述：
#     数据库是唯一数据源。此函数已废弃，仅保留空实现以兼容旧调用。
def ensure_config_data_ready() -> None:
    pass


# 获取单个配置模块
#
# 功能描述：
#     对外统一返回带默认值的稳定配置结构。
#     数据库有数据则用数据库的，没有则用默认值填充。
def get_single_config(config_key: str) -> Dict[str, Any]:
    db_config = get_db_config(config_key)
    return normalize_config_value(config_key, db_config)


# 获取全部配置模块
#
# 功能描述：
#     一次性返回设置页所需的全部数据库配置。
def get_all_configs() -> Dict[str, Dict[str, Any]]:
    return {
        'image_api': get_single_config('image_api'),
        'server': get_single_config('server'),
        'prompt_optimize': get_single_config('prompt_optimize'),
        'fal_api': get_single_config('fal_api'),
        'gptsapi_api': get_single_config('gptsapi_api'),
        'file_upload': get_single_config('file_upload'),
        'social_copy_api': get_single_config('social_copy_api'),
        'topaz_gigapixel': get_single_config('topaz_gigapixel')
    }
