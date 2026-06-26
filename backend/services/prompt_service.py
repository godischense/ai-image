import requests
import json
import re
import time
from typing import Optional, Dict, Any


class PromptService:
    """
    提示词优化服务

    功能描述：
        调用大语言模型API对用户输入的提示词进行优化，
        使其更适合图像生成任务。
        支持 Chat (v1/chat/completions) 和 Responses (v1/responses) 两种模式。
        支持 DeepSeek 思考模式。

    实现逻辑：
        1. 根据 mode 参数选择对应 API 端点
        2. Chat 模式：构建 messages 数组发送到 /v1/chat/completions
        3. Responses 模式：构建 input 数组发送到 /v1/responses（可附加联网工具）
        4. DeepSeek 模式：支持思考模式
        5. 解析响应中的优化结果
        6. 返回优化后的提示词或错误信息
    """

    # 类级别的最大重试次数和重试延迟配置
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 2

    def __init__(self, api_base_url: str, api_key: str, model: str, system_prompt: str, 
                 provider: str = 'openai', thinking_enabled: bool = False, reasoning_effort: str = 'high',
                 xiaomi_thinking_enabled: bool = False, xiaomi_enable_web_search: bool = False):
        self.api_base_url = api_base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.provider = provider
        self.thinking_enabled = thinking_enabled
        self.reasoning_effort = reasoning_effort
        self.xiaomi_thinking_enabled = xiaomi_thinking_enabled
        self.xiaomi_enable_web_search = xiaomi_enable_web_search

    # 判断是否为连接中断类的网络错误（如 "Response ended prematurely"）
    # 这类错误通常是临时性的，可以通过重试来解决
    @staticmethod
    def _is_connection_broken_error(exception: Exception) -> bool:
        error_msg = str(exception).lower()
        broken_keywords = [
            'response ended prematurely',
            'connection broken',
            'connection reset',
            'connection aborted',
            'remote disconnected',
            'connection closed',
        ]
        return any(keyword in error_msg for keyword in broken_keywords)

    def optimize_prompt(
        self,
        prompt: str,
        mode: str = 'chat',
        enable_web_search: bool = False
    ) -> Dict[str, Any]:
        """
        优化提示词

        功能描述：
            将用户输入的提示词发送给大语言模型进行优化，
            返回优化后的提示词。

        参数：
            prompt: 用户输入的原始提示词
            mode: API 模式，'chat' 或 'responses'
            enable_web_search: Responses 模式下是否启用联网搜索

        返回：
            成功时返回 {'success': True, 'optimized_prompt': '优化后的提示词'}
            失败时返回 {'error': '错误信息'}
        """
        if not prompt or not prompt.strip():
            return {'error': '提示词不能为空'}

        if not self.api_key:
            return {'error': '请先配置 API Key'}

        if not self.api_base_url:
            return {'error': '请先配置 API 地址'}

        if mode == 'responses':
            return self._optimize_via_responses(prompt, enable_web_search)
        else:
            return self._optimize_via_chat(prompt)

    def _optimize_via_chat(self, prompt: str, retry_count: int = 0) -> Dict[str, Any]:
        """使用 Chat (v1/chat/completions) 模式优化提示词"""
        url = f"{self.api_base_url}/v1/chat/completions"

        headers = {
            'Content-Type': 'application/json',
            'api-key': self.api_key
        } if self.provider == 'xiaomi' else {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        system_prompt = self.system_prompt
        if self.provider in ('deepseek', 'xiaomi'):
            system_prompt = re.sub(r'请直接返回JSON格式[^。]*。', '', system_prompt)
            system_prompt = re.sub(r'[，,]\s*JSON\s*格式', '', system_prompt)
            system_prompt = re.sub(r'不要包含任何其他内容或解释[。.]', '', system_prompt)

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt.strip()}
        ]

        payload = {
            'model': self.model,
            'messages': messages,
            'max_tokens': 18400
        }

        if self.provider == 'deepseek':
            if self.thinking_enabled:
                payload['reasoning_effort'] = self.reasoning_effort
                payload['extra_body'] = {"thinking": {"type": "enabled"}}
            else:
                payload['temperature'] = 0.7
        elif self.provider == 'xiaomi':
            # XIAOMI thinking 模式：通过 extra_body.thinking.type 控制
            if self.xiaomi_thinking_enabled:
                payload['extra_body'] = {"thinking": {"type": "enabled"}}
            else:
                payload['extra_body'] = {"thinking": {"type": "disabled"}}
                payload['temperature'] = 0.7

            # XIAOMI 联网搜索：通过 tools 参数实现
            if self.xiaomi_enable_web_search:
                payload['tools'] = [{
                    "type": "web_search",
                    "max_keyword": 3,
                    "force_search": True,
                    "limit": 1,
                    "user_location": {
                        "type": "approximate",
                        "country": "China",
                        "region": "Hubei",
                        "city": "Wuhan"
                    }
                }]
                payload['tool_choice'] = "auto"
        else:
            payload['temperature'] = 0.7

        print(
            "\n[PromptService] ========== optimize_prompt (Chat Mode) 上游请求 ==========\n"
            f"[PromptService] POST {url}\n"
            f"[PromptService] Provider: {self.provider}\n"
            f"[PromptService] Model: {self.model}\n"
            f"[PromptService] Thinking Enabled: {self.thinking_enabled}\n"
            f"[PromptService] Reasoning Effort: {self.reasoning_effort}\n"
            f"[PromptService] Original prompt length: {len(prompt)}\n"
            f"[PromptService] Retry count: {retry_count}\n"
            f"[PromptService] 请求体 payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            "[PromptService] =========================================================\n"
        )

        try:
            # timeout=(连接超时, 读取超时) — 连接30秒内连不上则报错，读取不设超时避免LLM响应慢时被截断
            response = requests.post(url, headers=headers, json=payload, timeout=(30, None), proxies={'http': None, 'https': None})
            response.raise_for_status()
            result = response.json()

            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return self._parse_llm_response(content, prompt)

        except requests.exceptions.Timeout:
            return {'error': '优化请求连接超时，请检查网络或API地址配置'}
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 'N/A'
            response_body = e.response.text if e.response is not None else ''
            # 如果响应体为空，尝试获取状态码的描述
            if not response_body:
                if status_code == 400:
                    response_body = '请求参数错误，请检查 API 配置和模型选择'
                elif status_code == 401:
                    response_body = 'API Key 无效或已过期'
                elif status_code == 403:
                    response_body = 'API Key 权限不足'
                elif status_code == 404:
                    response_body = 'API 地址或模型不存在'
                elif status_code == 429:
                    response_body = '请求频率超限，请稍后重试'
                elif status_code == 500:
                    response_body = '服务器内部错误'
                elif status_code == 502:
                    response_body = '网关错误'
                elif status_code == 503:
                    response_body = '服务暂不可用'
                elif status_code == 504:
                    response_body = '网关超时'
                else:
                    response_body = f'HTTP {status_code} 错误'
            print(
                f"\n[PromptService] ========== Chat API 返回错误 ==========\n"
                f"[PromptService] 状态码: {status_code}\n"
                f"[PromptService] 响应体:\n{response_body}\n"
                f"[PromptService] ==========================================\n"
            )
            if self.thinking_enabled and 'thinking' in response_body.lower():
                return {'error': f'思考模式请求失败: {response_body}。请尝试关闭思考模式重试。'}
            return {'error': f'优化失败: {response_body}'}
        except requests.exceptions.ConnectionError as e:
            # 专门处理连接中断类错误（如 "Response ended prematurely"）
            error_msg = str(e)
            print(
                f"\n[PromptService] ========== Chat 网络连接错误 ==========\n"
                f"[PromptService] 错误类型: ConnectionError\n"
                f"[PromptService] 错误详情: {error_msg}\n"
                f"[PromptService] 当前重试次数: {retry_count}\n"
                f"[PromptService] ===========================================\n"
            )
            if self._is_connection_broken_error(e) and retry_count < self.MAX_RETRIES:
                print(f"[PromptService] 检测到连接中断错误，{self.RETRY_DELAY_SECONDS}秒后进行第{retry_count + 1}次重试...\n")
                time.sleep(self.RETRY_DELAY_SECONDS)
                return self._optimize_via_chat(prompt, retry_count + 1)
            if self._is_connection_broken_error(e):
                return {'error': '与AI服务的网络连接不稳定，请求被中断。请检查您的网络环境（如VPN、代理）后重试。'}
            return {'error': f'网络连接失败: {error_msg}'}
        except requests.exceptions.RequestException as e:
            return {'error': f'优化失败: {str(e)}'}
        except Exception as e:
            return {'error': f'优化失败: {str(e)}'}

    def _optimize_via_responses(self, prompt: str, enable_web_search: bool, retry_count: int = 0) -> Dict[str, Any]:
        """使用 Responses (v1/responses) 模式优化提示词"""
        if self.provider == 'volcengine':
            url = self.api_base_url
        else:
            url = f"{self.api_base_url}/v1/responses"

        headers = {
            'Content-Type': 'application/json',
            'api-key': self.api_key
        } if self.provider == 'xiaomi' else {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        input_messages = prompt.strip() if self.provider == 'volcengine' else [
            {'role': 'user', 'content': prompt.strip()}
        ]

        payload = {
            'model': self.model,
            'input': input_messages,
            'max_output_tokens': 18400
        }

        if self.system_prompt:
            instructions = self.system_prompt
            if self.provider in ('deepseek', 'xiaomi'):
                instructions = re.sub(r'请直接返回JSON格式[^。]*。', '', instructions)
                instructions = re.sub(r'[，,]\s*JSON\s*格式', '', instructions)
                instructions = re.sub(r'不要包含任何其他内容或解释[。.]', '', instructions)
            payload['instructions'] = instructions

        if enable_web_search:
            payload['tools'] = [{'type': 'web_search'}]

        print(
            "\n[PromptService] ========== optimize_prompt (Responses Mode) 上游请求 ==========\n"
            f"[PromptService] POST {url}\n"
            f"[PromptService] Model: {self.model}\n"
            f"[PromptService] enable_web_search: {enable_web_search}\n"
            f"[PromptService] Original prompt length: {len(prompt)}\n"
            f"[PromptService] Retry count: {retry_count}\n"
            f"[PromptService] 请求体 payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            "[PromptService] ==============================================================\n"
        )

        try:
            # timeout=(连接超时, 读取超时) — 连接30秒内连不上则报错，读取不设超时避免LLM响应慢时被截断
            response = requests.post(url, headers=headers, json=payload, timeout=(30, None), proxies={'http': None, 'https': None})
            response.raise_for_status()
            result = response.json()

            print(f"[PromptService] Responses 原始响应:\n{json.dumps(result, ensure_ascii=False, indent=2)}\n")

            content = ''
            output = result.get('output', [])
            for item in output:
                if item.get('type') == 'message' and item.get('role') == 'assistant':
                    content_parts = item.get('content', [])
                    for part in content_parts:
                        if part.get('type') == 'output_text':
                            content = part.get('text', '')
                            break
                    if content:
                        break

            return self._parse_llm_response(content, prompt)

        except requests.exceptions.Timeout:
            return {'error': '优化请求连接超时，请检查网络或API地址配置'}
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 'N/A'
            response_body = e.response.text if e.response is not None else ''
            # 如果响应体为空，尝试获取状态码的描述
            if not response_body:
                if status_code == 400:
                    response_body = '请求参数错误，请检查 API 配置和模型选择'
                elif status_code == 401:
                    response_body = 'API Key 无效或已过期'
                elif status_code == 403:
                    response_body = 'API Key 权限不足'
                elif status_code == 404:
                    response_body = 'API 地址或模型不存在'
                elif status_code == 429:
                    response_body = '请求频率超限，请稍后重试'
                elif status_code == 500:
                    response_body = '服务器内部错误'
                elif status_code == 502:
                    response_body = '网关错误'
                elif status_code == 503:
                    response_body = '服务暂不可用'
                elif status_code == 504:
                    response_body = '网关超时'
                else:
                    response_body = f'HTTP {status_code} 错误'
            print(
                f"\n[PromptService] ========== Responses API 返回错误 ==========\n"
                f"[PromptService] 状态码: {status_code}\n"
                f"[PromptService] 响应体:\n{response_body}\n"
                f"[PromptService] ================================================\n"
            )
            # 如果启用了联网搜索但 API 不支持该工具，回退到不联网重试
            if enable_web_search and 'Unsupported tool type' in response_body:
                print("[PromptService] 模型不支持联网搜索工具，回退到不联网重试...\n")
                return self._optimize_via_responses(prompt, enable_web_search=False)
            return {'error': f'优化失败: {response_body}'}
        except requests.exceptions.ConnectionError as e:
            # 专门处理连接中断类错误（如 "Response ended prematurely"）
            error_msg = str(e)
            print(
                f"\n[PromptService] ========== Responses 网络连接错误 ==========\n"
                f"[PromptService] 错误类型: ConnectionError\n"
                f"[PromptService] 错误详情: {error_msg}\n"
                f"[PromptService] 当前重试次数: {retry_count}\n"
                f"[PromptService] =================================================\n"
            )
            if self._is_connection_broken_error(e) and retry_count < self.MAX_RETRIES:
                print(f"[PromptService] 检测到连接中断错误，{self.RETRY_DELAY_SECONDS}秒后进行第{retry_count + 1}次重试...\n")
                time.sleep(self.RETRY_DELAY_SECONDS)
                return self._optimize_via_responses(prompt, enable_web_search, retry_count + 1)
            if self._is_connection_broken_error(e):
                return {'error': '与AI服务的网络连接不稳定，请求被中断。请检查您的网络环境（如VPN、代理）后重试。'}
            return {'error': f'网络连接失败: {error_msg}'}
        except requests.exceptions.RequestException as e:
            return {'error': f'优化失败: {str(e)}'}
        except Exception as e:
            return {'error': f'优化失败: {str(e)}'}

    def _parse_llm_response(self, content: str, original_prompt: str) -> Dict[str, Any]:
        """解析 LLM 返回的文本内容，提取优化后的提示词"""
        print(f"[PromptService] 提取到的完整 content:\n{content}")
        print(f"[PromptService] content 长度: {len(content)}")

        if not content:
            return {'error': '模型返回内容为空'}

        optimized_prompt = content.strip()

        print(f"[PromptService] 去除首尾空白后长度: {len(optimized_prompt)}")

        if optimized_prompt.startswith('```json'):
            print("[PromptService] 检测到代码块格式，开始清理...")
            optimized_prompt = optimized_prompt.replace('```json', '').strip()
            optimized_prompt = optimized_prompt.replace('```', '').strip()
            print(f"[PromptService] 清理后长度: {len(optimized_prompt)}")
        elif optimized_prompt.startswith('```'):
            print("[PromptService] 检测到普通代码块格式，开始清理...")
            optimized_prompt = optimized_prompt.replace('```', '').strip()
            print(f"[PromptService] 清理后长度: {len(optimized_prompt)}")

        if not optimized_prompt:
            print("[PromptService] 清理后内容为空")
            return {'error': '清理后内容为空'}

        # 非 DeepSeek、非 XIAOMI 模型才尝试 JSON 解析（DeepSeek/XIAOMI 已配置为纯文本输出）
        if self.provider not in ('deepseek', 'xiaomi'):
            print(f"[PromptService] 准备解析的内容前500字符: '{optimized_prompt[:500]}...'")
            try:
                parsed_json = json.loads(optimized_prompt)
                print(f"[PromptService] JSON 解析成功，包含字段: {list(parsed_json.keys())}")

                if 'optimized_prompt' in parsed_json:
                    extracted = parsed_json.get('optimized_prompt', '').strip()
                    print(f"[PromptService] 从 optimized_prompt 字段提取: 长度={len(extracted)}")
                    optimized_prompt = extracted
                elif 'prompt' in parsed_json:
                    extracted = parsed_json.get('prompt', '').strip()
                    print(f"[PromptService] 从 prompt 字段提取: 长度={len(extracted)}")
                    optimized_prompt = extracted
                elif 'final_assembled_prompt' in parsed_json:
                    extracted = parsed_json.get('final_assembled_prompt', '').strip()
                    print(f"[PromptService] 从 final_assembled_prompt 字段提取: 长度={len(extracted)}")
                    optimized_prompt = extracted
                elif 'content' in parsed_json:
                    extracted = parsed_json.get('content', '').strip()
                    print(f"[PromptService] 从 content 字段提取: 长度={len(extracted)}")
                    optimized_prompt = extracted
                else:
                    print(f"[PromptService] JSON 中没有找到期望的字段，使用原始内容")

            except json.JSONDecodeError:
                pass

        print(
            f"[PromptService] 优化完成，原始长度: {len(original_prompt)}, 优化后长度: {len(optimized_prompt)}\n"
            f"[PromptService] 完整的优化后提示词:\n{optimized_prompt}\n"
        )

        if not optimized_prompt:
            return {'error': '模型返回的优化提示词为空'}

        return {
            'success': True,
            'optimized_prompt': optimized_prompt
        }
