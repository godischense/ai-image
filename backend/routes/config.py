import logging

from flask import Blueprint, request, jsonify, current_app

from models.config_model import (
    get_all_configs as get_all_db_configs,
    get_single_config as get_db_single_config,
    merge_and_save_db_config,
    ensure_config_data_ready,
    has_any_db_config,
    DEFAULT_CONFIGS
)

logger = logging.getLogger(__name__)
config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config', methods=['GET'])
def get_config():
    try:
        logger.info('[ConfigAPI] GET /api/config - 开始读取配置')

        db_has_config = has_any_db_config()
        logger.info('[ConfigAPI] 数据库中是否存在任何配置: %s', db_has_config)

        ensure_config_data_ready()

        config_payload = get_all_db_configs()

        logger.info('[ConfigAPI] 已读取全部数据库配置，共 %d 个模块', len(config_payload))

        return jsonify({
            'status': 'success',
            'config': {
                'version': 6,
                'imageApi': config_payload.get('image_api', {}),
                'server': config_payload.get('server', {}),
                'promptOptimize': config_payload.get('prompt_optimize', {}),
                'falApi': config_payload.get('fal_api', {}),
                'gptsapiApi': config_payload.get('gptsapi_api', {}),
                'apiyiApi': config_payload.get('apiyi_api', {}),
                'fileUpload': config_payload.get('file_upload', {}),
                'socialCopyApi': config_payload.get('social_copy_api', {}),
                'promptTransform': config_payload.get('prompt_transform', {}),
                'topazGigapixel': config_payload.get('topaz_gigapixel', {}),
                'editPromptSnippets': config_payload.get('edit_prompt_snippets', {}),
                'creatorOptions': config_payload.get('creator_options', {}),
                'imageLibraryCreatorFilter': config_payload.get('image_library_creator_filter', {})
            }
        }), 200
    except Exception as e:
        logger.error('[ConfigAPI] GET /api/config 读取失败: %s', str(e), exc_info=True)
        return jsonify({
            'error': 'Failed to load config',
            'details': str(e)
        }), 500


@config_bp.route('/api/config', methods=['POST'])
def save_config():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        logger.info('[ConfigAPI] POST /api/config - 开始保存配置，包含模块: %s', [k for k in data.keys()])
        if 'imageApi' in data:
            merge_and_save_db_config('image_api', data['imageApi'])
            logger.info('[ConfigAPI] image_api 配置已保存')

        if 'falApi' in data:
            logger.info('[ConfigAPI] 收到 falApi 数据: %s', data['falApi'])
            merge_and_save_db_config('fal_api', data['falApi'])
            # 验证写入是否成功
            saved = get_db_single_config('fal_api')
            logger.info('[ConfigAPI] fal_api 写入后从 DB 读回: %s', saved)
            logger.info('[ConfigAPI] fal_api 配置已保存')

        if 'server' in data:
            merge_and_save_db_config('server', data['server'])
            logger.info('[ConfigAPI] server 配置已保存')

        if 'promptOptimize' in data:
            merge_and_save_db_config('prompt_optimize', data['promptOptimize'])
            logger.info('[ConfigAPI] prompt_optimize 配置已保存')

        if 'gptsapiApi' in data:
            merge_and_save_db_config('gptsapi_api', data['gptsapiApi'])
            logger.info('[ConfigAPI] gptsapi_api 配置已保存')

        if 'apiyiApi' in data:
            merge_and_save_db_config('apiyi_api', data['apiyiApi'])
            logger.info('[ConfigAPI] apiyi_api 配置已保存')

        if 'fileUpload' in data:
            merge_and_save_db_config('file_upload', data['fileUpload'])
            logger.info('[ConfigAPI] file_upload 配置已保存')

        if 'socialCopyApi' in data:
            merge_and_save_db_config('social_copy_api', data['socialCopyApi'])
            logger.info('[ConfigAPI] social_copy_api 配置已保存')

        if 'promptTransform' in data:
            merge_and_save_db_config('prompt_transform', data['promptTransform'])
            logger.info('[ConfigAPI] prompt_transform 配置已保存')

        if 'topazGigapixel' in data:
            merge_and_save_db_config('topaz_gigapixel', data['topazGigapixel'])
            logger.info('[ConfigAPI] topaz_gigapixel 配置已保存')

        if 'editPromptSnippets' in data:
            merge_and_save_db_config('edit_prompt_snippets', data['editPromptSnippets'])
            logger.info('[ConfigAPI] edit_prompt_snippets 配置已保存')

        # 制作人列表：与 editPromptSnippets 写法对称，缺失字段保留旧值
        if 'creatorOptions' in data:
            merge_and_save_db_config('creator_options', data['creatorOptions'])
            logger.info('[ConfigAPI] creator_options 配置已保存')

        if 'imageLibraryCreatorFilter' in data:
            merge_and_save_db_config('image_library_creator_filter', data['imageLibraryCreatorFilter'])
            logger.info('[ConfigAPI] image_library_creator_filter config saved')

        update_app_config()

        return jsonify({
            'status': 'success',
            'message': 'Configuration saved'
        }), 200
    except Exception as e:
        logger.error('[ConfigAPI] POST /api/config 保存失败: %s', str(e), exc_info=True)
        return jsonify({
            'error': 'Failed to save config',
            'details': str(e)
        }), 500


@config_bp.route('/api/config/<config_type>', methods=['GET'])
def get_single_config(config_type):
    try:
        config_type_map = {
            'image_api': 'image_api',
            'server': 'server',
            'fal_api': 'fal_api',
            'gptsapi_api': 'gptsapi_api',
            'apiyi_api': 'apiyi_api',
            'file_upload': 'file_upload',
            'social_copy_api': 'social_copy_api',
            'prompt_transform': 'prompt_transform',
            'topaz_gigapixel': 'topaz_gigapixel',
            'edit_prompt_snippets': 'edit_prompt_snippets',
            'creator_options': 'creator_options',
            'image_library_creator_filter': 'image_library_creator_filter'
        }

        if config_type not in config_type_map:
            return jsonify({'error': 'Invalid config type'}), 400

        config = get_db_single_config(config_type)

        return jsonify({
            'status': 'success',
            'config': config
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Failed to load config',
            'details': str(e)
        }), 500


@config_bp.route('/api/config/<config_type>', methods=['POST'])
def save_single_config_api(config_type):
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        config_type_map = {
            'image_api': 'image_api',
            'server': 'server',
            'fal_api': 'fal_api',
            'gptsapi_api': 'gptsapi_api',
            'apiyi_api': 'apiyi_api',
            'file_upload': 'file_upload',
            'social_copy_api': 'social_copy_api',
            'prompt_transform': 'prompt_transform',
            'topaz_gigapixel': 'topaz_gigapixel',
            'edit_prompt_snippets': 'edit_prompt_snippets',
            'creator_options': 'creator_options',
            'image_library_creator_filter': 'image_library_creator_filter'
        }

        if config_type not in config_type_map:
            return jsonify({'error': 'Invalid config type'}), 400

        merge_and_save_db_config(config_type, data)

        update_app_config()

        return jsonify({
            'status': 'success',
            'message': f'{config_type} configuration saved'
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Failed to save config',
            'details': str(e)
        }), 500


def update_app_config():
    """
    更新应用配置

    功能描述：
        从数据库读取最新配置并同步到 Flask 应用上下文，保证业务路由和设置页使用同一数据源。
    """
    ensure_config_data_ready()
    image_api_config = get_db_single_config('image_api')
    server_config = get_db_single_config('server')
    prompt_optimize_config = get_db_single_config('prompt_optimize')

    # 获取当前选中的系统提示词
    system_prompts = prompt_optimize_config.get('systemPrompts', [])
    selected_id = prompt_optimize_config.get('selectedSystemPromptId', 'default')
    selected_prompt = next((sp for sp in system_prompts if sp.get('id') == selected_id), None)
    if selected_prompt:
        current_system_prompt = selected_prompt.get('content', '')
    else:
        current_system_prompt = prompt_optimize_config.get('systemPrompt', '')

    current_app.config['IMAGE_API_BASE_URL'] = image_api_config.get('baseUrl', '')
    current_app.config['IMAGE_API_KEY'] = image_api_config.get('apiKey', '')
    current_app.config['IMAGE_MODELS'] = image_api_config.get('imageModels', [])
    # 同步 image_api 中的余额查询字段到 Flask 应用上下文，供 user_balance 路由读取
    # Base URL 共用 imageApi.baseUrl；余额专用 token / userId 走独立字段
    # balanceField 与 balanceDivider 不再从配置读取，固定写在 user_balance.py 里
    current_app.config['IMAGE_API_BALANCE_TOKEN'] = image_api_config.get('balanceToken', '')
    current_app.config['IMAGE_API_BALANCE_USER_ID'] = image_api_config.get('balanceUserId', '')
    current_app.config['IMAGE_API_BALANCE_REFRESH_INTERVAL_MINUTES'] = image_api_config.get('balanceRefreshIntervalMinutes', 5)
    current_app.config['SERVER_PORT'] = server_config.get('port', 5678)
    current_app.config['PROMPT_OPTIMIZE_BASE_URL'] = prompt_optimize_config.get('baseUrl', '')
    current_app.config['PROMPT_OPTIMIZE_API_KEY'] = prompt_optimize_config.get('apiKey', '')
    current_app.config['PROMPT_OPTIMIZE_MODEL'] = prompt_optimize_config.get('model', 'gpt-4o')
    current_app.config['PROMPT_OPTIMIZE_SYSTEM_PROMPT'] = current_system_prompt
    current_app.config['PROMPT_OPTIMIZE_PROVIDER'] = prompt_optimize_config.get('provider', 'openai')
    current_app.config['PROMPT_OPTIMIZE_DEEPSEEK_MODEL'] = prompt_optimize_config.get('deepseekModel', 'deepseek-v4-pro')
    current_app.config['PROMPT_OPTIMIZE_THINKING_ENABLED'] = prompt_optimize_config.get('thinkingEnabled', False)
    current_app.config['PROMPT_OPTIMIZE_REASONING_EFFORT'] = prompt_optimize_config.get('reasoningEffort', 'high')
    current_app.config['PROMPT_OPTIMIZE_XIAOMI_MODEL'] = prompt_optimize_config.get('xiaomiModel', 'mimo-v2.5-pro')
    current_app.config['PROMPT_OPTIMIZE_XIAOMI_THINKING_ENABLED'] = prompt_optimize_config.get('xiaomiThinkingEnabled', False)
    current_app.config['PROMPT_OPTIMIZE_XIAOMI_ENABLE_WEB_SEARCH'] = prompt_optimize_config.get('xiaomiEnableWebSearch', False)
    current_app.config['PROMPT_OPTIMIZE_VOLCENGINE_BASE_URL'] = prompt_optimize_config.get('volcengineBaseUrl', 'https://ark.cn-beijing.volces.com/api/v3/responses')
    current_app.config['PROMPT_OPTIMIZE_VOLCENGINE_API_KEY'] = prompt_optimize_config.get('volcengineApiKey', '')
    current_app.config['PROMPT_OPTIMIZE_VOLCENGINE_MODEL'] = prompt_optimize_config.get('volcengineModel', 'doubao-seed-2-1-pro-260628')

    fal_api_config = get_db_single_config('fal_api')
    current_app.config['FAL_BASE_URL'] = fal_api_config.get('baseUrl', '')
    current_app.config['FAL_API_KEY'] = fal_api_config.get('apiKey', '')
    current_app.config['FAL_MODELS'] = fal_api_config.get('falModels', [])

    gptsapi_api_config = get_db_single_config('gptsapi_api')
    current_app.config['GPTSAPI_BASE_URL'] = gptsapi_api_config.get('baseUrl', 'https://api.gptsapi.net')
    current_app.config['GPTSAPI_API_KEY'] = gptsapi_api_config.get('apiKey', '')

    # 同步 APIYI 配置到 Flask 应用上下文，供 routes/images.py 等业务模块直接读取
    # 字段含义：
    #   APIYI_BASE_URL - APIYI 主域名（默认 https://api.apiyi.com），备选 vip.apiyi.com / b.apiyi.com
    #   APIYI_API_KEY  - API易控制台获取的 Bearer Token
    #   APIYI_IMAGE_MODELS - 可用模型列表（默认 ['gpt-image-2-vip']）
    #   APIYI_ACCESS_TOKEN - 余额查询令牌（区别于 apiKey：余额查询 Authorization: <token> 无 Bearer 前缀）
    apiyi_api_config = get_db_single_config('apiyi_api')
    current_app.config['APIYI_BASE_URL'] = apiyi_api_config.get('baseUrl', 'https://api.apiyi.com')
    current_app.config['APIYI_API_KEY'] = apiyi_api_config.get('apiKey', '')
    current_app.config['APIYI_IMAGE_MODELS'] = apiyi_api_config.get('imageModels', ['gpt-image-2-vip', 'gpt-image-2'])
    current_app.config['APIYI_ACCESS_TOKEN'] = apiyi_api_config.get('accessToken', '')

    file_upload_config = get_db_single_config('file_upload')
    current_app.config['FILE_UPLOAD_BASE_URL'] = file_upload_config.get('baseUrl', '')
    current_app.config['FILE_UPLOAD_API_KEY'] = file_upload_config.get('apiKey', '')

    social_copy_api_config = get_db_single_config('social_copy_api')
    current_app.config['SOCIAL_COPY_PROVIDER'] = social_copy_api_config.get('provider', 'openai')
    current_app.config['SOCIAL_COPY_BASE_URL'] = social_copy_api_config.get('baseUrl', '')
    current_app.config['SOCIAL_COPY_API_KEY'] = social_copy_api_config.get('apiKey', '')
    current_app.config['SOCIAL_COPY_MODEL'] = social_copy_api_config.get('model', '')
    current_app.config['SOCIAL_COPY_VOLCENGINE_BASE_URL'] = social_copy_api_config.get('volcengineBaseUrl', 'https://ark.cn-beijing.volces.com/api/v3/responses')
    current_app.config['SOCIAL_COPY_VOLCENGINE_API_KEY'] = social_copy_api_config.get('volcengineApiKey', '')
    current_app.config['SOCIAL_COPY_VOLCENGINE_MODEL'] = social_copy_api_config.get('volcengineModel', 'doubao-seed-2-1-pro-260628')
    current_app.config['SOCIAL_COPY_SYSTEM_PROMPT'] = social_copy_api_config.get('systemPrompt', '')

    prompt_transform_config = get_db_single_config('prompt_transform')
    current_app.config['PROMPT_TRANSFORM'] = prompt_transform_config.get('items', {})

    topaz_gigapixel_config = get_db_single_config('topaz_gigapixel')
    current_app.config['TOPAZ_GIGAPIXEL_EXE_PATH'] = topaz_gigapixel_config.get('exePath', '')
    current_app.config['TOPAZ_GIGAPIXEL_USE_SYSTEM_COMMAND'] = topaz_gigapixel_config.get('useSystemCommand', False)
    current_app.config['TOPAZ_GIGAPIXEL_MAX_PARALLEL'] = topaz_gigapixel_config.get('maxParallel', 1)
    current_app.config['TOPAZ_GIGAPIXEL_TIMEOUT'] = topaz_gigapixel_config.get('timeout', 600)

    # 同步编辑指令预设片段到 Flask 应用上下文，便于业务路由/扩展使用
    edit_prompt_snippets_config = get_db_single_config('edit_prompt_snippets')
    current_app.config['EDIT_PROMPT_SNIPPETS'] = edit_prompt_snippets_config.get('snippets', [])

    # 同步制作人列表到 Flask 应用上下文，供业务路由/扩展使用
    # 默认值取自 DEFAULT_CONFIGS['creator_options']['options']
    creator_options_config = get_db_single_config('creator_options')
    current_app.config['CREATOR_OPTIONS'] = creator_options_config.get(
        'options',
        DEFAULT_CONFIGS['creator_options']['options']
    )

    # 同步图像生成页「制作人」筛选持久化值到 Flask 应用上下文
    # 业务层如需读取用户当前筛选，可通过 current_app.config['IMAGE_LIBRARY_CREATOR_FILTER'] 获取
    creator_filter_config = get_db_single_config('image_library_creator_filter')
    current_app.config['IMAGE_LIBRARY_CREATOR_FILTER'] = creator_filter_config.get('selectedCreator', '')
