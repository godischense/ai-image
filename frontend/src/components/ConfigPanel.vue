<template>
  <div class="config-panel">
    <div class="config-panel__header">
      <h3 class="config-panel__title">配置设置</h3>
      <button class="config-panel__load-btn" @click="loadAllConfigs" title="重新加载所有配置">
        🔄
      </button>
    </div>

    <div class="config-panel__cards">
      <!-- 图像API配置卡片 -->
      <div class="config-card">
        <div class="config-card__header">
          <span class="config-card__icon">🖼️</span>
          <h4 class="config-card__title">图像生成 API</h4>
        </div>
        <form class="config-card__form" @submit.prevent="handleSaveImageApi">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="imageBaseUrl">Base URL</label>
              <input
                id="imageBaseUrl"
                v-model="imageApiForm.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://ai.t8star.cn"
              />
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="imageApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="imageApiKey"
                  v-model="imageApiForm.apiKey"
                  :type="showImageApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showImageApiKey = !showImageApiKey"
                >
                  {{ showImageApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="imageModels">图像模型列表</label>
              <textarea
                id="imageModels"
                v-model="imageApiForm.imageModelsText"
                class="config-card__input config-card__textarea"
                placeholder="每行一个模型名称&#10;例如：&#10;gpt-image-2&#10;dall-e-3"
                rows="3"
              ></textarea>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingImageApi">
              <span v-if="savingImageApi" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingImageApi ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="imageApiMessage" class="config-card__message" :class="[`config-card__message--${imageApiMessageType}`]">
            {{ imageApiMessage }}
          </div>
        </form>
      </div>

      <!-- 服务器设置卡片 -->

      <div class="config-card">
        <div class="config-card__header">
          <span class="config-card__icon">⚙️</span>
          <h4 class="config-card__title">服务器设置</h4>
        </div>
        <form class="config-card__form" @submit.prevent="handleSaveServer">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="serverPort">端口</label>
              <input
                id="serverPort"
                v-model.number="serverForm.port"
                type="number"
                class="config-card__input"
                placeholder="5678"
                min="1"
                max="65535"
              />
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingServer">
              <span v-if="savingServer" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingServer ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="serverMessage" class="config-card__message" :class="[`config-card__message--${serverMessageType}`]">
            {{ serverMessage }}
          </div>
        </form>
      </div>

      <!-- 优化提示词配置卡片 -->
      <div class="config-card">
        <div class="config-card__header">
          <span class="config-card__icon">✨</span>
          <h4 class="config-card__title">优化提示词</h4>
        </div>
        <form class="config-card__form" @submit.prevent="handleSavePromptOptimize">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label">API Provider</label>
              <div class="config-card__tab-group">
                <button
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': promptOptimizeForm.provider === 'openai' }]"
                  @click="promptOptimizeForm.provider = 'openai'"
                >
                  OpenAI 兼容
                </button>
                <button
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': promptOptimizeForm.provider === 'deepseek' }]"
                  @click="promptOptimizeForm.provider = 'deepseek'"
                >
                  DeepSeek
                </button>
                <button
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': promptOptimizeForm.provider === 'xiaomi' }]"
                  @click="promptOptimizeForm.provider = 'xiaomi'"
                >
                  XIAOMI
                </button>
              </div>
            </div>

            <div v-if="promptOptimizeForm.provider === 'openai'" class="config-card__field config-card__field--with-action">
              <label class="config-card__label" for="promptOptimizeBaseUrl">Base URL</label>
              <div class="config-card__input-group">
                <input
                  id="promptOptimizeBaseUrl"
                  v-model="promptOptimizeForm.baseUrl"
                  type="text"
                  class="config-card__input"
                  placeholder="https://ai.t8star.cn"
                />
                <button
                  type="button"
                  class="config-card__action-btn"
                  title="测试连接"
                  @click="testApiConnection('promptOptimize')"
                >
                  <span v-if="testingPromptOptimize" class="config-card__spinner">⟳</span>
                  <span v-else>📡</span>
                </button>
              </div>
            </div>

            <div v-if="promptOptimizeForm.provider === 'deepseek'" class="config-card__field">
              <label class="config-card__label">Base URL</label>
              <div class="config-card__input config-card__input--readonly">
                https://api.deepseek.com
              </div>
            </div>

            <div v-if="promptOptimizeForm.provider === 'xiaomi'" class="config-card__field config-card__field--with-action">
              <label class="config-card__label">Base URL</label>
              <div class="config-card__input-group">
                <div class="config-card__input config-card__input--readonly">
                  https://api.xiaomimimo.com
                </div>
                <button
                  type="button"
                  class="config-card__action-btn"
                  title="测试连接"
                  @click="testApiConnection('promptOptimize')"
                >
                  <span v-if="testingPromptOptimize" class="config-card__spinner">⟳</span>
                  <span v-else>📡</span>
                </button>
              </div>
            </div>

            <div v-if="promptOptimizeForm.provider === 'openai'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="promptOptimizeApiKey"
                  v-model="promptOptimizeForm.apiKey"
                  :type="showPromptOptimizeApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showPromptOptimizeApiKey = !showPromptOptimizeApiKey"
                >
                  {{ showPromptOptimizeApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

            <div v-else-if="promptOptimizeForm.provider === 'deepseek'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeDeepseekApiKey">DeepSeek API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="promptOptimizeDeepseekApiKey"
                  v-model="promptOptimizeForm.deepseekApiKey"
                  :type="showPromptOptimizeApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showPromptOptimizeApiKey = !showPromptOptimizeApiKey"
                >
                  {{ showPromptOptimizeApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

            <div v-else-if="promptOptimizeForm.provider === 'xiaomi'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeXiaomiApiKey">XIAOMI API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="promptOptimizeXiaomiApiKey"
                  v-model="promptOptimizeForm.xiaomiApiKey"
                  :type="showPromptOptimizeApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="输入XIAOMI API Key..."
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showPromptOptimizeApiKey = !showPromptOptimizeApiKey"
                >
                  {{ showPromptOptimizeApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

            <div v-if="promptOptimizeForm.provider === 'openai'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeModel">模型</label>
              <input
                id="promptOptimizeModel"
                v-model="promptOptimizeForm.model"
                type="text"
                class="config-card__input"
                placeholder="gpt-5"
              />
            </div>

            <div v-else-if="promptOptimizeForm.provider === 'deepseek'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeDeepseekModel">模型</label>
              <select
                id="promptOptimizeDeepseekModel"
                v-model="promptOptimizeForm.deepseekModel"
                class="config-card__input config-card__select"
              >
                <option v-for="option in deepseekModelOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div v-else-if="promptOptimizeForm.provider === 'xiaomi'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeXiaomiModel">模型</label>
              <select
                id="promptOptimizeXiaomiModel"
                v-model="promptOptimizeForm.xiaomiModel"
                class="config-card__input config-card__select"
              >
                <option v-for="option in xiaomiModelOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div v-if="promptOptimizeForm.provider === 'deepseek'" class="config-card__field config-card__field--checkbox">
              <label class="config-card__label config-card__label--checkbox">
                <input
                  v-model="promptOptimizeForm.thinkingEnabled"
                  type="checkbox"
                  class="config-card__checkbox"
                />
                <span>启用思考模式</span>
              </label>
            </div>

            <div v-if="promptOptimizeForm.provider === 'deepseek' && promptOptimizeForm.thinkingEnabled" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeReasoningEffort">思考深度</label>
              <select
                id="promptOptimizeReasoningEffort"
                v-model="promptOptimizeForm.reasoningEffort"
                class="config-card__input config-card__select"
              >
                <option v-for="option in reasoningEffortOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div v-if="promptOptimizeForm.provider === 'xiaomi'" class="config-card__field config-card__field--checkbox">
              <label class="config-card__label config-card__label--checkbox">
                <input
                  v-model="promptOptimizeForm.xiaomiThinkingEnabled"
                  type="checkbox"
                  class="config-card__checkbox"
                />
                <span>启用思考模式</span>
              </label>
            </div>

            <div v-if="promptOptimizeForm.provider === 'openai'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeMode">模式</label>
              <div class="config-card__tab-group">
                <button
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': promptOptimizeForm.mode === 'chat' }]"
                  @click="promptOptimizeForm.mode = 'chat'"
                >
                  Chat
                </button>
                <button
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': promptOptimizeForm.mode === 'responses' }]"
                  @click="promptOptimizeForm.mode = 'responses'"
                >
                  Responses
                </button>
              </div>
              <span class="config-card__tab-hint">
                {{ promptOptimizeForm.mode === 'chat' ? 'v1/chat/completions' : 'v1/responses' }}
              </span>
            </div>

            <div v-if="promptOptimizeForm.provider === 'openai' && promptOptimizeForm.mode === 'responses'" class="config-card__field config-card__field--checkbox">
              <label class="config-card__label config-card__label--checkbox">
                <input
                  v-model="promptOptimizeForm.enableWebSearch"
                  type="checkbox"
                  class="config-card__checkbox"
                />
                <span>启用联网搜索</span>
              </label>
            </div>

            <div v-if="promptOptimizeForm.provider === 'xiaomi'" class="config-card__field config-card__field--checkbox">
              <label class="config-card__label config-card__label--checkbox">
                <input
                  v-model="promptOptimizeForm.xiaomiEnableWebSearch"
                  type="checkbox"
                  class="config-card__checkbox"
                />
                <span>启用联网搜索</span>
              </label>
            </div>

            <div class="config-card__field">
              <label class="config-card__label">系统提示词</label>
              
              <!-- 系统提示词选择器 -->
              <div class="system-prompts-container">
                <div class="system-prompts-selector">
                  <div 
                    v-for="(prompt, index) in promptOptimizeForm.systemPrompts" 
                    :key="prompt.id"
                    :class="['system-prompt-item', { active: promptOptimizeForm.selectedSystemPromptId === prompt.id }]"
                    @click="selectSystemPrompt(prompt.id)"
                  >
                    <div class="system-prompt-header">
                      <span class="system-prompt-name">{{ prompt.name }}</span>
                      <div class="system-prompt-actions">
                        <button type="button" class="system-prompt-action-btn" @click.stop="editSystemPrompt(index)" title="编辑">✏️</button>
                        <button v-if="promptOptimizeForm.systemPrompts.length > 1" type="button" class="system-prompt-action-btn" @click.stop="deleteSystemPrompt(index)" title="删除">🗑️</button>
                      </div>
                    </div>
                  </div>
                  <button type="button" class="add-system-prompt-btn" @click="addSystemPrompt">+ 添加新提示词</button>
                </div>

                <!-- 当前选中的系统提示词内容 -->
                <div class="current-system-prompt">
                  <textarea
                    v-model="currentSystemPromptContent"
                    class="config-card__input config-card__textarea"
                    placeholder="定义优化提示词的行为..."
                    rows="4"
                    @input="updateCurrentSystemPromptContent"
                  ></textarea>
                </div>
              </div>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingPromptOptimize">
              <span v-if="savingPromptOptimize" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingPromptOptimize ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="promptOptimizeMessage" class="config-card__message" :class="[`config-card__message--${promptOptimizeMessageType}`]">
            {{ promptOptimizeMessage }}
          </div>
        </form>
      </div>

      <!-- Fal API配置卡片 -->
      <div class="config-card">
        <div class="config-card__header">
          <span class="config-card__icon">🔗</span>
          <h4 class="config-card__title">Fal API 设置</h4>
          <span class="config-card__hint">队列协议（始终异步）</span>
        </div>
        <form class="config-card__form" @submit.prevent="handleSaveFalApi">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="falApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="falApiKey"
                  v-model="falApiForm.apiKey"
                  :type="showFalApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="输入 fal API Key"
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showFalApiKey = !showFalApiKey"
                >
                  {{ showFalApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="falModels">Fal 模型列表</label>
              <textarea
                id="falModels"
                v-model="falApiForm.falModelsText"
                class="config-card__input config-card__textarea"
                placeholder="每行一个模型ID&#10;例如：&#10;openai/gpt-image-2&#10;openai/gpt-image-2/edit"
                rows="3"
              ></textarea>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingFalApi">
              <span v-if="savingFalApi" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingFalApi ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="falApiMessage" class="config-card__message" :class="[`config-card__message--${falApiMessageType}`]">
            {{ falApiMessage }}
          </div>
        </form>
      </div>

      <!-- GPTsAPI配置卡片 -->
      <div class="config-card">
        <div class="config-card__header">
          <span class="config-card__icon">🧩</span>
          <h4 class="config-card__title">GPTsAPI 设置</h4>
          <span class="config-card__hint">gpt-image-2 直连接口</span>
        </div>
        <form class="config-card__form" @submit.prevent="handleSaveGptsapiApi">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="gptsapiBaseUrl">Base URL</label>
              <input
                id="gptsapiBaseUrl"
                v-model="gptsapiApiForm.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://api.gptsapi.net"
              />
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="gptsapiApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="gptsapiApiKey"
                  v-model="gptsapiApiForm.apiKey"
                  :type="showGptsapiApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="输入 GPTsAPI API Key"
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showGptsapiApiKey = !showGptsapiApiKey"
                >
                  {{ showGptsapiApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingGptsapiApi">
              <span v-if="savingGptsapiApi" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingGptsapiApi ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="gptsapiApiMessage" class="config-card__message" :class="[`config-card__message--${gptsapiApiMessageType}`]">
            {{ gptsapiApiMessage }}
          </div>
        </form>
      </div>

      <!-- 文件上传设置卡片 -->
      <div class="config-card">
        <div class="config-card__header">
          <span class="config-card__icon">📁</span>
          <h4 class="config-card__title">文件上传设置</h4>
          <span class="config-card__hint">上传图片获取临时 URL，替代 base64 传参</span>
        </div>
        <form class="config-card__form" @submit.prevent="handleSaveFileUpload">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="fileUploadBaseUrl">上传地址 (Base URL)</label>
              <input
                id="fileUploadBaseUrl"
                v-model="fileUploadForm.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://ai.t8star.cn"
              />
              <span class="config-card__hint">完整的上传 API 地址为：{Base URL}/v1/files</span>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="fileUploadApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="fileUploadApiKey"
                  v-model="fileUploadForm.apiKey"
                  :type="showFileUploadApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="输入文件上传 API Key"
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showFileUploadApiKey = !showFileUploadApiKey"
                >
                  {{ showFileUploadApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingFileUpload">
              <span v-if="savingFileUpload" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingFileUpload ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="fileUploadMessage" class="config-card__message" :class="[`config-card__message--${fileUploadMessageType}`]">
            {{ fileUploadMessage }}
          </div>
        </form>
      </div>

      <!-- 朋友圈文案API配置卡片 -->
      <div class="config-card">
        <div class="config-card__header">
          <span class="config-card__icon">📱</span>
          <h4 class="config-card__title">朋友圈文案生成 API</h4>
          <span class="config-card__hint">OpenAI 兼容聊天接口</span>
        </div>
        <form class="config-card__form" @submit.prevent="handleSaveSocialCopyApi">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="socialCopyBaseUrl">Base URL</label>
              <input
                id="socialCopyBaseUrl"
                v-model="socialCopyApiForm.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://api.example.com"
              />
              <span class="config-card__hint">完整调用地址为：{Base URL}/v1/chat/completions</span>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="socialCopyApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="socialCopyApiKey"
                  v-model="socialCopyApiForm.apiKey"
                  :type="showSocialCopyApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="输入朋友圈文案 API Key"
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showSocialCopyApiKey = !showSocialCopyApiKey"
                >
                  {{ showSocialCopyApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="socialCopyModel">模型</label>
              <input
                id="socialCopyModel"
                v-model="socialCopyApiForm.model"
                type="text"
                class="config-card__input"
                placeholder="输入模型名称"
              />
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="socialCopySystemPrompt">系统提示词</label>
              <textarea
                id="socialCopySystemPrompt"
                v-model="socialCopyApiForm.systemPrompt"
                class="config-card__input config-card__textarea"
                placeholder="可选，为朋友圈文案生成指定语气和要求"
                rows="4"
              ></textarea>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingSocialCopyApi">
              <span v-if="savingSocialCopyApi" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingSocialCopyApi ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="socialCopyApiMessage" class="config-card__message" :class="[`config-card__message--${socialCopyApiMessageType}`]">
            {{ socialCopyApiMessage }}
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue';
import { useConfigStore } from '@/stores/configStore';

const configStore = useConfigStore();

/* eslint-disable */

const imageApiForm = reactive({
  baseUrl: '',
  apiKey: '',
  imageModelsText: ''
});

const serverForm = reactive({
  port: null
});

const promptOptimizeForm = reactive({
  baseUrl: '',
  apiKey: '',
  model: '',
  mode: 'chat',
  enableWebSearch: false,
  systemPrompt: '',
  provider: 'openai',
  deepseekApiKey: '',
  deepseekModel: 'deepseek-v4-pro',
  thinkingEnabled: false,
  reasoningEffort: 'high',
  xiaomiApiKey: '',
  xiaomiModel: 'mimo-v2.5-pro',
  xiaomiThinkingEnabled: false,
  xiaomiEnableWebSearch: false,
  systemPrompts: [
    {
      id: 'default',
      name: '默认优化',
      content: '你是一个专业的图像提示词优化专家。请将用户输入的提示词优化为更详细、更适合图像生成的描述。优化后的提示词应该：1. 更具体清晰 2. 包含更多细节描述 3. 适合作为图像生成的输入。请直接返回JSON格式：{"optimized_prompt": "优化后的提示词内容"}，不要包含任何其他内容或解释。'
    }
  ],
  selectedSystemPromptId: 'default'
});

// 当前选中的系统提示词内容
const currentSystemPromptContent = ref('');

const deepseekModelOptions = [
  { value: 'deepseek-v4-flash', label: 'deepseek-v4-flash' },
  { value: 'deepseek-v4-pro', label: 'deepseek-v4-pro' }
];

const reasoningEffortOptions = [
  { value: 'high', label: 'High' },
  { value: 'max', label: 'Max' }
];

const xiaomiModelOptions = [
  { value: 'mimo-v2.5-pro', label: 'mimo-v2.5-pro' },
  { value: 'mimo-v2.5', label: 'mimo-v2.5' }
];

const falApiForm = reactive({
  apiKey: '',
  falModelsText: ''
});

const gptsapiApiForm = reactive({
  baseUrl: 'https://api.gptsapi.net',
  apiKey: ''
});

const fileUploadForm = reactive({
  baseUrl: '',
  apiKey: ''
});

const socialCopyApiForm = reactive({
  baseUrl: '',
  apiKey: '',
  model: '',
  systemPrompt: ''
});

const showImageApiKey = ref(false);
const showPromptOptimizeApiKey = ref(false);
const savingImageApi = ref(false);
const savingPromptOptimize = ref(false);
const savingServer = ref(false);
const testingPromptOptimize = ref(false);
const showFalApiKey = ref(false);
const savingFalApi = ref(false);
const falApiMessage = ref('');
const falApiMessageType = ref('success');
const showGptsapiApiKey = ref(false);
const savingGptsapiApi = ref(false);
const gptsapiApiMessage = ref('');
const gptsapiApiMessageType = ref('success');
const savingFileUpload = ref(false);
const fileUploadMessage = ref('');
const fileUploadMessageType = ref('success');
const showFileUploadApiKey = ref(false);
const showSocialCopyApiKey = ref(false);
const savingSocialCopyApi = ref(false);
const socialCopyApiMessage = ref('');
const socialCopyApiMessageType = ref('success');
const imageApiMessage = ref('');
const imageApiMessageType = ref('success');
const serverMessage = ref('');
const serverMessageType = ref('success');
const promptOptimizeMessage = ref('');
const promptOptimizeMessageType = ref('success');

const loadAllConfigs = async () => {
  try {
    console.log('[ConfigPanel] loadAllConfigs - 开始加载所有配置');
    await configStore.fetchConfig();
    console.log('[ConfigPanel] loadAllConfigs - fetchConfig成功，store数据:', {
      imageApi: configStore.imageApi,
      server: configStore.server,
      promptOptimize: configStore.promptOptimize
    });
    syncFormsFromStore();
    showMessage('imageApi', '所有配置已加载', 'success');
    showMessage('server', '所有配置已加载', 'success');
    showMessage('promptOptimize', '所有配置已加载', 'success');
    showMessage('falApi', '所有配置已加载', 'success');
    showMessage('gptsapiApi', '所有配置已加载', 'success');
    showMessage('fileUpload', '所有配置已加载', 'success');
    showMessage('socialCopyApi', '所有配置已加载', 'success');
  } catch (error) {
    console.error('[ConfigPanel] loadAllConfigs - 加载配置失败:', error.message);
    syncFormsFromStore();
    showMessage('imageApi', '加载配置失败: ' + error.message, 'error');
  }
};

// 测试API连接的处理函数
// 仅用于优化提示词API的连接测试
const testApiConnection = async () => {
  const isDeepseek = promptOptimizeForm.provider === 'deepseek';
  const isXiaomi = promptOptimizeForm.provider === 'xiaomi';
  
  if (!isDeepseek && !isXiaomi && !promptOptimizeForm.baseUrl) {
    showMessage('promptOptimize', '请先填写Base URL', 'error');
    return;
  }

  const apiKeyToUse = isXiaomi ? promptOptimizeForm.xiaomiApiKey
    : (isDeepseek ? promptOptimizeForm.deepseekApiKey : promptOptimizeForm.apiKey);
  if (!apiKeyToUse) {
    const providerName = isXiaomi ? 'XIAOMI' : (isDeepseek ? 'DeepSeek' : '');
    showMessage('promptOptimize', isDeepseek || isXiaomi ? `请先填写${providerName} API Key` : '请先填写API Key', 'error');
    return;
  }

  const modelToUse = isXiaomi ? promptOptimizeForm.xiaomiModel
    : (isDeepseek ? promptOptimizeForm.deepseekModel : promptOptimizeForm.model);
  if (!modelToUse) {
    showMessage('promptOptimize', '请先填写模型名称', 'error');
    return;
  }

  testingPromptOptimize.value = true;
  showMessage('promptOptimize', '正在测试连接...', 'info');

  try {
    let testUrl = isXiaomi ? 'https://api.xiaomimimo.com'
       : (isDeepseek ? 'https://api.deepseek.com' : promptOptimizeForm.baseUrl.replace(/\/$/, ''));
    let requestBody = {};

    if (!isDeepseek && !isXiaomi && promptOptimizeForm.mode === 'responses') {
      testUrl += '/v1/responses';
      requestBody = {
        model: modelToUse,
        input: 'test'
      };
    } else {
      testUrl += '/v1/chat/completions';
      requestBody = {
        model: modelToUse,
        messages: [{ role: 'user', content: 'test' }],
        max_tokens: 1
      };
    }

    // XIAOMI 使用 api-key 请求头，其他使用 Authorization
    const headers = isXiaomi
      ? { 'api-key': apiKeyToUse, 'Content-Type': 'application/json' }
      : { 'Authorization': `Bearer ${apiKeyToUse}`, 'Content-Type': 'application/json' };

    const response = await fetch(testUrl, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(requestBody)
    });

    if (response.ok) {
      showMessage('promptOptimize', '连接成功！', 'success');
    } else {
      const errorData = await response.json().catch(() => ({}));
      const errorMsg = errorData.error?.message || `HTTP ${response.status}`;
      showMessage('promptOptimize', `连接失败: ${errorMsg}`, 'error');
    }
  } catch (error) {
    console.error('[ConfigPanel] testApiConnection - 测试连接失败:', error);
    showMessage('promptOptimize', `连接失败: ${error.message}`, 'error');
  } finally {
    testingPromptOptimize.value = false;
  }
};

const handleSaveImageApi = async () => {
  if (!validateImageApiForm()) {
    return;
  }

  savingImageApi.value = true;
  imageApiMessage.value = '';

  try {
    const configData = {
      imageApi: {
        baseUrl: imageApiForm.baseUrl,
        apiKey: imageApiForm.apiKey,
        isAsync: configStore.imageApi?.isAsync ?? false,
        imageModels: parseModels(imageApiForm.imageModelsText)
      }
    };

    await configStore.saveConfig(configData);
    showMessage('imageApi', '图像API配置保存成功！', 'success');
  } catch (error) {
    showMessage('imageApi', '保存图像API配置失败: ' + error.message, 'error');
  } finally {
    savingImageApi.value = false;
  }
};

const handleSaveServer = async () => {
  if (!validateServerForm()) {
    return;
  }

  savingServer.value = true;
  serverMessage.value = '';

  try {
    const configData = {
      server: {
        port: serverForm.port
      }
    };

    await configStore.saveConfig(configData);
    showMessage('server', '服务器配置保存成功！', 'success');
  } catch (error) {
    showMessage('server', '保存服务器配置失败: ' + error.message, 'error');
  } finally {
    savingServer.value = false;
  }
};

const handleSavePromptOptimize = async () => {
  if (!validatePromptOptimizeForm()) {
    return;
  }

  savingPromptOptimize.value = true;
  promptOptimizeMessage.value = '';

  try {
    const configData = {
      promptOptimize: {
        baseUrl: (promptOptimizeForm.provider === 'deepseek' || promptOptimizeForm.provider === 'xiaomi')
          ? (configStore.promptOptimize.baseUrl || promptOptimizeForm.baseUrl || '')
          : promptOptimizeForm.baseUrl,
        apiKey: promptOptimizeForm.apiKey,
        model: (promptOptimizeForm.provider === 'deepseek' || promptOptimizeForm.provider === 'xiaomi')
          ? (configStore.promptOptimize.model || promptOptimizeForm.model || '')
          : promptOptimizeForm.model,
        mode: promptOptimizeForm.mode,
        enableWebSearch: promptOptimizeForm.enableWebSearch,
        systemPrompt: promptOptimizeForm.systemPrompt,
        provider: promptOptimizeForm.provider,
        deepseekApiKey: promptOptimizeForm.deepseekApiKey,
        deepseekModel: promptOptimizeForm.deepseekModel,
        thinkingEnabled: promptOptimizeForm.thinkingEnabled,
        reasoningEffort: promptOptimizeForm.reasoningEffort,
        xiaomiApiKey: promptOptimizeForm.xiaomiApiKey,
        xiaomiModel: promptOptimizeForm.xiaomiModel,
        xiaomiThinkingEnabled: promptOptimizeForm.xiaomiThinkingEnabled,
        xiaomiEnableWebSearch: promptOptimizeForm.xiaomiEnableWebSearch,
        systemPrompts: promptOptimizeForm.systemPrompts,
        selectedSystemPromptId: promptOptimizeForm.selectedSystemPromptId
      }
    };

    await configStore.saveConfig(configData);
    showMessage('promptOptimize', '优化提示词配置保存成功！', 'success');
  } catch (error) {
    showMessage('promptOptimize', '保存优化提示词配置失败: ' + error.message, 'error');
  } finally {
    savingPromptOptimize.value = false;
  }
};

const handleSaveFalApi = async () => {
  if (!validateFalApiForm()) {
    return;
  }
  savingFalApi.value = true;
  falApiMessage.value = '';
  try {
    const configData = {
      falApi: {
        apiKey: falApiForm.apiKey,
        falModels: parseModels(falApiForm.falModelsText)
      }
    };
    await configStore.saveConfig(configData);
    showMessage('falApi', 'Fal API配置保存成功！', 'success');
  } catch (error) {
    showMessage('falApi', '保存Fal API配置失败: ' + error.message, 'error');
  } finally {
    savingFalApi.value = false;
  }
};

const handleSaveGptsapiApi = async () => {
  if (!validateGptsapiApiForm()) {
    return;
  }
  savingGptsapiApi.value = true;
  gptsapiApiMessage.value = '';
  try {
    const configData = {
      gptsapiApi: {
        baseUrl: gptsapiApiForm.baseUrl,
        apiKey: gptsapiApiForm.apiKey
      }
    };
    await configStore.saveConfig(configData);
    showMessage('gptsapiApi', 'GPTsAPI配置保存成功！', 'success');
  } catch (error) {
    showMessage('gptsapiApi', '保存GPTsAPI配置失败: ' + error.message, 'error');
  } finally {
    savingGptsapiApi.value = false;
  }
};

const handleSaveFileUpload = async () => {
  if (!validateFileUploadForm()) {
    return;
  }
  savingFileUpload.value = true;
  fileUploadMessage.value = '';
  try {
    const configData = {
      fileUpload: {
        baseUrl: fileUploadForm.baseUrl,
        apiKey: fileUploadForm.apiKey
      }
    };
    await configStore.saveConfig(configData);
    showMessage('fileUpload', '文件上传配置保存成功！', 'success');
  } catch (error) {
    showMessage('fileUpload', '保存文件上传配置失败: ' + error.message, 'error');
  } finally {
    savingFileUpload.value = false;
  }
};

const handleSaveSocialCopyApi = async () => {
  if (!validateSocialCopyApiForm()) {
    return;
  }
  savingSocialCopyApi.value = true;
  socialCopyApiMessage.value = '';
  try {
    const configData = {
      socialCopyApi: {
        baseUrl: socialCopyApiForm.baseUrl.trim(),
        apiKey: socialCopyApiForm.apiKey,
        model: socialCopyApiForm.model.trim(),
        systemPrompt: socialCopyApiForm.systemPrompt
      }
    };
    await configStore.saveConfig(configData);
    showMessage('socialCopyApi', '朋友圈文案 API 配置保存成功！', 'success');
  } catch (error) {
    showMessage('socialCopyApi', '保存朋友圈文案 API 配置失败: ' + error.message, 'error');
  } finally {
    savingSocialCopyApi.value = false;
  }
};

const validateImageApiForm = () => {
  if (!imageApiForm.baseUrl) {
    showMessage('imageApi', '请输入图像API的Base URL', 'error');
    return false;
  }

  if (!imageApiForm.apiKey) {
    showMessage('imageApi', '请输入图像API的API Key', 'error');
    return false;
  }

  if (parseModels(imageApiForm.imageModelsText).length === 0) {
    showMessage('imageApi', '请至少填写一个图像模型', 'error');
    return false;
  }

  return true;
};

const validateServerForm = () => {
  if (!serverForm.port || serverForm.port < 1 || serverForm.port > 65535) {
    showMessage('server', '端口必须在 1-65535 之间', 'error');
    return false;
  }

  return true;
};

const validatePromptOptimizeForm = () => {
  if (promptOptimizeForm.provider === 'openai') {
    if (!promptOptimizeForm.baseUrl) {
      showMessage('promptOptimize', '请输入优化提示词的API Base URL', 'error');
      return false;
    }

    if (!promptOptimizeForm.apiKey) {
      showMessage('promptOptimize', '请输入优化提示词的API Key', 'error');
      return false;
    }

    if (!promptOptimizeForm.model) {
      showMessage('promptOptimize', '请输入优化提示词的模型名称', 'error');
      return false;
    }
  } else if (promptOptimizeForm.provider === 'deepseek') {
    if (!promptOptimizeForm.deepseekApiKey) {
      showMessage('promptOptimize', '请输入DeepSeek API Key', 'error');
      return false;
    }

    if (!promptOptimizeForm.deepseekModel) {
      showMessage('promptOptimize', '请选择DeepSeek模型', 'error');
      return false;
    }
  } else if (promptOptimizeForm.provider === 'xiaomi') {
    if (!promptOptimizeForm.xiaomiApiKey) {
      showMessage('promptOptimize', '请输入XIAOMI API Key', 'error');
      return false;
    }

    if (!promptOptimizeForm.xiaomiModel) {
      showMessage('promptOptimize', '请选择XIAOMI模型', 'error');
      return false;
    }
  }

  return true;
};

const validateFalApiForm = () => {
  if (!falApiForm.apiKey) {
    showMessage('falApi', '请输入Fal API的API Key', 'error');
    return false;
  }
  if (parseModels(falApiForm.falModelsText).length === 0) {
    showMessage('falApi', '请至少填写一个Fal模型', 'error');
    return false;
  }
  return true;
};

const validateGptsapiApiForm = () => {
  if (!gptsapiApiForm.baseUrl) {
    showMessage('gptsapiApi', '请输入GPTsAPI的Base URL', 'error');
    return false;
  }
  if (!gptsapiApiForm.apiKey) {
    showMessage('gptsapiApi', '请输入GPTsAPI的API Key', 'error');
    return false;
  }
  return true;
};

const validateFileUploadForm = () => {
  if (!fileUploadForm.baseUrl) {
    showMessage('fileUpload', '请输入文件上传地址', 'error');
    return false;
  }
  if (!fileUploadForm.apiKey) {
    showMessage('fileUpload', '请输入文件上传 API Key', 'error');
    return false;
  }
  return true;
};

const validateSocialCopyApiForm = () => {
  if (!socialCopyApiForm.baseUrl.trim()) {
    showMessage('socialCopyApi', '请输入朋友圈文案 API 的 Base URL', 'error');
    return false;
  }
  if (!socialCopyApiForm.apiKey) {
    showMessage('socialCopyApi', '请输入朋友圈文案 API Key', 'error');
    return false;
  }
  if (!socialCopyApiForm.model.trim()) {
    showMessage('socialCopyApi', '请输入朋友圈文案模型', 'error');
    return false;
  }
  return true;
};

// 系统提示词管理函数
const selectSystemPrompt = (id) => {
  promptOptimizeForm.selectedSystemPromptId = id;
  updateCurrentSystemPromptDisplay();
};

const updateCurrentSystemPromptDisplay = () => {
  const selectedPrompt = promptOptimizeForm.systemPrompts.find(p => p.id === promptOptimizeForm.selectedSystemPromptId);
  if (selectedPrompt) {
    currentSystemPromptContent.value = selectedPrompt.content;
  }
};

const updateCurrentSystemPromptContent = () => {
  const selectedPrompt = promptOptimizeForm.systemPrompts.find(p => p.id === promptOptimizeForm.selectedSystemPromptId);
  if (selectedPrompt) {
    selectedPrompt.content = currentSystemPromptContent.value;
    // 同时更新旧的 systemPrompt 字段以保持兼容性
    promptOptimizeForm.systemPrompt = currentSystemPromptContent.value;
  }
};

const addSystemPrompt = () => {
  const newId = 'prompt_' + Date.now();
  const newPrompt = {
    id: newId,
    name: '新提示词 ' + (promptOptimizeForm.systemPrompts.length + 1),
    content: ''
  };
  promptOptimizeForm.systemPrompts.push(newPrompt);
  selectSystemPrompt(newId);
};

const editSystemPrompt = (index) => {
  const newName = prompt('请输入新的提示词名称：', promptOptimizeForm.systemPrompts[index].name);
  if (newName && newName.trim()) {
    promptOptimizeForm.systemPrompts[index].name = newName.trim();
  }
};

const deleteSystemPrompt = (index) => {
  if (confirm('确定要删除这个系统提示词吗？')) {
    const deletedId = promptOptimizeForm.systemPrompts[index].id;
    promptOptimizeForm.systemPrompts.splice(index, 1);
    // 如果删除的是当前选中的，则选中第一个
    if (deletedId === promptOptimizeForm.selectedSystemPromptId && promptOptimizeForm.systemPrompts.length > 0) {
      selectSystemPrompt(promptOptimizeForm.systemPrompts[0].id);
    }
  }
};

const parseModels = (value) => {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
};

const syncFormsFromStore = () => {
  console.log('[ConfigPanel] syncFormsFromStore - 同步store数据到表单');

  imageApiForm.baseUrl = configStore.imageApi?.baseUrl || '';
  imageApiForm.apiKey = configStore.imageApi?.apiKey || '';
  imageApiForm.imageModelsText = Array.isArray(configStore.imageApi?.imageModels)
    ? configStore.imageApi.imageModels.join('\n')
    : '';

  serverForm.port = configStore.server?.port ?? null;

  promptOptimizeForm.baseUrl = configStore.promptOptimize?.baseUrl || '';
  promptOptimizeForm.apiKey = configStore.promptOptimize?.apiKey || '';
  promptOptimizeForm.model = configStore.promptOptimize?.model || '';
  promptOptimizeForm.mode = configStore.promptOptimize?.mode || 'chat';
  promptOptimizeForm.enableWebSearch = configStore.promptOptimize?.enableWebSearch || false;
  promptOptimizeForm.systemPrompt = configStore.promptOptimize?.systemPrompt || '';
  promptOptimizeForm.provider = configStore.promptOptimize?.provider || 'openai';
  promptOptimizeForm.deepseekApiKey = configStore.promptOptimize?.deepseekApiKey || '';
  promptOptimizeForm.deepseekModel = configStore.promptOptimize?.deepseekModel || 'deepseek-v4-pro';
  promptOptimizeForm.thinkingEnabled = configStore.promptOptimize?.thinkingEnabled || false;
  promptOptimizeForm.reasoningEffort = configStore.promptOptimize?.reasoningEffort || 'high';
  promptOptimizeForm.xiaomiApiKey = configStore.promptOptimize?.xiaomiApiKey || '';
  promptOptimizeForm.xiaomiModel = configStore.promptOptimize?.xiaomiModel || 'mimo-v2.5-pro';
  promptOptimizeForm.xiaomiThinkingEnabled = configStore.promptOptimize?.xiaomiThinkingEnabled || false;
  promptOptimizeForm.xiaomiEnableWebSearch = configStore.promptOptimize?.xiaomiEnableWebSearch || false;
  
  // 同步系统提示词列表
  if (configStore.promptOptimize?.systemPrompts && configStore.promptOptimize.systemPrompts.length > 0) {
    promptOptimizeForm.systemPrompts = configStore.promptOptimize.systemPrompts;
  }
  if (configStore.promptOptimize?.selectedSystemPromptId) {
    promptOptimizeForm.selectedSystemPromptId = configStore.promptOptimize.selectedSystemPromptId;
  } else if (promptOptimizeForm.systemPrompts.length > 0) {
    promptOptimizeForm.selectedSystemPromptId = promptOptimizeForm.systemPrompts[0].id;
  }
  
  // 更新当前显示的系统提示词内容
  updateCurrentSystemPromptDisplay();

  falApiForm.apiKey = configStore.falApi?.apiKey || '';
  falApiForm.falModelsText = Array.isArray(configStore.falApi?.falModels)
    ? configStore.falApi.falModels.join('\n')
    : '';

  gptsapiApiForm.baseUrl = configStore.gptsapiApi?.baseUrl || 'https://api.gptsapi.net';
  gptsapiApiForm.apiKey = configStore.gptsapiApi?.apiKey || '';

  fileUploadForm.baseUrl = configStore.fileUpload?.baseUrl || '';
  fileUploadForm.apiKey = configStore.fileUpload?.apiKey || '';

  socialCopyApiForm.baseUrl = configStore.socialCopyApi?.baseUrl || '';
  socialCopyApiForm.apiKey = configStore.socialCopyApi?.apiKey || '';
  socialCopyApiForm.model = configStore.socialCopyApi?.model || '';
  socialCopyApiForm.systemPrompt = configStore.socialCopyApi?.systemPrompt || '';

  console.log('[ConfigPanel] syncFormsFromStore - 表单同步完成:', {
    imageApi: { ...imageApiForm },
    server: { ...serverForm },
    promptOptimize: { ...promptOptimizeForm }
  });
};

const isValidUrl = (url) => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

const showMessage = (type, text, messageType) => {
  if (type === 'imageApi') {
    imageApiMessage.value = text;
    imageApiMessageType.value = messageType;
    setTimeout(() => { imageApiMessage.value = ''; }, 3000);
  } else if (type === 'server') {
    serverMessage.value = text;
    serverMessageType.value = messageType;
    setTimeout(() => { serverMessage.value = ''; }, 3000);
  } else if (type === 'promptOptimize') {
    promptOptimizeMessage.value = text;
    promptOptimizeMessageType.value = messageType;
    setTimeout(() => { promptOptimizeMessage.value = ''; }, 3000);
  } else if (type === 'falApi') {
    falApiMessage.value = text;
    falApiMessageType.value = messageType;
    setTimeout(() => { falApiMessage.value = ''; }, 3000);
  } else if (type === 'gptsapiApi') {
    gptsapiApiMessage.value = text;
    gptsapiApiMessageType.value = messageType;
    setTimeout(() => { gptsapiApiMessage.value = ''; }, 3000);
  } else if (type === 'fileUpload') {
    fileUploadMessage.value = text;
    fileUploadMessageType.value = messageType;
    setTimeout(() => { fileUploadMessage.value = ''; }, 3000);
  } else if (type === 'socialCopyApi') {
    socialCopyApiMessage.value = text;
    socialCopyApiMessageType.value = messageType;
    setTimeout(() => { socialCopyApiMessage.value = ''; }, 3000);
  }
};

onMounted(() => {
  loadAllConfigs();
});

// 自动保存 promptOptimize 表单数据到 localStorage
// 用户输入时实时持久化，刷新页面后自动恢复
watch(promptOptimizeForm, () => {
  configStore.promptOptimize.baseUrl = promptOptimizeForm.baseUrl;
  configStore.promptOptimize.apiKey = promptOptimizeForm.apiKey;
  configStore.promptOptimize.model = promptOptimizeForm.model;
  configStore.promptOptimize.mode = promptOptimizeForm.mode;
  configStore.promptOptimize.enableWebSearch = promptOptimizeForm.enableWebSearch;
  configStore.promptOptimize.systemPrompt = promptOptimizeForm.systemPrompt;
  configStore.promptOptimize.provider = promptOptimizeForm.provider;
  configStore.promptOptimize.deepseekApiKey = promptOptimizeForm.deepseekApiKey;
  configStore.promptOptimize.deepseekModel = promptOptimizeForm.deepseekModel;
  configStore.promptOptimize.thinkingEnabled = promptOptimizeForm.thinkingEnabled;
  configStore.promptOptimize.reasoningEffort = promptOptimizeForm.reasoningEffort;
  configStore.promptOptimize.systemPrompts = promptOptimizeForm.systemPrompts;
  configStore.promptOptimize.selectedSystemPromptId = promptOptimizeForm.selectedSystemPromptId;
  configStore.saveToStorage();
}, { deep: true });


</script>

<style lang="scss" scoped>
@import './ConfigPanel.scss';
</style>
