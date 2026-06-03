import logging

from flask import Blueprint, request, jsonify, current_app

from models.config_model import (
    get_all_configs as get_all_db_configs,
    get_single_config as get_db_single_config,
    merge_and_save_db_config,
    ensure_config_data_ready,
    has_any_db_config
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
                'version': 4,
                'imageApi': config_payload.get('image_api', {}),
                'server': config_payload.get('server', {}),
                'promptOptimize': config_payload.get('prompt_optimize', {}),
                'falApi': config_payload.get('fal_api', {}),
                'gptsapiApi': config_payload.get('gptsapi_api', {}),
                'fileUpload': config_payload.get('file_upload', {}),
                'socialCopyApi': config_payload.get('social_copy_api', {})
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

        if 'server' in data:
            merge_and_save_db_config('server', data['server'])
            logger.info('[ConfigAPI] server 配置已保存')

        if 'promptOptimize' in data:
            merge_and_save_db_config('prompt_optimize', data['promptOptimize'])
            logger.info('[ConfigAPI] prompt_optimize 配置已保存')

        if 'falApi' in data:
            merge_and_save_db_config('fal_api', data['falApi'])
            logger.info('[ConfigAPI] fal_api 配置已保存')

        if 'gptsapiApi' in data:
            merge_and_save_db_config('gptsapi_api', data['gptsapiApi'])
            logger.info('[ConfigAPI] gptsapi_api 配置已保存')

        if 'fileUpload' in data:
            merge_and_save_db_config('file_upload', data['fileUpload'])
            logger.info('[ConfigAPI] file_upload 配置已保存')

        if 'socialCopyApi' in data:
            merge_and_save_db_config('social_copy_api', data['socialCopyApi'])
            logger.info('[ConfigAPI] social_copy_api 配置已保存')

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
            'file_upload': 'file_upload',
            'social_copy_api': 'social_copy_api'
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
            'file_upload': 'file_upload',
            'social_copy_api': 'social_copy_api'
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

    fal_api_config = get_db_single_config('fal_api')
    current_app.config['FAL_API_KEY'] = fal_api_config.get('apiKey', '')
    current_app.config['FAL_MODELS'] = fal_api_config.get('falModels', [])

    gptsapi_api_config = get_db_single_config('gptsapi_api')
    current_app.config['GPTSAPI_BASE_URL'] = gptsapi_api_config.get('baseUrl', 'https://api.gptsapi.net')
    current_app.config['GPTSAPI_API_KEY'] = gptsapi_api_config.get('apiKey', '')

    file_upload_config = get_db_single_config('file_upload')
    current_app.config['FILE_UPLOAD_BASE_URL'] = file_upload_config.get('baseUrl', '')
    current_app.config['FILE_UPLOAD_API_KEY'] = file_upload_config.get('apiKey', '')

    social_copy_api_config = get_db_single_config('social_copy_api')
    current_app.config['SOCIAL_COPY_BASE_URL'] = social_copy_api_config.get('baseUrl', '')
    current_app.config['SOCIAL_COPY_API_KEY'] = social_copy_api_config.get('apiKey', '')
    current_app.config['SOCIAL_COPY_MODEL'] = social_copy_api_config.get('model', '')
    current_app.config['SOCIAL_COPY_SYSTEM_PROMPT'] = social_copy_api_config.get('systemPrompt', '')
