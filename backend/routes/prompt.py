from flask import Blueprint, request, jsonify, current_app
from services.prompt_service import PromptService
from models.config_model import get_single_config

prompt_bp = Blueprint('prompt', __name__)


def get_prompt_service() -> PromptService:
    """
    获取提示词优化服务实例

    功能描述：
        从数据库配置中读取 prompt_optimize 配置，
        创建并返回 PromptService 实例。
        支持 DeepSeek 提供商的特殊配置（思考模式、思考深度等）。

    返回：
        PromptService 实例
    """
    prompt_config = get_single_config('prompt_optimize')

    provider = prompt_config.get('provider', 'openai')
    thinking_enabled = prompt_config.get('thinkingEnabled', False)
    reasoning_effort = prompt_config.get('reasoningEffort', 'high')
    xiaomi_thinking_enabled = False
    xiaomi_enable_web_search = False

    if provider == 'deepseek':
        base_url = 'https://api.deepseek.com'
        model = prompt_config.get('deepseekModel', 'deepseek-v4-pro')
        api_key = prompt_config.get('deepseekApiKey', current_app.config.get('PROMPT_OPTIMIZE_DEEPSEEK_API_KEY', ''))
    elif provider == 'xiaomi':
        base_url = 'https://api.xiaomimimo.com'
        model = prompt_config.get('xiaomiModel', 'mimo-v2.5-pro')
        api_key = prompt_config.get('xiaomiApiKey', '')
        xiaomi_thinking_enabled = prompt_config.get('xiaomiThinkingEnabled', False)
        xiaomi_enable_web_search = prompt_config.get('xiaomiEnableWebSearch', False)
    else:
        base_url = prompt_config.get('baseUrl', current_app.config.get('PROMPT_OPTIMIZE_BASE_URL', ''))
        model = prompt_config.get('model', current_app.config.get('PROMPT_OPTIMIZE_MODEL', ''))
        api_key = prompt_config.get('apiKey', current_app.config.get('PROMPT_OPTIMIZE_API_KEY', ''))

    # 获取当前选中的系统提示词
    system_prompts = prompt_config.get('systemPrompts', [])
    selected_id = prompt_config.get('selectedSystemPromptId', 'default')
    selected_prompt = next((sp for sp in system_prompts if sp.get('id') == selected_id), None)
    if selected_prompt:
        system_prompt = selected_prompt.get('content', '')
    else:
        system_prompt = prompt_config.get('systemPrompt', current_app.config.get('PROMPT_OPTIMIZE_SYSTEM_PROMPT', ''))

    return PromptService(
        api_base_url=base_url,
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
        provider=provider,
        thinking_enabled=thinking_enabled,
        reasoning_effort=reasoning_effort,
        xiaomi_thinking_enabled=xiaomi_thinking_enabled,
        xiaomi_enable_web_search=xiaomi_enable_web_search
    )


# 优化提示词
# 功能描述：
#     接收用户输入的提示词，调用大语言模型进行优化，
#     返回优化后的提示词。
# 实现逻辑：
#     1. 接收 JSON 请求体中的 prompt 字段
#     2. 校验 prompt 不为空
#     3. 调用 PromptService.optimize_prompt() 进行优化
#     4. 返回优化结果或错误信息
@prompt_bp.route('/api/prompt/optimize', methods=['POST'])
def optimize_prompt():
    data = request.get_json() or {}

    prompt = data.get('prompt', '').strip()

    if not prompt:
        return jsonify({'error': '提示词不能为空'}), 400

    print(
            "\n[Prompt Route] ========== POST /api/prompt/optimize ==========\n"
            f"[Prompt Route] 收到优化请求，prompt 长度: {len(prompt)}\n"
            f"[Prompt Route] 完整 prompt:\n{prompt}\n"
            "[Prompt Route] ==================================================\n"
        )

    prompt_service = get_prompt_service()

    prompt_config = get_single_config('prompt_optimize')
    provider = prompt_config.get('provider', 'openai')
    mode = prompt_config.get('mode', 'chat')
    enable_web_search = prompt_config.get('enableWebSearch', False)

    # DeepSeek 不支持 Responses API，强制使用 chat 模式
    if provider == 'deepseek':
        if mode == 'responses':
            print("[Prompt Route] DeepSeek 提供商不支持 Responses API，自动切换为 chat 模式")
            mode = 'chat'
        if enable_web_search:
            print("[Prompt Route] DeepSeek 提供商不支持联网搜索，已禁用")
            enable_web_search = False
    elif provider == 'xiaomi':
        # XIAOMI 只支持 Chat 模式，但支持联网搜索（通过 tools 参数实现）
        if mode == 'responses':
            print("[Prompt Route] XIAOMI 提供商不支持 Responses API，自动切换为 chat 模式")
            mode = 'chat'

    print(
        f"[Prompt Route] provider: {provider}, mode: {mode}, enable_web_search: {enable_web_search}\n"
    )

    result = prompt_service.optimize_prompt(
        prompt,
        mode=mode,
        enable_web_search=enable_web_search
    )

    if 'error' in result:
        print(
            f"\n[Prompt Route] ========== 优化失败 ==========\n"
            f"[Prompt Route] 错误信息: {result.get('error')}\n"
            f"[Prompt Route] ====================================\n"
        )
        return jsonify(result), 400

    return jsonify({
        'success': True,
        'optimized_prompt': result.get('optimized_prompt', '')
    }), 200
