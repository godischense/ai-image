<template>
  <div class="config-panel">
    <div class="config-panel__header">
      <h3 class="config-panel__title">配置设置</h3>
      <button class="config-panel__load-btn" @click="loadAllConfigs" title="重新加载所有配置">
        🔄
      </button>
    </div>

    <div class="config-panel__cards">
      <!-- T8 平台图像生成 API 配置卡片（按用户要求重命名） -->
      <div class="config-card">
        <div class="config-card__header" @click="toggleCard('imageApi')">
          <span class="config-card__icon">🖼️</span>
          <h4 class="config-card__title">T8 平台图像生成 API</h4>
          <!-- 余额预览 chip：折叠态也能看到当前余额；点击触发刷新
               Base URL 与生图共用，平台名通过 t8BalancePlatformName 计算属性展示 -->
          <span
            class="config-card__balance-chip"
            :class="{
              'config-card__balance-chip--loading': t8BalanceStatus === 'loading',
              'config-card__balance-chip--error': t8BalanceStatus === 'error',
              'config-card__balance-chip--success': t8BalanceStatus === 'success'
            }"
            :title="t8BalanceTooltip"
            @click.stop="refreshT8BalancePreview"
          >
            <span v-if="t8BalanceStatus === 'loading'" class="config-card__balance-spinner">⟳</span>
            <span v-else-if="t8BalanceStatus === 'error'" class="config-card__balance-icon">⚠</span>
            <span v-else-if="t8BalanceStatus === 'success'" class="config-card__balance-icon">●</span>
            <span class="config-card__balance-label">余额</span>
            <strong class="config-card__balance-value">{{ t8BalanceDisplay }}</strong>
          </span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.imageApi }"
            :title="cardCollapsed.imageApi ? '展开' : '收起'"
            :aria-label="cardCollapsed.imageApi ? '展开' : '收起'"
            @click.stop="toggleCard('imageApi')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.imageApi" class="config-card__form" @submit.prevent="handleSaveImageApi">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="imageBaseUrl">Base URL</label>
              <input
                id="imageBaseUrl"
                v-model="imageApiForm.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://ai.t8star.org"
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

            <!-- T8 余额查询字段组：Base URL 与生图共用，已在卡片顶部"Base URL"统一维护
                 字段名（quota）和换算除数（500000）已硬编码在后端，不再让用户配置 -->
            <div class="config-card__field config-card__field--divider">
              <span class="config-card__hint config-card__hint--section">T8 平台余额查询（共用上方 Base URL）</span>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="imageApiBalanceToken">API Token（余额查询）</label>
              <div class="config-card__input-wrapper">
                <input
                  id="imageApiBalanceToken"
                  v-model="imageApiForm.balanceToken"
                  :type="showImageApiBalanceToken ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="在个人中心生成系统令牌"
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showImageApiBalanceToken = !showImageApiBalanceToken"
                >
                  {{ showImageApiBalanceToken ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="imageApiBalanceUserId">用户 ID（余额查询）</label>
              <div class="config-card__input-group">
                <input
                  id="imageApiBalanceUserId"
                  v-model="imageApiForm.balanceUserId"
                  type="text"
                  class="config-card__input"
                  placeholder="在个人中心查看，作为 New-API-User 请求头"
                />
                <button
                  type="button"
                  class="config-card__action-btn"
                  title="测试连接"
                  :disabled="testingImageApiBalance"
                  @click="testImageApiBalanceConnection"
                >
                  <span v-if="testingImageApiBalance" class="config-card__spinner">⟳</span>
                  <span v-else>📡</span>
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="imageApiBalanceRefreshInterval">自动刷新间隔（分钟）</label>
              <input
                id="imageApiBalanceRefreshInterval"
                v-model.number="imageApiForm.balanceRefreshIntervalMinutes"
                type="number"
                class="config-card__input"
                min="1"
                max="60"
                step="1"
              />
              <span class="config-card__hint">头部余额预览按此间隔自动拉取，范围 1-60</span>
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

      <!-- APIYI 设置卡片（gpt-image-2-vip 文生图/编辑，按文档统一视为异步执行） -->
      <div class="config-card">
        <div class="config-card__header" @click="toggleCard('apiyiApi')">
          <span class="config-card__icon">🌐</span>
          <h4 class="config-card__title">APIYI 设置</h4>
          <span class="config-card__hint">gpt-image-2-vip 文生图/编辑</span>
          <!-- APIYI 余额预览 chip：复用 T8 余额 chip 的样式与交互模式，折叠态也能看到 -->
          <span
            class="config-card__balance-chip"
            :class="{
              'config-card__balance-chip--loading': apiyiBalanceStatus === 'loading',
              'config-card__balance-chip--error': apiyiBalanceStatus === 'error',
              'config-card__balance-chip--success': apiyiBalanceStatus === 'success'
            }"
            :title="apiyiBalanceTooltip"
            @click.stop="refreshApiyiBalancePreview"
          >
            <span v-if="apiyiBalanceStatus === 'loading'" class="config-card__balance-spinner">⟳</span>
            <span v-else-if="apiyiBalanceStatus === 'error'" class="config-card__balance-icon">⚠</span>
            <span v-else-if="apiyiBalanceStatus === 'success'" class="config-card__balance-icon">●</span>
            <span class="config-card__balance-label">余额$</span>
            <strong class="config-card__balance-value">{{ apiyiBalanceDisplay }}</strong>
          </span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.apiyiApi }"
            :title="cardCollapsed.apiyiApi ? '展开' : '收起'"
            :aria-label="cardCollapsed.apiyiApi ? '展开' : '收起'"
            @click.stop="toggleCard('apiyiApi')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.apiyiApi" class="config-card__form" @submit.prevent="handleSaveApiyiApi">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="apiyiBaseUrl">Base URL</label>
              <input
                id="apiyiBaseUrl"
                v-model="apiyiApiForm.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://api.apiyi.com"
              />
              <span class="config-card__hint">APIYI 主域名；备用域名：vip.apiyi.com / b.apiyi.com</span>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="apiyiApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="apiyiApiKey"
                  v-model="apiyiApiForm.apiKey"
                  :type="showApiyiApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showApiyiApiKey = !showApiyiApiKey"
                >
                  {{ showApiyiApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="apiyiModels">图像模型列表</label>
              <textarea
                id="apiyiModels"
                v-model="apiyiApiForm.imageModelsText"
                class="config-card__input config-card__textarea"
                placeholder="每行一个模型名称&#10;例如：&#10;gpt-image-2-vip&#10;gpt-image-2"
                rows="3"
              ></textarea>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="apiyiAccessToken">AccessToken（余额查询）</label>
              <div class="config-card__input-wrapper">
                <input
                  id="apiyiAccessToken"
                  v-model="apiyiApiForm.accessToken"
                  :type="showApiyiAccessToken ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="APIYI 控制台 → 个人中心 → 系统令牌"
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showApiyiAccessToken = !showApiyiAccessToken"
                >
                  {{ showApiyiAccessToken ? '🙈' : '👁️' }}
                </button>
              </div>
              <span class="config-card__hint">仅用于在卡片头部展示账户余额（不影响图像生成）；在 apiyi.com 控制台的个人中心生成 AccessToken；与生图 API Key 互相独立</span>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingApiyiApi">
              <span v-if="savingApiyiApi" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingApiyiApi ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="apiyiApiMessage" class="config-card__message" :class="[`config-card__message--${apiyiApiMessageType}`]">
            {{ apiyiApiMessage }}
          </div>
        </form>
      </div>

      <!-- 服务器设置卡片 -->

      <div class="config-card">
        <div class="config-card__header" @click="toggleCard('server')">
          <span class="config-card__icon">⚙️</span>
          <h4 class="config-card__title">服务器设置</h4>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.server }"
            :title="cardCollapsed.server ? '展开' : '收起'"
            :aria-label="cardCollapsed.server ? '展开' : '收起'"
            @click.stop="toggleCard('server')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.server" class="config-card__form" @submit.prevent="handleSaveServer">
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
        <div class="config-card__header" @click="toggleCard('promptOptimize')">
          <span class="config-card__icon">✨</span>
          <h4 class="config-card__title">优化提示词</h4>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.promptOptimize }"
            :title="cardCollapsed.promptOptimize ? '展开' : '收起'"
            :aria-label="cardCollapsed.promptOptimize ? '展开' : '收起'"
            @click.stop="toggleCard('promptOptimize')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.promptOptimize" class="config-card__form" @submit.prevent="handleSavePromptOptimize">
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
                <button
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': promptOptimizeForm.provider === 'volcengine' }]"
                  @click="promptOptimizeForm.provider = 'volcengine'"
                >
                  火山引擎
                </button>
              </div>
            </div>

            <div v-if="promptOptimizeForm.provider === 'openai' || promptOptimizeForm.provider === 'volcengine'" class="config-card__field config-card__field--with-action">
              <label class="config-card__label" for="promptOptimizeBaseUrl">Base URL</label>
              <div class="config-card__input-group">
                <input
                  id="promptOptimizeBaseUrl"
                  v-model="promptOptimizeCurrentBaseUrl"
                  type="text"
                  class="config-card__input"
                  :placeholder="promptOptimizeForm.provider === 'volcengine' ? 'https://ark.cn-beijing.volces.com/api/v3/responses' : 'https://ai.t8star.org'"
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
              <span v-if="promptOptimizeForm.provider === 'volcengine'" class="config-card__hint">Responses API 完整地址</span>
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

            <div v-else-if="promptOptimizeForm.provider === 'volcengine'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeVolcengineApiKey">火山引擎 API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="promptOptimizeVolcengineApiKey"
                  v-model="promptOptimizeForm.volcengineApiKey"
                  :type="showPromptOptimizeApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="输入火山引擎 API Key..."
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

            <div v-if="promptOptimizeForm.provider === 'openai' || promptOptimizeForm.provider === 'volcengine'" class="config-card__field">
              <label class="config-card__label" for="promptOptimizeModel">模型</label>
              <input
                id="promptOptimizeModel"
                v-model="promptOptimizeCurrentModel"
                type="text"
                class="config-card__input"
                :placeholder="promptOptimizeForm.provider === 'volcengine' ? 'doubao-seed-2-1-pro-260628' : 'gpt-5'"
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

            <div v-if="promptOptimizeForm.provider === 'volcengine'" class="config-card__field">
              <label class="config-card__label">模式</label>
              <div class="config-card__input config-card__input--readonly">
                Responses
              </div>
              <span class="config-card__tab-hint">火山引擎使用 /api/v3/responses</span>
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

      <!-- 提示词改变配置卡片 -->
      <div class="config-card">
        <div class="config-card__header" @click="toggleCard('promptTransform')">
          <span class="config-card__icon">✦</span>
          <h4 class="config-card__title">提示词改变</h4>
          <span class="config-card__hint">按媒体平台独立优化</span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.promptTransform }"
            :title="cardCollapsed.promptTransform ? '展开' : '收起'"
            :aria-label="cardCollapsed.promptTransform ? '展开' : '收起'"
            @click.stop="toggleCard('promptTransform')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.promptTransform" class="config-card__form" @submit.prevent="handleSavePromptTransform">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label">媒体平台</label>
              <div class="config-card__tab-group">
                <button
                  v-for="media in promptTransformMediaOptions"
                  :key="media.value"
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': selectedPromptTransformMedia === media.value }]"
                  @click="selectedPromptTransformMedia = media.value"
                >
                  {{ media.label }}
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="promptTransformProvider">模型平台</label>
              <select
                id="promptTransformProvider"
                v-model="currentPromptTransformItem.providerName"
                class="config-card__input config-card__select"
              >
                <option value="">请选择模型平台</option>
                <option v-for="option in promptTransformProviderOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="promptTransformBaseUrl">Base URL</label>
              <input
                id="promptTransformBaseUrl"
                v-model="currentPromptTransformProviderConfig.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://api.example.com"
              />
              <span v-if="currentPromptTransformProviderConfig.mode === 'responses'" class="config-card__hint">Responses API 完整地址</span>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="promptTransformApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="promptTransformApiKey"
                  v-model="currentPromptTransformProviderConfig.apiKey"
                  :type="showPromptTransformApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showPromptTransformApiKey = !showPromptTransformApiKey"
                >
                  {{ showPromptTransformApiKey ? '隐藏' : '显示' }}
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="promptTransformModel">模型名称</label>
              <input
                id="promptTransformModel"
                v-model="currentPromptTransformProviderConfig.model"
                type="text"
                class="config-card__input"
                placeholder="gpt-5"
              />
            </div>

            <div class="config-card__field">
              <label class="config-card__label">系统提示词</label>
              <div class="system-prompts-container">
                <div class="system-prompts-selector">
                  <div
                    v-for="(prompt, index) in currentPromptTransformItem.systemPrompts"
                    :key="prompt.id"
                    :class="['system-prompt-item', { active: currentPromptTransformItem.selectedSystemPromptId === prompt.id }]"
                    @click="selectPromptTransformSystemPrompt(prompt.id)"
                  >
                    <div class="system-prompt-header">
                      <span class="system-prompt-name">{{ prompt.name }}</span>
                      <div class="system-prompt-actions">
                        <button type="button" class="system-prompt-action-btn" @click.stop="editPromptTransformSystemPrompt(index)" title="重命名">✏️</button>
                        <button v-if="currentPromptTransformItem.systemPrompts.length > 1" type="button" class="system-prompt-action-btn" @click.stop="deletePromptTransformSystemPrompt(index)" title="删除">🗑️</button>
                      </div>
                    </div>
                  </div>
                  <button type="button" class="add-system-prompt-btn" @click="addPromptTransformSystemPrompt">+ 添加新提示词</button>
                </div>

                <div class="current-system-prompt">
                  <textarea
                    v-if="currentPromptTransformSystemPrompt"
                    v-model="currentPromptTransformSystemPrompt.content"
                    class="config-card__input config-card__textarea"
                    placeholder="定义该媒体平台的提示词改写规则..."
                    rows="5"
                    @input="syncPromptTransformLegacyPrompt"
                  ></textarea>
                </div>
              </div>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingPromptTransform">
              <span v-if="savingPromptTransform" class="config-card__spinner">⟳</span>
              <span v-else>保存</span>
              {{ savingPromptTransform ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="promptTransformMessage" class="config-card__message" :class="[`config-card__message--${promptTransformMessageType}`]">
            {{ promptTransformMessage }}
          </div>
        </form>
      </div>

      <!-- Fal API配置卡片 -->
      <div class="config-card">
        <div class="config-card__header" @click="toggleCard('falApi')">
          <span class="config-card__icon">🔗</span>
          <h4 class="config-card__title">T8转Fal API 设置</h4>
          <span class="config-card__hint">队列协议（始终异步）余额与T8API 余额共用</span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.falApi }"
            :title="cardCollapsed.falApi ? '展开' : '收起'"
            :aria-label="cardCollapsed.falApi ? '展开' : '收起'"
            @click.stop="toggleCard('falApi')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.falApi" class="config-card__form" @submit.prevent="handleSaveFalApi">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="falBaseUrl">Base URL</label>
              <input
                id="falBaseUrl"
                v-model="falApiForm.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://your-host.com/fal"
              />
              <span class="config-card__hint">完整调用地址为：{Base URL}/{model}（如 gpt-image-2/edit）</span>
            </div>

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
              <label class="config-card__label" for="falModels">Fal 模型</label>
              <input
                id="falModels"
                v-model="falApiForm.falModel"
                type="text"
                class="config-card__input"
                placeholder="openai/gpt-image-2"
              />
              <span class="config-card__hint">模型名称，自动根据参考图切换 edit 端点</span>
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
        <div class="config-card__header" @click="toggleCard('gptsapiApi')">
          <span class="config-card__icon">🧩</span>
          <h4 class="config-card__title">GPTsAPI 设置</h4>
          <span class="config-card__hint">GPTSapi 直连接口</span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.gptsapiApi }"
            :title="cardCollapsed.gptsapiApi ? '展开' : '收起'"
            :aria-label="cardCollapsed.gptsapiApi ? '展开' : '收起'"
            @click.stop="toggleCard('gptsapiApi')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.gptsapiApi" class="config-card__form" @submit.prevent="handleSaveGptsapiApi">
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
        <div class="config-card__header" @click="toggleCard('fileUpload')">
          <span class="config-card__icon">📁</span>
          <h4 class="config-card__title">文件上传设置</h4>
          <span class="config-card__hint">上传图片获取临时 URL，替代 base64 传参</span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.fileUpload }"
            :title="cardCollapsed.fileUpload ? '展开' : '收起'"
            :aria-label="cardCollapsed.fileUpload ? '展开' : '收起'"
            @click.stop="toggleCard('fileUpload')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.fileUpload" class="config-card__form" @submit.prevent="handleSaveFileUpload">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="fileUploadBaseUrl">上传地址 (Base URL)</label>
              <input
                id="fileUploadBaseUrl"
                v-model="fileUploadForm.baseUrl"
                type="text"
                class="config-card__input"
                placeholder="https://ai.t8star.org"
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
        <div class="config-card__header" @click="toggleCard('socialCopyApi')">
          <span class="config-card__icon">📱</span>
          <h4 class="config-card__title">朋友圈文案生成 API</h4>
          <span class="config-card__hint">OpenAI 兼容 / 火山引擎</span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.socialCopyApi }"
            :title="cardCollapsed.socialCopyApi ? '展开' : '收起'"
            :aria-label="cardCollapsed.socialCopyApi ? '展开' : '收起'"
            @click.stop="toggleCard('socialCopyApi')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.socialCopyApi" class="config-card__form" @submit.prevent="handleSaveSocialCopyApi">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label">API Provider</label>
              <div class="config-card__tab-group">
                <button
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': socialCopyApiForm.provider === 'openai' }]"
                  @click="socialCopyApiForm.provider = 'openai'"
                >
                  OpenAI 兼容
                </button>
                <button
                  type="button"
                  :class="['config-card__tab', { 'config-card__tab--active': socialCopyApiForm.provider === 'volcengine' }]"
                  @click="socialCopyApiForm.provider = 'volcengine'"
                >
                  火山引擎
                </button>
              </div>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="socialCopyBaseUrl">Base URL</label>
              <input
                id="socialCopyBaseUrl"
                v-model="socialCopyCurrentBaseUrl"
                type="text"
                class="config-card__input"
                :placeholder="socialCopyApiForm.provider === 'volcengine' ? 'https://ark.cn-beijing.volces.com/api/v3/responses' : 'https://api.example.com'"
              />
              <span class="config-card__hint">
                {{ socialCopyApiForm.provider === 'volcengine' ? 'Responses API 完整地址' : '完整调用地址为：{Base URL}/v1/chat/completions' }}
              </span>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="socialCopyApiKey">API Key</label>
              <div class="config-card__input-wrapper">
                <input
                  id="socialCopyApiKey"
                  v-model="socialCopyCurrentApiKey"
                  :type="showSocialCopyApiKey ? 'text' : 'password'"
                  class="config-card__input"
                  :placeholder="socialCopyApiForm.provider === 'volcengine' ? '输入火山引擎 API Key' : '输入朋友圈文案 API Key'"
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
                v-model="socialCopyCurrentModel"
                type="text"
                class="config-card__input"
                :placeholder="socialCopyApiForm.provider === 'volcengine' ? 'doubao-seed-2-1-pro-260628' : '输入模型名称'"
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

      <!-- 编辑指令预设卡片 -->
      <div class="config-card">
        <div class="config-card__header" @click="toggleCard('editPromptSnippets')">
          <span class="config-card__icon">📝</span>
          <h4 class="config-card__title">编辑指令预设</h4>
          <span class="config-card__hint">编辑页一键追加固定提示词片段</span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.editPromptSnippets }"
            :title="cardCollapsed.editPromptSnippets ? '展开' : '收起'"
            :aria-label="cardCollapsed.editPromptSnippets ? '展开' : '收起'"
            @click.stop="toggleCard('editPromptSnippets')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.editPromptSnippets" class="config-card__form" @submit.prevent="handleSaveEditPromptSnippets">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label">预设片段列表</label>
              <div class="system-prompts-container">
                <div class="system-prompts-selector">
                  <div
                    v-for="(snippet, index) in editPromptSnippetsForm.snippets"
                    :key="snippet.id"
                    :class="['system-prompt-item', { active: editPromptSnippetsForm.selectedSnippetId === snippet.id }]"
                    @click="selectEditPromptSnippet(snippet.id)"
                  >
                    <div class="system-prompt-header">
                      <span class="system-prompt-name">{{ snippet.name || ('片段 ' + (index + 1)) }}</span>
                      <div class="system-prompt-actions">
                        <button type="button" class="system-prompt-action-btn" @click.stop="renameEditPromptSnippet(index)" title="重命名">✏️</button>
                        <button v-if="editPromptSnippetsForm.snippets.length > 0" type="button" class="system-prompt-action-btn" @click.stop="deleteEditPromptSnippet(index)" title="删除">🗑️</button>
                      </div>
                    </div>
                  </div>
                  <button type="button" class="add-system-prompt-btn" @click="addEditPromptSnippet">+ 添加新片段</button>
                </div>

                <!-- 当前选中片段的内容编辑区 -->
                <div class="current-system-prompt">
                  <textarea
                    v-model="currentEditPromptSnippetContent"
                    class="config-card__input config-card__textarea"
                    placeholder="编辑指令预设片段的提示词内容..."
                    rows="4"
                    @input="updateCurrentEditPromptSnippetContent"
                  ></textarea>
                </div>
              </div>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingEditPromptSnippets">
              <span v-if="savingEditPromptSnippets" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingEditPromptSnippets ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="editPromptSnippetsMessage" class="config-card__message" :class="[`config-card__message--${editPromptSnippetsMessageType}`]">
            {{ editPromptSnippetsMessage }}
          </div>
        </form>
      </div>

      <!-- 制作人列表卡片：用于生图/编辑页「制作人」下拉选项的配置 -->
      <div class="config-card">
        <div class="config-card__header" @click="toggleCard('creatorOptions')">
          <span class="config-card__icon">👤</span>
          <h4 class="config-card__title">制作人列表</h4>
          <span class="config-card__hint">生图/编辑页「制作人」下拉选项</span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.creatorOptions }"
            :title="cardCollapsed.creatorOptions ? '展开' : '收起'"
            :aria-label="cardCollapsed.creatorOptions ? '展开' : '收起'"
            @click.stop="toggleCard('creatorOptions')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.creatorOptions" class="config-card__form" @submit.prevent="handleSaveCreatorOptions">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label">制作人列表</label>
              <div class="system-prompts-container">
                <div v-if="creatorOptionsForm.options.length === 0" class="system-prompts-empty">暂无制作人，请添加</div>
                <div
                  v-for="(name, index) in creatorOptionsForm.options"
                  :key="`creator_${index}`"
                  class="system-prompt-item"
                >
                  <div class="system-prompt-header">
                    <input
                      :value="name"
                      @input="updateCreatorOptionName(index, $event.target.value)"
                      @click.stop
                      class="system-prompt-name-input"
                      placeholder="输入制作人姓名"
                    />
                    <div class="system-prompt-actions">
                      <button type="button" class="system-prompt-action-btn" @click.stop="renameCreatorOption(index)" title="重命名">✏️</button>
                      <button v-if="creatorOptionsForm.options.length > 1" type="button" class="system-prompt-action-btn" @click.stop="deleteCreatorOption(index)" title="删除">🗑️</button>
                    </div>
                  </div>
                </div>
                <button type="button" class="add-system-prompt-btn" @click="addCreatorOption">+ 添加新制作人</button>
              </div>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingCreatorOptions">
              <span v-if="savingCreatorOptions" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingCreatorOptions ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="creatorOptionsMessage" class="config-card__message" :class="[`config-card__message--${creatorOptionsMessageType}`]">
            {{ creatorOptionsMessage }}
          </div>
        </form>
      </div>

      <!-- Topaz Gigapixel AI 配置卡片 -->
      <div class="config-card">
        <div class="config-card__header" @click="toggleCard('topazGigapixel')">
          <span class="config-card__icon">🔍</span>
          <h4 class="config-card__title">Topaz Gigapixel AI</h4>
          <span class="config-card__hint">本机商业软件，需已安装 Gigapixel AI ≥ 7.3.0</span>
          <button
            type="button"
            class="config-card__toggle"
            :class="{ 'config-card__toggle--collapsed': cardCollapsed.topazGigapixel }"
            :title="cardCollapsed.topazGigapixel ? '展开' : '收起'"
            :aria-label="cardCollapsed.topazGigapixel ? '展开' : '收起'"
            @click.stop="toggleCard('topazGigapixel')"
          >
            <span class="config-card__toggle-icon">▾</span>
          </button>
        </div>
        <form v-show="!cardCollapsed.topazGigapixel" class="config-card__form" @submit.prevent="handleSaveTopazGigapixel">
          <div class="config-card__content">
            <div class="config-card__field">
              <label class="config-card__label" for="topazExePath">gigapixel.exe 路径</label>
              <div class="config-card__input-wrapper">
                <input
                  id="topazExePath"
                  v-model="topazGigapixelForm.exePath"
                  :type="showTopazExePath ? 'text' : 'password'"
                  class="config-card__input"
                  placeholder="C:\Program Files\Topaz Labs LLC\Topaz Gigapixel AI\gigapixel.exe"
                />
                <button
                  type="button"
                  class="config-card__toggle-visibility"
                  @click="showTopazExePath = !showTopazExePath"
                >
                  {{ showTopazExePath ? '🙈' : '👁️' }}
                </button>
              </div>
              <span class="config-card__hint">使用系统命令（已加入 PATH）时可填 "gigapixel"，否则填完整路径</span>
            </div>

            <div class="config-card__field">
              <label class="config-card__label">
                <input
                  v-model="topazGigapixelForm.useSystemCommand"
                  type="checkbox"
                  class="config-card__checkbox"
                />
                使用系统命令 "gigapixel"（需已配置 PATH）
              </label>
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="topazDefaultScale">默认缩放倍率</label>
              <input
                id="topazDefaultScale"
                v-model.number="topazGigapixelForm.defaultScale"
                type="number"
                class="config-card__input"
                placeholder="2.0"
                min="1"
                max="16"
                step="0.1"
              />
            </div>

            <div class="config-card__field">
              <label class="config-card__label" for="topazDefaultModel">默认模型</label>
              <input
                id="topazDefaultModel"
                v-model="topazGigapixelForm.defaultModel"
                type="text"
                class="config-card__input"
                placeholder="Standard"
                list="topaz-model-list"
              />
              <datalist id="topaz-model-list">
                <option value="Art & CG" />
                <option value="Lines" />
                <option value="Very Compressed" />
                <option value="High Fidelity" />
                <option value="Low Resolution" />
                <option value="Standard" />
                <option value="Text & Shapes" />
                <option value="Redefine" />
                <option value="Recover" />
              </datalist>
            </div>

            <div class="config-card__field-row">
              <div class="config-card__field config-card__field--half">
                <label class="config-card__label" for="topazMaxParallel">并发数</label>
                <input
                  id="topazMaxParallel"
                  v-model.number="topazGigapixelForm.maxParallel"
                  type="number"
                  class="config-card__input"
                  min="1"
                  max="4"
                />
                <span class="config-card__hint">默认 1，Topaz 吃 GPU 资源</span>
              </div>

              <div class="config-card__field config-card__field--half">
                <label class="config-card__label" for="topazTimeout">超时(秒)</label>
                <input
                  id="topazTimeout"
                  v-model.number="topazGigapixelForm.timeout"
                  type="number"
                  class="config-card__input"
                  min="60"
                  max="3600"
                />
                <span class="config-card__hint">默认 600s，10 分钟</span>
              </div>
            </div>
          </div>

          <div class="config-card__actions">
            <button type="submit" class="config-card__save-btn" :disabled="savingTopazGigapixel">
              <span v-if="savingTopazGigapixel" class="config-card__spinner">⏳</span>
              <span v-else>💾</span>
              {{ savingTopazGigapixel ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="topazGigapixelMessage" class="config-card__message" :class="[`config-card__message--${topazGigapixelMessageType}`]">
            {{ topazGigapixelMessage }}
          </div>
        </form>
      </div>
      <!-- T8 平台余额功能已合并到上方"图像生成 API"卡片，共用 baseUrl + balanceToken + balanceUserId + balanceRefreshIntervalMinutes -->
    </div>

    <!-- 通用 confirmDialog：用于制作人删除等二次确认（项目规则禁止使用浏览器原生 confirm） -->
    <ConfirmDialog
      :visible="showCommonConfirmDialog"
      :title="commonConfirmDialogConfig.title"
      :message="commonConfirmDialogConfig.message"
      :confirm-text="commonConfirmDialogConfig.confirmText"
      :cancel-text="commonConfirmDialogConfig.cancelText"
      :danger="commonConfirmDialogConfig.danger"
      @confirm="handleCommonConfirmDialogConfirm"
      @cancel="handleCommonConfirmDialogCancel"
    />

    <!-- 制作人重命名输入弹窗：避免使用浏览器原生 prompt()，改为内置对话框 -->
    <Teleport to="body">
      <Transition name="creator-rename-fade">
        <div v-if="showCreatorRenameDialog" class="creator-rename-overlay" @click.self="handleCreatorRenameCancel">
          <div class="creator-rename-dialog" @click.stop>
            <div class="creator-rename-dialog__header">
              <h3 class="creator-rename-dialog__title">{{ creatorRenameDialogTitle }}</h3>
            </div>
            <div class="creator-rename-dialog__content">
              <p class="creator-rename-dialog__hint">请输入新的制作人姓名（原名称：{{ creatorRenameInitialValue || '（空）' }}）</p>
              <input
                v-model="creatorRenameNewValue"
                class="creator-rename-dialog__input"
                placeholder="制作人姓名"
                @keyup.enter="handleCreatorRenameConfirm"
                ref="creatorRenameInputRef"
              />
            </div>
            <div class="creator-rename-dialog__actions">
              <button type="button" class="creator-rename-dialog__btn creator-rename-dialog__btn--cancel" @click="handleCreatorRenameCancel">取消</button>
              <button type="button" class="creator-rename-dialog__btn creator-rename-dialog__btn--confirm" @click="handleCreatorRenameConfirm">确定</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { useConfigStore } from '@/stores/configStore';
import { getUserBalance, getApiyiBalance } from '@/services/api';
// 引入项目统一的 confirmDialog 组件：制作人列表的删除/重命名等弹窗必须使用此组件（项目规则禁止使用浏览器原生 confirm/alert/prompt）
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue';

const configStore = useConfigStore();

/* eslint-disable */

// T8 平台图像生成 API + 余额查询共用表单
// baseUrl/apiKey 用于文生图/编辑，balanceToken/balanceUserId/balanceRefreshIntervalMinutes 用于余额查询
// 余额字段名（quota）和换算除数（500000）已硬编码在后端，不暴露给用户
const imageApiForm = reactive({
  baseUrl: '',
  apiKey: '',
  imageModelsText: '',
  balanceToken: '',
  balanceUserId: '',
  balanceRefreshIntervalMinutes: 5
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
  volcengineBaseUrl: 'https://ark.cn-beijing.volces.com/api/v3/responses',
  volcengineApiKey: '',
  volcengineModel: 'doubao-seed-2-1-pro-260628',
  systemPrompts: [
    {
      id: 'default',
      name: '默认优化',
      content: '你是一个专业的图像提示词优化专家。请将用户输入的提示词优化为更详细、更适合图像生成的描述。优化后的提示词应该：1. 更具体清晰 2. 包含更多细节描述 3. 适合作为图像生成的输入。请直接返回JSON格式：{"optimized_prompt": "优化后的提示词内容"}，不要包含任何其他内容或解释。'
    }
  ],
  selectedSystemPromptId: 'default'
});

const promptOptimizeCurrentBaseUrl = computed({
  get() {
    return promptOptimizeForm.provider === 'volcengine'
      ? promptOptimizeForm.volcengineBaseUrl
      : promptOptimizeForm.baseUrl;
  },
  set(value) {
    if (promptOptimizeForm.provider === 'volcengine') {
      promptOptimizeForm.volcengineBaseUrl = value;
    } else {
      promptOptimizeForm.baseUrl = value;
    }
  }
});

const promptOptimizeCurrentModel = computed({
  get() {
    return promptOptimizeForm.provider === 'volcengine'
      ? promptOptimizeForm.volcengineModel
      : promptOptimizeForm.model;
  },
  set(value) {
    if (promptOptimizeForm.provider === 'volcengine') {
      promptOptimizeForm.volcengineModel = value;
    } else {
      promptOptimizeForm.model = value;
    }
  }
});

const promptTransformMediaOptions = [
  { value: 'officialAccount', label: '公众号' },
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'shortVideo', label: '短视频' }
];

const promptTransformProviderOptions = [
  { value: 'OpenAI 兼容', label: 'OpenAI 兼容' },
  { value: 'DeepSeek', label: 'DeepSeek' },
  { value: 'XIAOMI', label: 'XIAOMI' },
  { value: '火山引擎', label: '火山引擎' },
  { value: '自定义', label: '自定义' }
];

const createPromptTransformProviderConfigs = () => ({
  'OpenAI 兼容': {
    providerKey: 'openai',
    baseUrl: '',
    apiKey: '',
    model: '',
    mode: 'chat'
  },
  DeepSeek: {
    providerKey: 'deepseek',
    baseUrl: 'https://api.deepseek.com',
    apiKey: '',
    model: 'deepseek-v4-pro',
    mode: 'chat'
  },
  XIAOMI: {
    providerKey: 'xiaomi',
    baseUrl: 'https://api.xiaomimimo.com',
    apiKey: '',
    model: 'mimo-v2.5-pro',
    mode: 'chat'
  },
  '火山引擎': {
    providerKey: 'volcengine',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3/responses',
    apiKey: '',
    model: 'doubao-seed-2-1-pro-260628',
    mode: 'responses'
  },
  '自定义': {
    providerKey: 'openai',
    baseUrl: '',
    apiKey: '',
    model: '',
    mode: 'chat'
  }
});

const createPromptTransformItem = () => ({
  providerName: '',
  providerConfigs: createPromptTransformProviderConfigs(),
  baseUrl: '',
  apiKey: '',
  model: '',
  systemPrompt: '',
  systemPrompts: [
    {
      id: 'default',
      name: '默认提示词',
      content: ''
    }
  ],
  selectedSystemPromptId: 'default'
});

const normalizePromptTransformItemForForm = (item = {}) => {
  const legacyPrompt = item.systemPrompt || '';
  const providerConfigs = createPromptTransformProviderConfigs();
  const hasProviderConfigs = item.providerConfigs && typeof item.providerConfigs === 'object';
  if (hasProviderConfigs) {
    Object.keys(item.providerConfigs).forEach((providerName) => {
      providerConfigs[providerName] = {
        ...(providerConfigs[providerName] || {}),
        ...(item.providerConfigs[providerName] || {})
      };
    });
  }
  if (item.providerName && !providerConfigs[item.providerName]) {
    providerConfigs[item.providerName] = {
      providerKey: 'openai',
      baseUrl: '',
      apiKey: '',
      model: '',
      mode: 'chat'
    };
  }
  if (!hasProviderConfigs && item.providerName && (item.baseUrl || item.apiKey || item.model)) {
    providerConfigs[item.providerName] = {
      ...(providerConfigs[item.providerName] || {}),
      baseUrl: item.baseUrl || providerConfigs[item.providerName]?.baseUrl || '',
      apiKey: item.apiKey !== undefined ? item.apiKey : (providerConfigs[item.providerName]?.apiKey || ''),
      model: item.model || providerConfigs[item.providerName]?.model || '',
      mode: item.mode || providerConfigs[item.providerName]?.mode || 'chat'
    };
  }
  let systemPrompts = Array.isArray(item.systemPrompts)
    ? item.systemPrompts.map((prompt, index) => ({
        id: prompt?.id || `prompt_${index}`,
        name: prompt?.name || `提示词 ${index + 1}`,
        content: prompt?.content || ''
      }))
    : [];

  if (systemPrompts.length === 0) {
    systemPrompts = [{
      id: 'default',
      name: '默认提示词',
      content: legacyPrompt
    }];
  }

  const selectedSystemPromptId = systemPrompts.some(prompt => prompt.id === item.selectedSystemPromptId)
    ? item.selectedSystemPromptId
    : systemPrompts[0]?.id || 'default';
  const selectedPrompt = systemPrompts.find(prompt => prompt.id === selectedSystemPromptId);

  return {
    ...createPromptTransformItem(),
    ...item,
    providerConfigs,
    systemPrompts,
    selectedSystemPromptId,
    systemPrompt: selectedPrompt?.content || legacyPrompt || ''
  };
};

const serializePromptTransformItem = (item = {}) => {
  const normalized = normalizePromptTransformItemForForm(item);
  const selectedPrompt = normalized.systemPrompts.find(prompt => prompt.id === normalized.selectedSystemPromptId);
  const selectedProviderConfig = normalized.providerConfigs[normalized.providerName] || {};
  return {
    providerName: normalized.providerName || '',
    providerConfigs: normalized.providerConfigs,
    baseUrl: selectedProviderConfig.baseUrl || '',
    apiKey: selectedProviderConfig.apiKey || '',
    model: selectedProviderConfig.model || '',
    mode: selectedProviderConfig.mode || 'chat',
    providerKey: selectedProviderConfig.providerKey || 'openai',
    systemPrompt: selectedPrompt?.content || '',
    systemPrompts: normalized.systemPrompts.map(prompt => ({
      id: prompt.id,
      name: prompt.name || '未命名提示词',
      content: prompt.content || ''
    })),
    selectedSystemPromptId: normalized.selectedSystemPromptId
  };
};

const promptTransformForm = reactive({
  items: {
    officialAccount: createPromptTransformItem(),
    xiaohongshu: createPromptTransformItem(),
    shortVideo: createPromptTransformItem()
  }
});

const selectedPromptTransformMedia = ref('officialAccount');
const currentPromptTransformItem = computed(() => promptTransformForm.items[selectedPromptTransformMedia.value]);
const currentPromptTransformProviderConfig = computed(() => {
  const item = currentPromptTransformItem.value;
  const providerName = item?.providerName || '';
  if (!item.providerConfigs || typeof item.providerConfigs !== 'object') {
    item.providerConfigs = createPromptTransformProviderConfigs();
  }
  if (providerName && !item.providerConfigs[providerName]) {
    item.providerConfigs[providerName] = {
      providerKey: 'openai',
      baseUrl: '',
      apiKey: '',
      model: '',
      mode: 'chat'
    };
  }
  return providerName ? item.providerConfigs[providerName] : {
    providerKey: 'openai',
    baseUrl: '',
    apiKey: '',
    model: '',
    mode: 'chat'
  };
});
const currentPromptTransformSystemPrompt = computed(() => {
  const item = currentPromptTransformItem.value;
  if (!item?.systemPrompts?.length) return null;
  return item.systemPrompts.find(prompt => prompt.id === item.selectedSystemPromptId) || item.systemPrompts[0];
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
  baseUrl: '',
  apiKey: '',
  falModel: ''
});

const gptsapiApiForm = reactive({
  baseUrl: 'https://api.gptsapi.net',
  apiKey: ''
});

// APIYI 配置表单（gpt-image-2-vip 文生图/编辑，按文档统一视为异步执行）
// 字段说明：
//   baseUrl - APIYI 域名（默认主域名，备选 vip.apiyi.com / b.apiyi.com）
//   apiKey  - API易 平台获取的 API Key（用于生图 Authorization: Bearer）
//   imageModelsText - 模型名称列表（多行），目前主要用 gpt-image-2-vip
//   accessToken - 余额查询令牌（与生图 apiKey 独立；按文档 Authorization: <token> 无 Bearer 前缀）
const apiyiApiForm = reactive({
  baseUrl: 'https://api.apiyi.com',
  apiKey: '',
  imageModelsText: 'gpt-image-2-vip\ngpt-image-2',
  accessToken: ''
});

const fileUploadForm = reactive({
  baseUrl: '',
  apiKey: ''
});

// Topaz Gigapixel AI 配置表单
const topazGigapixelForm = reactive({
  exePath: '',
  useSystemCommand: false,
  defaultScale: 2.0,
  defaultModel: 'Standard',
  defaultEnabled: true,
  defaultSharpen: 0,
  defaultDenoise: 0,
  defaultCompression: 67,
  defaultFr: 50,
  defaultPreDownscaling: 75,
  maxParallel: 1,
  timeout: 600
});

// 编辑指令预设片段配置表单
// 每个片段结构: { id: string, name: string, content: string }
// selectedSnippetId 用于设置页内当前正在编辑的片段
const editPromptSnippetsForm = reactive({
  snippets: [],
  selectedSnippetId: null
});
// 制作人列表表单：与 editPromptSnippetsForm 写法对称；options 是字符串数组
const creatorOptionsForm = reactive({
  options: []
});
// 当前选中的预设片段内容（绑定到 textarea）
const currentEditPromptSnippetContent = ref('');

const socialCopyApiForm = reactive({
  provider: 'openai',
  baseUrl: '',
  apiKey: '',
  model: '',
  volcengineBaseUrl: 'https://ark.cn-beijing.volces.com/api/v3/responses',
  volcengineApiKey: '',
  volcengineModel: 'doubao-seed-2-1-pro-260628',
  systemPrompt: ''
});

const socialCopyCurrentBaseUrl = computed({
  get() {
    return socialCopyApiForm.provider === 'volcengine'
      ? socialCopyApiForm.volcengineBaseUrl
      : socialCopyApiForm.baseUrl;
  },
  set(value) {
    if (socialCopyApiForm.provider === 'volcengine') {
      socialCopyApiForm.volcengineBaseUrl = value;
    } else {
      socialCopyApiForm.baseUrl = value;
    }
  }
});

const socialCopyCurrentApiKey = computed({
  get() {
    return socialCopyApiForm.provider === 'volcengine'
      ? socialCopyApiForm.volcengineApiKey
      : socialCopyApiForm.apiKey;
  },
  set(value) {
    if (socialCopyApiForm.provider === 'volcengine') {
      socialCopyApiForm.volcengineApiKey = value;
    } else {
      socialCopyApiForm.apiKey = value;
    }
  }
});

const socialCopyCurrentModel = computed({
  get() {
    return socialCopyApiForm.provider === 'volcengine'
      ? socialCopyApiForm.volcengineModel
      : socialCopyApiForm.model;
  },
  set(value) {
    if (socialCopyApiForm.provider === 'volcengine') {
      socialCopyApiForm.volcengineModel = value;
    } else {
      socialCopyApiForm.model = value;
    }
  }
});

// T8 余额字段已合并到 imageApiForm 中（balanceToken/balanceUserId/balanceRefreshIntervalMinutes），
// 旧版独立的 userBalanceForm 已被删除，避免与 store 中的 imageApi.balanceXxx 重复维护

const showImageApiKey = ref(false);
// 余额查询 Token 密码框可见性切换（与 showImageApiKey 同模式）
const showImageApiBalanceToken = ref(false);
const showPromptOptimizeApiKey = ref(false);
const showPromptTransformApiKey = ref(false);
const savingImageApi = ref(false);
const savingPromptOptimize = ref(false);
const savingPromptTransform = ref(false);
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
const promptTransformMessage = ref('');
const promptTransformMessageType = ref('success');
// APIYI 配置状态：复用其他 API 卡片的状态模式
const showApiyiApiKey = ref(false);
const savingApiyiApi = ref(false);
const apiyiApiMessage = ref('');
const apiyiApiMessageType = ref('success');
// AccessToken 输入框显隐切换（与 apiKey 一致用密码框，默认隐藏）
const showApiyiAccessToken = ref(false);
// APIYI 余额卡片头部预览态：折叠态也能看到当前余额
// 状态：'idle'（未配置/未拉取）| 'loading' | 'success' | 'error'
const apiyiBalanceStatus = ref('idle');
const apiyiBalanceDisplay = ref('—');
const apiyiBalanceTooltip = ref('点击刷新余额');
let apiyiBalanceRequestSeq = 0;
const savingFileUpload = ref(false);
const fileUploadMessage = ref('');
const fileUploadMessageType = ref('success');
const showFileUploadApiKey = ref(false);
const showSocialCopyApiKey = ref(false);
const showTopazExePath = ref(false);
const savingTopazGigapixel = ref(false);
const topazGigapixelMessage = ref('');
const topazGigapixelMessageType = ref('success');
// 编辑指令预设片段配置状态
const savingEditPromptSnippets = ref(false);
const editPromptSnippetsMessage = ref('');
const editPromptSnippetsMessageType = ref('success');
// 制作人列表配置状态：与 editPromptSnippets 写法对称
const savingCreatorOptions = ref(false);
const creatorOptionsMessage = ref('');
const creatorOptionsMessageType = ref('success');
// 制作人重命名输入弹窗状态：避免使用浏览器原生 prompt()，使用 confirmDialog 统一弹窗组件
const showCreatorRenameDialog = ref(false);
const creatorRenameDialogTitle = ref('重命名制作人');
const creatorRenameIndex = ref(-1);
const creatorRenameInitialValue = ref('');
const creatorRenameNewValue = ref('');
const savingSocialCopyApi = ref(false);
const socialCopyApiMessage = ref('');
const socialCopyApiMessageType = ref('success');
const imageApiMessage = ref('');
const imageApiMessageType = ref('success');
const serverMessage = ref('');
const serverMessageType = ref('success');
const promptOptimizeMessage = ref('');
const promptOptimizeMessageType = ref('success');
// 旧版用户余额相关 ref（showUserBalanceToken/savingUserBalance/testingUserBalance/userBalanceMessage/...）
// 已合并到 imageApi 相关状态：余额测试中态用 testingImageApiBalance，提示用 imageApiMessage
// T8 平台余额卡片头部预览态：折叠态也能看到当前余额
// 状态：'idle'（未配置/未拉取）| 'loading' | 'success' | 'error'
const testingImageApiBalance = ref(false);
const t8BalanceStatus = ref('idle');
const t8BalanceDisplay = ref('—');
const t8BalanceTooltip = ref('点击刷新余额');
let t8BalanceRequestSeq = 0;

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
    showMessage('apiyiApi', '所有配置已加载', 'success');
    showMessage('fileUpload', '所有配置已加载', 'success');
    showMessage('socialCopyApi', '所有配置已加载', 'success');
    showMessage('topazGigapixel', '所有配置已加载', 'success');
    showMessage('editPromptSnippets', '所有配置已加载', 'success');
    showMessage('creatorOptions', '所有配置已加载', 'success');
    // 旧版独立 userBalance 卡片已合并到 imageApi 卡片，此处不再单独提示 userBalance
    // 配置加载完毕后，若关键字段齐全则自动拉一次头部余额预览
    refreshT8BalancePreview();
    refreshApiyiBalancePreview();
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
  const isVolcengine = promptOptimizeForm.provider === 'volcengine';
  
  if (!isDeepseek && !isXiaomi && !promptOptimizeCurrentBaseUrl.value) {
    showMessage('promptOptimize', '请先填写Base URL', 'error');
    return;
  }

  const apiKeyToUse = isVolcengine ? promptOptimizeForm.volcengineApiKey
    : (isXiaomi ? promptOptimizeForm.xiaomiApiKey
      : (isDeepseek ? promptOptimizeForm.deepseekApiKey : promptOptimizeForm.apiKey));
  if (!apiKeyToUse) {
    const providerName = isVolcengine ? '火山引擎' : (isXiaomi ? 'XIAOMI' : (isDeepseek ? 'DeepSeek' : ''));
    showMessage('promptOptimize', isDeepseek || isXiaomi || isVolcengine ? `请先填写${providerName} API Key` : '请先填写API Key', 'error');
    return;
  }

  const modelToUse = isVolcengine ? promptOptimizeForm.volcengineModel
    : (isXiaomi ? promptOptimizeForm.xiaomiModel
      : (isDeepseek ? promptOptimizeForm.deepseekModel : promptOptimizeForm.model));
  if (!modelToUse) {
    showMessage('promptOptimize', '请先填写模型名称', 'error');
    return;
  }

  testingPromptOptimize.value = true;
  showMessage('promptOptimize', '正在测试连接...', 'info');

  try {
    let testUrl = isVolcengine ? promptOptimizeForm.volcengineBaseUrl.trim()
       : (isXiaomi ? 'https://api.xiaomimimo.com'
         : (isDeepseek ? 'https://api.deepseek.com' : promptOptimizeForm.baseUrl.replace(/\/$/, '')));
    let requestBody = {};

    if (isVolcengine) {
      requestBody = {
        model: modelToUse,
        input: 'test'
      };
    } else if (!isDeepseek && !isXiaomi && promptOptimizeForm.mode === 'responses') {
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
    // 自动刷新间隔：保证 ≥ 1 的整数；非数字 / 空 / 0 都回退到 5
    const minutes = Math.max(1, Math.floor(Number(imageApiForm.balanceRefreshIntervalMinutes) || 5));
    const configData = {
      imageApi: {
        baseUrl: imageApiForm.baseUrl,
        apiKey: imageApiForm.apiKey,
        isAsync: configStore.imageApi?.isAsync ?? false,
        imageModels: parseModels(imageApiForm.imageModelsText),
        // T8 余额查询字段：与生图共用同一 imageApi 块，Base URL 不再单独维护
        balanceToken: imageApiForm.balanceToken,
        balanceUserId: imageApiForm.balanceUserId,
        balanceRefreshIntervalMinutes: minutes
      }
    };

    await configStore.saveConfig(configData);
    await configStore.fetchConfig();
    syncFormsFromStore();
    showMessage('imageApi', '图像API配置保存成功！', 'success');
    // 保存成功后立即刷新头部预览，避免"保存成功但 chip 仍显示旧值"
    refreshT8BalancePreview();
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
    const newPort = serverForm.port;
    const oldPort = configStore.server?.port;
    if (newPort !== oldPort) {
      showMessage('server', `服务器配置保存成功！端口已变更为 ${newPort}，请手动重启后端以让新端口生效。`, 'success');
    } else {
      showMessage('server', '服务器配置保存成功！', 'success');
    }
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
        volcengineBaseUrl: promptOptimizeForm.volcengineBaseUrl,
        volcengineApiKey: promptOptimizeForm.volcengineApiKey,
        volcengineModel: promptOptimizeForm.volcengineModel,
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

const handleSavePromptTransform = async () => {
  if (!validatePromptTransformForm()) {
    return;
  }

  savingPromptTransform.value = true;
  promptTransformMessage.value = '';

  try {
    await configStore.saveConfig({
      promptTransform: {
        items: {
          officialAccount: serializePromptTransformItem(promptTransformForm.items.officialAccount),
          xiaohongshu: serializePromptTransformItem(promptTransformForm.items.xiaohongshu),
          shortVideo: serializePromptTransformItem(promptTransformForm.items.shortVideo)
        }
      }
    });
    showMessage('promptTransform', '提示词改变配置保存成功', 'success');
  } catch (error) {
    showMessage('promptTransform', '保存提示词改变配置失败: ' + error.message, 'error');
  } finally {
    savingPromptTransform.value = false;
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
        baseUrl: falApiForm.baseUrl,
        apiKey: falApiForm.apiKey,
        falModels: falApiForm.falModel ? [falApiForm.falModel] : []
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

// 保存 APIYI 配置到后端
// 校验：baseUrl 必填且为合法 URL；apiKey 必填；至少一个模型名
// accessToken 为可选字段（用户可能只想用生图不想查余额，保存时不应阻断）
const handleSaveApiyiApi = async () => {
  if (!validateApiyiApiForm()) {
    return;
  }
  savingApiyiApi.value = true;
  apiyiApiMessage.value = '';
  try {
    const configData = {
      apiyiApi: {
        baseUrl: apiyiApiForm.baseUrl.trim(),
        apiKey: apiyiApiForm.apiKey,
        imageModels: parseModels(apiyiApiForm.imageModelsText),
        // accessToken 可能为空字符串（清空场景），仍需透传给后端以覆盖旧值
        accessToken: apiyiApiForm.accessToken || ''
      }
    };
    await configStore.saveConfig(configData);
    await configStore.fetchConfig();
    syncFormsFromStore();
    showMessage('apiyiApi', 'APIYI 配置保存成功！', 'success');
    // 保存成功后立即刷新卡片头部余额预览，避免"已保存但显示旧值"
    refreshApiyiBalancePreview();
  } catch (error) {
    showMessage('apiyiApi', '保存 APIYI 配置失败: ' + error.message, 'error');
  } finally {
    savingApiyiApi.value = false;
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
        provider: socialCopyApiForm.provider,
        baseUrl: socialCopyApiForm.baseUrl.trim(),
        apiKey: socialCopyApiForm.apiKey,
        model: socialCopyApiForm.model.trim(),
        volcengineBaseUrl: socialCopyApiForm.volcengineBaseUrl.trim(),
        volcengineApiKey: socialCopyApiForm.volcengineApiKey,
        volcengineModel: socialCopyApiForm.volcengineModel.trim(),
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

const handleSaveTopazGigapixel = async () => {
  // Topaz Gigapixel 表单无需严格校验：exe 路径在使用时会被 check 接口二次校验
  savingTopazGigapixel.value = true;
  topazGigapixelMessage.value = '';
  try {
    const configData = {
      topazGigapixel: {
        exePath: topazGigapixelForm.exePath,
        useSystemCommand: topazGigapixelForm.useSystemCommand,
        defaultScale: topazGigapixelForm.defaultScale,
        defaultModel: topazGigapixelForm.defaultModel,
        defaultEnabled: topazGigapixelForm.defaultEnabled,
        defaultSharpen: topazGigapixelForm.defaultSharpen,
        defaultDenoise: topazGigapixelForm.defaultDenoise,
        defaultCompression: topazGigapixelForm.defaultCompression,
        defaultFr: topazGigapixelForm.defaultFr,
        defaultPreDownscaling: topazGigapixelForm.defaultPreDownscaling,
        maxParallel: topazGigapixelForm.maxParallel,
        timeout: topazGigapixelForm.timeout
      }
    };
    await configStore.saveConfig(configData);
    showMessage('topazGigapixel', 'Topaz Gigapixel 配置保存成功！修改后请手动重启后端以让并发数生效。', 'success');
  } catch (error) {
    showMessage('topazGigapixel', '保存 Topaz Gigapixel 配置失败: ' + error.message, 'error');
  } finally {
    savingTopazGigapixel.value = false;
  }
};

// 旧版独立的 handleSaveUserBalance 已被删除；T8 余额字段已合并到 imageApi 卡片，
// 由 handleSaveImageApi 统一处理（与生图共用同一保存逻辑）

// 卡片头部余额预览：拉取 /api/user/balance 并把结果回填到 chip 上
// 折叠态/展开态都共用这一个函数，由 t8BalanceRequestSeq 防并发竞态
// 字段读取：baseUrl / balanceToken / balanceUserId 全部来自 configStore.imageApi（与生图共用）
const refreshT8BalancePreview = async () => {
  // 关键字段未填齐时直接进入 idle 态，避免发无意义的请求
  const ia = configStore.imageApi || {};
  if (!ia.baseUrl || !ia.balanceToken || !ia.balanceUserId) {
    t8BalanceStatus.value = 'idle';
    t8BalanceDisplay.value = '未配置';
    t8BalanceTooltip.value = '请先在图像生成 API 配置中填写余额 Token、用户 ID';
    return;
  }
  const seq = ++t8BalanceRequestSeq;
  t8BalanceStatus.value = 'loading';
  t8BalanceDisplay.value = '…';
  t8BalanceTooltip.value = '正在拉取…';
  try {
    const result = await getUserBalance();
    if (seq !== t8BalanceRequestSeq) return;  // 期间被更新的请求覆盖，跳过
    if (result && result.status === 'success') {
      t8BalanceStatus.value = 'success';
      t8BalanceDisplay.value = String(result.displayAmount || result.amount);
      t8BalanceTooltip.value = `更新于 ${new Date().toLocaleTimeString()}`;
    } else {
      t8BalanceStatus.value = 'error';
      t8BalanceDisplay.value = '失败';
      t8BalanceTooltip.value = `刷新失败：${(result && result.message) || '未知错误'}`;
    }
  } catch (err) {
    if (seq !== t8BalanceRequestSeq) return;
    t8BalanceStatus.value = 'error';
    t8BalanceDisplay.value = '失败';
    t8BalanceTooltip.value = `刷新失败：${err.message || '网络错误'}`;
  }
};

// APIYI 余额卡片头部预览：拉取 /api/apiyi/balance 并把结果回填到 chip 上
// 折叠态/展开态都共用这一个函数，由 apiyiBalanceRequestSeq 防并发竞态
// 与 T8 余额 chip 共用同样的状态机（idle / loading / success / error）
const refreshApiyiBalancePreview = async () => {
  // 关键字段未填齐（accessToken 为空）时直接进入 idle 态，避免发无意义的请求
  const aiy = configStore.apiyiApi || {};
  if (!aiy.accessToken) {
    apiyiBalanceStatus.value = 'idle';
    apiyiBalanceDisplay.value = '未配置';
    apiyiBalanceTooltip.value = '请先填写 AccessToken';
    return;
  }
  const seq = ++apiyiBalanceRequestSeq;
  apiyiBalanceStatus.value = 'loading';
  apiyiBalanceDisplay.value = '…';
  apiyiBalanceTooltip.value = '正在拉取…';
  try {
    const result = await getApiyiBalance();
    if (seq !== apiyiBalanceRequestSeq) return;  // 期间被更新的请求覆盖，跳过
    if (result && result.status === 'success') {
      apiyiBalanceStatus.value = 'success';
      apiyiBalanceDisplay.value = String(result.displayAmount || result.amount);
      apiyiBalanceTooltip.value = `更新于 ${new Date().toLocaleTimeString()}`;
    } else {
      const message = (result && result.message) || '未知错误';
      showMessage('apiyiApi', `APIYI 余额查询失败: ${message}`, 'error');
      apiyiBalanceStatus.value = 'error';
      apiyiBalanceDisplay.value = '失败';
      apiyiBalanceTooltip.value = `刷新失败：${(result && result.message) || '未知错误'}`;
    }
  } catch (err) {
    const message = err.message || '网络错误';
    if (seq !== apiyiBalanceRequestSeq) return;
    showMessage('apiyiApi', `APIYI 余额查询失败: ${message}`, 'error');
    apiyiBalanceStatus.value = 'error';
    apiyiBalanceDisplay.value = '失败';
    apiyiBalanceTooltip.value = `刷新失败：${err.message || '网络错误'}`;
  }
};

// T8 余额"测试连接"：直接调 /api/user/balance，立即验证配置可用性
// 字段读取：baseUrl / balanceToken / balanceUserId 全部来自 imageApiForm（与生图共用）
const testImageApiBalanceConnection = async () => {
  if (!imageApiForm.baseUrl.trim() || !imageApiForm.balanceToken.trim() || !imageApiForm.balanceUserId.trim()) {
    showMessage('imageApi', '请先填写 Base URL、余额 Token、用户 ID', 'error');
    return;
  }
  testingImageApiBalance.value = true;
  showMessage('imageApi', '正在测试余额连接...', 'info');
  try {
    const result = await getUserBalance();
    if (result && result.status === 'success') {
      showMessage('imageApi', `余额连接成功！余额: ${result.displayAmount || result.amount}`, 'success');
      // 同步刷新头部预览，避免"测试成功但 chip 还显示失败"
      t8BalanceStatus.value = 'success';
      t8BalanceDisplay.value = String(result.displayAmount || result.amount);
      t8BalanceTooltip.value = `更新于 ${new Date().toLocaleTimeString()}`;
    } else {
      showMessage('imageApi', `余额连接失败: ${result?.message || '未知错误'}`, 'error');
    }
  } catch (error) {
    showMessage('imageApi', `余额连接失败: ${error.message}`, 'error');
  } finally {
    testingImageApiBalance.value = false;
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

  // 余额字段交叉校验：只要 Token / 用户 ID 中任一填写，就必须同时填写两者
  // （与旧版 userBalance 校验一致，避免只配一半导致接口必然失败）
  const hasBalanceToken = !!imageApiForm.balanceToken.trim();
  const hasBalanceUserId = !!imageApiForm.balanceUserId.trim();
  if (hasBalanceToken && !hasBalanceUserId) {
    showMessage('imageApi', '已填写余额 Token，请同时填写用户 ID', 'error');
    return false;
  }
  if (hasBalanceUserId && !hasBalanceToken) {
    showMessage('imageApi', '已填写用户 ID，请同时填写余额 Token', 'error');
    return false;
  }
  const minutes = Number(imageApiForm.balanceRefreshIntervalMinutes);
  if (!Number.isFinite(minutes) || minutes < 1 || minutes > 60) {
    showMessage('imageApi', '余额自动刷新间隔必须在 1-60 分钟之间', 'error');
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
  } else if (promptOptimizeForm.provider === 'volcengine') {
    if (!promptOptimizeForm.volcengineBaseUrl) {
      showMessage('promptOptimize', '请输入火山引擎 Responses API Base URL', 'error');
      return false;
    }

    if (!isValidUrl(promptOptimizeForm.volcengineBaseUrl.trim())) {
      showMessage('promptOptimize', '火山引擎 Responses API Base URL格式不正确', 'error');
      return false;
    }

    if (!promptOptimizeForm.volcengineApiKey) {
      showMessage('promptOptimize', '请输入火山引擎 API Key', 'error');
      return false;
    }

    if (!promptOptimizeForm.volcengineModel) {
      showMessage('promptOptimize', '请输入火山引擎模型名称', 'error');
      return false;
    }
  }

  return true;
};

const validatePromptTransformForm = () => {
  const media = promptTransformMediaOptions.find(option => option.value === selectedPromptTransformMedia.value);
  const item = serializePromptTransformItem(promptTransformForm.items[selectedPromptTransformMedia.value]);
  const providerConfig = item.providerConfigs?.[item.providerName] || {};
  const apiValues = [
    item.providerName,
    providerConfig.baseUrl,
    providerConfig.apiKey,
    providerConfig.model
  ].map(value => (value || '').trim());
  const filledApiCount = apiValues.filter(Boolean).length;
  const validPromptCount = item.systemPrompts.filter(prompt => (prompt.content || '').trim()).length;
  const label = media?.label || '当前媒体';

  if ((filledApiCount > 0 || validPromptCount > 0) && (filledApiCount < apiValues.length || validPromptCount === 0)) {
    showMessage('promptTransform', `${label}配置未填写完整`, 'error');
    return false;
  }

  if (providerConfig.baseUrl && !isValidUrl(providerConfig.baseUrl.trim())) {
    showMessage('promptTransform', `${label} Base URL格式不正确`, 'error');
    return false;
  }

  return true;
};

const validateFalApiForm = () => {
  if (!falApiForm.baseUrl.trim()) {
    showMessage('falApi', '请输入Fal API的Base URL', 'error');
    return false;
  }
  if (!isValidUrl(falApiForm.baseUrl.trim())) {
    showMessage('falApi', 'Fal API的Base URL格式不正确', 'error');
    return false;
  }
  if (!falApiForm.apiKey) {
    showMessage('falApi', '请输入Fal API的API Key', 'error');
    return false;
  }
  if (!falApiForm.falModel.trim()) {
    showMessage('falApi', '请输入Fal模型名称', 'error');
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

// APIYI 表单校验：baseUrl 必填且为合法 URL；apiKey 必填；至少一个模型名
const validateApiyiApiForm = () => {
  const baseUrl = apiyiApiForm.baseUrl.trim();
  if (!baseUrl) {
    showMessage('apiyiApi', '请输入 APIYI 的 Base URL', 'error');
    return false;
  }
  if (!isValidUrl(baseUrl)) {
    showMessage('apiyiApi', 'APIYI 的 Base URL 格式不正确', 'error');
    return false;
  }
  if (!apiyiApiForm.apiKey) {
    showMessage('apiyiApi', '请输入 APIYI 的 API Key', 'error');
    return false;
  }
  if (parseModels(apiyiApiForm.imageModelsText).length === 0) {
    showMessage('apiyiApi', '请至少填写一个图像模型', 'error');
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
  if (!socialCopyCurrentBaseUrl.value.trim()) {
    showMessage('socialCopyApi', '请输入朋友圈文案 API 的 Base URL', 'error');
    return false;
  }
  if (!isValidUrl(socialCopyCurrentBaseUrl.value.trim())) {
    showMessage('socialCopyApi', '请输入有效的朋友圈文案 API Base URL', 'error');
    return false;
  }
  if (!socialCopyCurrentApiKey.value) {
    showMessage('socialCopyApi', '请输入朋友圈文案 API Key', 'error');
    return false;
  }
  if (!socialCopyCurrentModel.value.trim()) {
    showMessage('socialCopyApi', '请输入朋友圈文案模型', 'error');
    return false;
  }
  return true;
};

// 旧版独立的 validateUserBalanceForm 已被删除；T8 余额字段校验已合并到 validateImageApiForm
// （余额 Token / 用户 ID 必须同时填写，自动刷新间隔 1-60 分钟）

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

const syncPromptTransformLegacyPrompt = () => {
  const selectedPrompt = currentPromptTransformSystemPrompt.value;
  if (selectedPrompt) {
    currentPromptTransformItem.value.systemPrompt = selectedPrompt.content || '';
  }
};

const selectPromptTransformSystemPrompt = (id) => {
  currentPromptTransformItem.value.selectedSystemPromptId = id;
  syncPromptTransformLegacyPrompt();
};

const addPromptTransformSystemPrompt = () => {
  const item = currentPromptTransformItem.value;
  const newId = 'prompt_' + Date.now();
  item.systemPrompts.push({
    id: newId,
    name: '新提示词 ' + (item.systemPrompts.length + 1),
    content: ''
  });
  item.selectedSystemPromptId = newId;
  syncPromptTransformLegacyPrompt();
};

const editPromptTransformSystemPrompt = (index) => {
  const item = currentPromptTransformItem.value;
  const newName = prompt('请输入新的提示词名称：', item.systemPrompts[index].name);
  if (newName && newName.trim()) {
    item.systemPrompts[index].name = newName.trim();
  }
};

const deletePromptTransformSystemPrompt = (index) => {
  const item = currentPromptTransformItem.value;
  if (item.systemPrompts.length <= 1) {
    return;
  }
  if (confirm('确定要删除这个系统提示词吗？')) {
    const deletedId = item.systemPrompts[index].id;
    item.systemPrompts.splice(index, 1);
    if (deletedId === item.selectedSystemPromptId) {
      item.selectedSystemPromptId = item.systemPrompts[0]?.id || 'default';
    }
    syncPromptTransformLegacyPrompt();
  }
};

// 编辑指令预设片段管理函数
// 功能：选中 / 新增 / 重命名 / 删除 / 内容编辑，与 systemPrompts 列表模式保持一致
const selectEditPromptSnippet = (id) => {
  editPromptSnippetsForm.selectedSnippetId = id;
  updateCurrentEditPromptSnippetDisplay();
};

const updateCurrentEditPromptSnippetDisplay = () => {
  const selected = editPromptSnippetsForm.snippets.find(s => s.id === editPromptSnippetsForm.selectedSnippetId);
  if (selected) {
    currentEditPromptSnippetContent.value = selected.content || '';
  } else {
    currentEditPromptSnippetContent.value = '';
  }
};

const updateCurrentEditPromptSnippetContent = () => {
  const selected = editPromptSnippetsForm.snippets.find(s => s.id === editPromptSnippetsForm.selectedSnippetId);
  if (selected) {
    selected.content = currentEditPromptSnippetContent.value;
  }
};

const addEditPromptSnippet = () => {
  // 使用时间戳 + 随机数避免极端情况下时间戳冲突
  const newId = 'snippet_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
  const newSnippet = {
    id: newId,
    name: '新片段 ' + (editPromptSnippetsForm.snippets.length + 1),
    content: ''
  };
  editPromptSnippetsForm.snippets.push(newSnippet);
  selectEditPromptSnippet(newId);
};

const renameEditPromptSnippet = (index) => {
  // 提示输入新名称；空名称允许（保存时表单不强制 name 必填，仅做显示用）
  const newName = prompt('请输入新的片段名称：', editPromptSnippetsForm.snippets[index].name);
  if (newName !== null) {
    editPromptSnippetsForm.snippets[index].name = newName.trim();
  }
};

const deleteEditPromptSnippet = (index) => {
  if (!editPromptSnippetsForm.snippets[index]) return;
  if (editPromptSnippetsForm.snippets.length <= 1) {
    showMessage('editPromptSnippets', '至少需要保留一条预设片段', 'error');
    return;
  }
  if (confirm('确定要删除这个预设片段吗？')) {
    const deletedId = editPromptSnippetsForm.snippets[index].id;
    editPromptSnippetsForm.snippets.splice(index, 1);
    // 删除当前选中后切到第一条
    if (deletedId === editPromptSnippetsForm.selectedSnippetId && editPromptSnippetsForm.snippets.length > 0) {
      selectEditPromptSnippet(editPromptSnippetsForm.snippets[0].id);
    } else {
      updateCurrentEditPromptSnippetDisplay();
    }
  }
};

// 保存编辑指令预设片段到后端
const handleSaveEditPromptSnippets = async () => {
  savingEditPromptSnippets.value = true;
  editPromptSnippetsMessage.value = '';
  try {
    // 兜底：清除空对象、id 重复等异常
    const cleaned = editPromptSnippetsForm.snippets
      .filter(s => s && typeof s === 'object')
      .map((s, idx) => ({
        id: s.id || ('snippet_' + Date.now() + '_' + idx),
        name: s.name || '片段 ' + (idx + 1),
        content: s.content || ''
      }));
    // 去重 id
    const seen = new Set();
    const dedup = [];
    for (const item of cleaned) {
      if (seen.has(item.id)) {
        item.id = item.id + '_' + Math.floor(Math.random() * 1000);
      }
      seen.add(item.id);
      dedup.push(item);
    }
    const selectedId = dedup.find(s => s.id === editPromptSnippetsForm.selectedSnippetId)
      ? editPromptSnippetsForm.selectedSnippetId
      : (dedup[0]?.id || null);

    editPromptSnippetsForm.snippets = dedup;
    editPromptSnippetsForm.selectedSnippetId = selectedId;

    const configData = {
      editPromptSnippets: {
        snippets: dedup,
        selectedSnippetId: selectedId
      }
    };
    await configStore.saveConfig(configData);
    showMessage('editPromptSnippets', '编辑指令预设保存成功！', 'success');
  } catch (error) {
    showMessage('editPromptSnippets', '保存编辑指令预设失败: ' + error.message, 'error');
  } finally {
    savingEditPromptSnippets.value = false;
  }
};

// ========== 制作人列表配置（creatorOptions）相关方法 ==========
// 实现逻辑：
//   1. 选项来源：configStore.creatorOptions.options（持久化在 app_config.creator_options 表）
//   2. 表单层（creatorOptionsForm.options）是字符串数组，编辑时不影响 store
//   3. 删除/重命名弹窗统一走 confirmDialog 或自定义输入弹窗（项目规则禁止浏览器原生 confirm/prompt/alert）

// 同步 store 中的制作人列表到本地表单
const syncCreatorOptionsForm = () => {
  const list = Array.isArray(configStore.creatorOptions?.options)
    ? configStore.creatorOptions.options
    : []
  creatorOptionsForm.options = [...list]
}

// 新增一个空的制作人输入项
const addCreatorOption = () => {
  creatorOptionsForm.options.push('')
}

// 原地更新指定下标的制作人姓名（input 双向绑定）
const updateCreatorOptionName = (index, value) => {
  if (index < 0 || index >= creatorOptionsForm.options.length) return
  creatorOptionsForm.options[index] = value
}

// 打开重命名弹窗（避免使用 prompt()，使用项目统一弹窗组件 + 自定义输入框）
const renameCreatorOption = (index) => {
  if (index < 0 || index >= creatorOptionsForm.options.length) return
  creatorRenameIndex.value = index
  creatorRenameInitialValue.value = creatorOptionsForm.options[index] || ''
  creatorRenameNewValue.value = creatorRenameInitialValue.value
  creatorRenameDialogTitle.value = '重命名制作人'
  showCreatorRenameDialog.value = true
}

// 确认重命名
const handleCreatorRenameConfirm = () => {
  const idx = creatorRenameIndex.value
  if (idx < 0 || idx >= creatorOptionsForm.options.length) {
    showCreatorRenameDialog.value = false
    return
  }
  const newName = (creatorRenameNewValue.value || '').trim()
  if (newName.length > 0) {
    creatorOptionsForm.options[idx] = newName
  }
  showCreatorRenameDialog.value = false
}

// 取消重命名
const handleCreatorRenameCancel = () => {
  showCreatorRenameDialog.value = false
}

// 删除指定下标的制作人：至少保留 1 项，避免生图/编辑页下拉无选项
const deleteCreatorOption = (index) => {
  if (index < 0 || index >= creatorOptionsForm.options.length) return
  if (creatorOptionsForm.options.length <= 1) {
    showMessage('creatorOptions', '至少需要保留 1 个制作人', 'error')
    return
  }
  const name = creatorOptionsForm.options[index] || `第 ${index + 1} 项`
  // 使用 confirmDialog 而非浏览器 confirm()：符合项目规则
  showConfirmDialog({
    title: '确认删除',
    message: `确定要删除制作人「${name}」吗？此操作只在保存前生效。`,
    confirmText: '删除',
    cancelText: '取消',
    danger: true,
    onConfirm: () => {
      creatorOptionsForm.options.splice(index, 1)
    }
  })
}

// 保存制作人列表到后端：与 editPromptSnippets 保存写法对称
const handleSaveCreatorOptions = async () => {
  savingCreatorOptions.value = true
  creatorOptionsMessage.value = ''
  try {
    // 兜底：去除空字符串、确保至少 1 项
    const cleaned = creatorOptionsForm.options
      .map((name) => (name || '').trim())
      .filter((name) => name.length > 0)
    if (cleaned.length === 0) {
      showMessage('creatorOptions', '制作人列表不能为空，请至少添加 1 项', 'error')
      return
    }
    // 去重：保留第一个出现的，后面的同名项会被忽略
    const seen = new Set()
    const dedup = []
    for (const item of cleaned) {
      if (seen.has(item)) continue
      seen.add(item)
      dedup.push(item)
    }
    creatorOptionsForm.options = dedup
    await configStore.saveConfig({ creatorOptions: { options: dedup } })
    showMessage('creatorOptions', '制作人列表保存成功！', 'success')
  } catch (error) {
    showMessage('creatorOptions', '保存制作人列表失败: ' + (error?.message || '未知错误'), 'error')
  } finally {
    savingCreatorOptions.value = false
  }
}

// ========== 通用 confirmDialog 包装（项目规则禁止使用浏览器原生 confirm/alert/prompt） ==========
// 内部状态：与 DirectCreateView 等视图保持一致的 openConfirmDialog 写法
const showCommonConfirmDialog = ref(false)
const commonConfirmDialogConfig = reactive({
  title: '确认',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  onConfirm: null
})
const showConfirmDialog = (options = {}) => {
  commonConfirmDialogConfig.title = options.title || '确认'
  commonConfirmDialogConfig.message = options.message || ''
  commonConfirmDialogConfig.confirmText = options.confirmText || '确定'
  commonConfirmDialogConfig.cancelText = options.cancelText || '取消'
  commonConfirmDialogConfig.danger = !!options.danger
  commonConfirmDialogConfig.onConfirm = options.onConfirm || null
  showCommonConfirmDialog.value = true
}
const handleCommonConfirmDialogConfirm = () => {
  const action = commonConfirmDialogConfig.onConfirm
  showCommonConfirmDialog.value = false
  if (typeof action === 'function') {
    // 异步错误吞到 console：避免单个回调异常中断整个 UI
    try { action() } catch (e) { console.error('[ConfigPanel] confirmDialog onConfirm 异常:', e) }
  }
}
const handleCommonConfirmDialogCancel = () => {
  commonConfirmDialogConfig.onConfirm = null
  showCommonConfirmDialog.value = false
}

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
  // T8 余额查询字段同步：与生图共用同一 imageApi 块；缺失时回退到空字符串/5 分钟兜底
  imageApiForm.balanceToken = configStore.imageApi?.balanceToken || '';
  imageApiForm.balanceUserId = configStore.imageApi?.balanceUserId || '';
  const balanceMinutes = Number(configStore.imageApi?.balanceRefreshIntervalMinutes);
  imageApiForm.balanceRefreshIntervalMinutes = Number.isFinite(balanceMinutes) && balanceMinutes >= 1
    ? balanceMinutes
    : 5;

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
  promptOptimizeForm.volcengineBaseUrl = configStore.promptOptimize?.volcengineBaseUrl || 'https://ark.cn-beijing.volces.com/api/v3/responses';
  promptOptimizeForm.volcengineApiKey = configStore.promptOptimize?.volcengineApiKey || '';
  promptOptimizeForm.volcengineModel = configStore.promptOptimize?.volcengineModel || 'doubao-seed-2-1-pro-260628';
  
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

  falApiForm.baseUrl = configStore.falApi?.baseUrl || '';
  falApiForm.apiKey = configStore.falApi?.apiKey || '';
  falApiForm.falModel = Array.isArray(configStore.falApi?.falModels) && configStore.falApi.falModels.length > 0
    ? configStore.falApi.falModels[0]
    : 'openai/gpt-image-2';

  gptsapiApiForm.baseUrl = configStore.gptsapiApi?.baseUrl || 'https://api.gptsapi.net';
  gptsapiApiForm.apiKey = configStore.gptsapiApi?.apiKey || '';

  // APIYI 表单同步：缺失时回退到默认 baseUrl 和默认模型
  const apiyiStore = configStore.apiyiApi || {};
  apiyiApiForm.baseUrl = apiyiStore.baseUrl || 'https://api.apiyi.com';
  apiyiApiForm.apiKey = apiyiStore.apiKey || '';
  const apiyiModels = Array.isArray(apiyiStore.imageModels) && apiyiStore.imageModels.length > 0
    ? Array.from(new Set([...apiyiStore.imageModels, 'gpt-image-2']))
    : ['gpt-image-2-vip', 'gpt-image-2'];
  apiyiApiForm.imageModelsText = apiyiModels.join('\n');
  // AccessToken 可为空字符串：与 store 透传一致，避免误把 undefined 写回表单
  apiyiApiForm.accessToken = apiyiStore.accessToken || '';

  fileUploadForm.baseUrl = configStore.fileUpload?.baseUrl || '';
  fileUploadForm.apiKey = configStore.fileUpload?.apiKey || '';

  socialCopyApiForm.provider = configStore.socialCopyApi?.provider || 'openai';
  socialCopyApiForm.baseUrl = configStore.socialCopyApi?.baseUrl || '';
  socialCopyApiForm.apiKey = configStore.socialCopyApi?.apiKey || '';
  socialCopyApiForm.model = configStore.socialCopyApi?.model || '';
  socialCopyApiForm.volcengineBaseUrl = configStore.socialCopyApi?.volcengineBaseUrl || 'https://ark.cn-beijing.volces.com/api/v3/responses';
  socialCopyApiForm.volcengineApiKey = configStore.socialCopyApi?.volcengineApiKey || '';
  socialCopyApiForm.volcengineModel = configStore.socialCopyApi?.volcengineModel || 'doubao-seed-2-1-pro-260628';
  socialCopyApiForm.systemPrompt = configStore.socialCopyApi?.systemPrompt || '';

  const promptTransformItems = configStore.promptTransform?.items || {};
  promptTransformMediaOptions.forEach((media) => {
    promptTransformForm.items[media.value] = normalizePromptTransformItemForForm(promptTransformItems[media.value] || {});
  });

  // Topaz Gigapixel 表单同步
  const tg = configStore.topazGigapixel || {};
  topazGigapixelForm.exePath = tg.exePath || '';
  topazGigapixelForm.useSystemCommand = tg.useSystemCommand !== undefined ? !!tg.useSystemCommand : false;
  topazGigapixelForm.defaultScale = tg.defaultScale !== undefined ? tg.defaultScale : 2.0;
  topazGigapixelForm.defaultModel = tg.defaultModel || 'Standard';
  topazGigapixelForm.defaultEnabled = tg.defaultEnabled !== undefined ? !!tg.defaultEnabled : true;
  topazGigapixelForm.defaultSharpen = tg.defaultSharpen !== undefined ? tg.defaultSharpen : 0;
  topazGigapixelForm.defaultDenoise = tg.defaultDenoise !== undefined ? tg.defaultDenoise : 0;
  topazGigapixelForm.defaultCompression = tg.defaultCompression !== undefined ? tg.defaultCompression : 67;
  topazGigapixelForm.defaultFr = tg.defaultFr !== undefined ? tg.defaultFr : 50;
  topazGigapixelForm.defaultPreDownscaling = tg.defaultPreDownscaling !== undefined ? tg.defaultPreDownscaling : 75;
  topazGigapixelForm.maxParallel = tg.maxParallel !== undefined ? tg.maxParallel : 1;
  topazGigapixelForm.timeout = tg.timeout !== undefined ? tg.timeout : 600;

  // 同步编辑指令预设片段
  // 兜底处理：缺失或非数组时退化为空列表
  const storeSnippets = configStore.editPromptSnippets;
  if (storeSnippets && Array.isArray(storeSnippets.snippets)) {
    // 深拷贝避免表单编辑直接污染 store
    editPromptSnippetsForm.snippets = storeSnippets.snippets.map(s => ({
      id: s.id,
      name: s.name || '',
      content: s.content || ''
    }));
  } else {
    editPromptSnippetsForm.snippets = [];
  }
  editPromptSnippetsForm.selectedSnippetId = storeSnippets?.selectedSnippetId
    || editPromptSnippetsForm.snippets[0]?.id
    || null;
  updateCurrentEditPromptSnippetDisplay();

  // 同步制作人列表到表单：与 editPromptSnippets 同步写法对称
  syncCreatorOptionsForm();

  // T8 余额字段已合并到 imageApi 中（balanceToken/balanceUserId/balanceRefreshIntervalMinutes），
  // 上面 imageApiForm 同步块已统一处理；旧版独立 userBalance 同步块已删除

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

// 各设置卡片的收起/展开状态：true 表示已收起（默认全部收起）
// key 与下方模板中的卡片标识保持一致，新增/删除卡片时需同步更新
// 注意：userBalance 卡片已合并到 imageApi 卡片，不再单独维护 userBalance 状态
const cardCollapsed = reactive({
  imageApi: true,
  // APIYI 卡片：与 apiyiApi 配置对应，新增时需同步注册到 cardCollapsed + showMessage
  apiyiApi: true,
  server: true,
  promptOptimize: true,
  promptTransform: true,
  falApi: true,
  gptsapiApi: true,
  fileUpload: true,
  socialCopyApi: true,
  editPromptSnippets: true,
  topazGigapixel: true,
  // 制作人列表卡片：用于生图/编辑页「制作人」下拉选项的配置
  creatorOptions: true
});

// 切换指定卡片的收起/展开状态
// 逻辑：点击头部按钮时翻转该卡片的 boolean 状态
const toggleCard = (key) => {
  if (cardCollapsed[key] !== undefined) {
    cardCollapsed[key] = !cardCollapsed[key];
  }
};

const showMessage = (type, text, messageType) => {
  if (type === 'imageApi') {
    imageApiMessage.value = text;
    imageApiMessageType.value = messageType;
    setTimeout(() => { imageApiMessage.value = ''; }, 3000);
  } else if (type === 'apiyiApi') {
    // APIYI 消息通道：与 imageApi 写法一致；未注册时调用方静默失败会让用户误以为没保存
    apiyiApiMessage.value = text;
    apiyiApiMessageType.value = messageType;
    setTimeout(() => { apiyiApiMessage.value = ''; }, 3000);
  } else if (type === 'server') {
    serverMessage.value = text;
    serverMessageType.value = messageType;
    setTimeout(() => { serverMessage.value = ''; }, 3000);
  } else if (type === 'promptOptimize') {
    promptOptimizeMessage.value = text;
    promptOptimizeMessageType.value = messageType;
    setTimeout(() => { promptOptimizeMessage.value = ''; }, 3000);
  } else if (type === 'promptTransform') {
    promptTransformMessage.value = text;
    promptTransformMessageType.value = messageType;
    setTimeout(() => { promptTransformMessage.value = ''; }, 3000);
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
  } else if (type === 'topazGigapixel') {
    topazGigapixelMessage.value = text;
    topazGigapixelMessageType.value = messageType;
    setTimeout(() => { topazGigapixelMessage.value = ''; }, 3000);
  } else if (type === 'editPromptSnippets') {
    editPromptSnippetsMessage.value = text;
    editPromptSnippetsMessageType.value = messageType;
    setTimeout(() => { editPromptSnippetsMessage.value = ''; }, 3000);
  } else if (type === 'creatorOptions') {
    // 制作人列表消息通道：与 editPromptSnippets 写法一致
    creatorOptionsMessage.value = text;
    creatorOptionsMessageType.value = messageType;
    setTimeout(() => { creatorOptionsMessage.value = ''; }, 3000);
  }
  // 旧版 userBalance 消息通道已删除：T8 余额相关消息改走 imageApiMessage
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
  configStore.promptOptimize.xiaomiApiKey = promptOptimizeForm.xiaomiApiKey;
  configStore.promptOptimize.xiaomiModel = promptOptimizeForm.xiaomiModel;
  configStore.promptOptimize.xiaomiThinkingEnabled = promptOptimizeForm.xiaomiThinkingEnabled;
  configStore.promptOptimize.xiaomiEnableWebSearch = promptOptimizeForm.xiaomiEnableWebSearch;
  configStore.promptOptimize.volcengineBaseUrl = promptOptimizeForm.volcengineBaseUrl;
  configStore.promptOptimize.volcengineApiKey = promptOptimizeForm.volcengineApiKey;
  configStore.promptOptimize.volcengineModel = promptOptimizeForm.volcengineModel;
  configStore.promptOptimize.systemPrompts = promptOptimizeForm.systemPrompts;
  configStore.promptOptimize.selectedSystemPromptId = promptOptimizeForm.selectedSystemPromptId;
  configStore.saveToStorage();
}, { deep: true });

watch(promptTransformForm, () => {
  configStore.promptTransform = {
    items: {
      officialAccount: serializePromptTransformItem(promptTransformForm.items.officialAccount),
      xiaohongshu: serializePromptTransformItem(promptTransformForm.items.xiaohongshu),
      shortVideo: serializePromptTransformItem(promptTransformForm.items.shortVideo)
    }
  };
  configStore.saveToStorage();
}, { deep: true });


</script>

<style lang="scss" scoped>
@import './ConfigPanel.scss';
</style>
