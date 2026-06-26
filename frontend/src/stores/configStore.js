import { defineStore } from 'pinia';
import { getConfig, saveConfig } from '../services/api';

const STORAGE_KEY = 'app_config';

const createPromptProviderConfigs = () => ({
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
  providerConfigs: createPromptProviderConfigs(),
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

const createPromptTransform = () => ({
  items: {
    officialAccount: createPromptTransformItem(),
    xiaohongshu: createPromptTransformItem(),
    shortVideo: createPromptTransformItem()
  }
});

const normalizePromptTransformItem = (value = {}) => {
  const defaults = createPromptTransformItem();
  const legacyPrompt = value?.systemPrompt || '';
  const providerConfigs = createPromptProviderConfigs();
  const hasProviderConfigs = value?.providerConfigs && typeof value.providerConfigs === 'object';
  if (hasProviderConfigs) {
    for (const providerName of Object.keys(value.providerConfigs)) {
      providerConfigs[providerName] = {
        ...(providerConfigs[providerName] || {}),
        ...(value.providerConfigs[providerName] || {})
      };
    }
  }
  if (value?.providerName && !providerConfigs[value.providerName]) {
    providerConfigs[value.providerName] = {
      providerKey: 'openai',
      baseUrl: '',
      apiKey: '',
      model: '',
      mode: 'chat'
    };
  }
  if (!hasProviderConfigs && value?.providerName && (value?.baseUrl || value?.apiKey || value?.model)) {
    providerConfigs[value.providerName] = {
      ...(providerConfigs[value.providerName] || {}),
      baseUrl: value.baseUrl || providerConfigs[value.providerName]?.baseUrl || '',
      apiKey: value.apiKey !== undefined ? value.apiKey : (providerConfigs[value.providerName]?.apiKey || ''),
      model: value.model || providerConfigs[value.providerName]?.model || '',
      mode: value.mode || providerConfigs[value.providerName]?.mode || 'chat'
    };
  }
  let systemPrompts = Array.isArray(value?.systemPrompts)
    ? value.systemPrompts.map((item, index) => ({
        id: item?.id || `prompt_${index}`,
        name: item?.name || `提示词 ${index + 1}`,
        content: item?.content || ''
      }))
    : [];

  if (systemPrompts.length === 0) {
    systemPrompts = [{
      id: 'default',
      name: '默认提示词',
      content: legacyPrompt
    }];
  }

  const selectedSystemPromptId = systemPrompts.some(item => item.id === value?.selectedSystemPromptId)
    ? value.selectedSystemPromptId
    : systemPrompts[0]?.id || 'default';
  const selectedPrompt = systemPrompts.find(item => item.id === selectedSystemPromptId);

  return {
    ...defaults,
    ...value,
    providerConfigs,
    systemPrompts,
    selectedSystemPromptId,
    systemPrompt: selectedPrompt?.content || legacyPrompt || ''
  };
};

const normalizePromptTransform = (value = {}) => {
  const defaults = createPromptTransform();
  const items = value?.items || {};
  return {
    items: {
      officialAccount: normalizePromptTransformItem({ ...defaults.items.officialAccount, ...(items.officialAccount || {}) }),
      xiaohongshu: normalizePromptTransformItem({ ...defaults.items.xiaohongshu, ...(items.xiaohongshu || {}) }),
      shortVideo: normalizePromptTransformItem({ ...defaults.items.shortVideo, ...(items.shortVideo || {}) })
    }
  };
};

const defaultConfig = {
  version: 6,
  // T8 平台图像生成 API 与余额查询共用 baseUrl
  // balanceToken / balanceUserId / balanceRefreshIntervalMinutes 三个字段供设置页"余额"功能使用
  // 余额字段名与换算除数已硬编码在后端 (backend/routes/user_balance.py)
  imageApi: {
    baseUrl: 'https://ai.t8star.org ',
    apiKey: '',
    isAsync: false,
    imageModels: ['gpt-image-2'],
    balanceToken: '',
    balanceUserId: '',
    balanceRefreshIntervalMinutes: 5
  },
  server: {
    port: 5678
  },
  promptOptimize: {
    baseUrl: 'https://ai.t8star.org',
    apiKey: '',
    model: 'gpt-5',
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
  },
  falApi: {
    baseUrl: '',
    apiKey: '',
    falModels: ['openai/gpt-image-2']
  },
  gptsapiApi: {
    baseUrl: 'https://api.gptsapi.net',
    apiKey: ''
  },
  // APIYI（gpt-image-2-vip）端口配置：默认主域名 + 固定模型名
  // 由后端 ThreadPoolExecutor 包装为异步任务，提交后立即返回 task_id
  // 字段说明：
  //   baseUrl      - APIYI 主域名（默认 https://api.apiyi.com）
  //   apiKey       - API易控制台获取的 Bearer Token（用于生图 Authorization: Bearer）
  //   imageModels  - 可用模型列表（默认 ['gpt-image-2-vip']）
  //   accessToken  - 余额查询令牌（与 apiKey 独立；按文档 Authorization: <token> 无 Bearer 前缀）
  apiyiApi: {
    baseUrl: 'https://api.apiyi.com',
    apiKey: '',
    imageModels: ['gpt-image-2-vip', 'gpt-image-2'],
    accessToken: ''
  },
  fileUpload: {
    baseUrl: 'https://ai.t8star.org',
    apiKey: ''
  },
  socialCopyApi: {
    provider: 'openai',
    baseUrl: '',
    apiKey: '',
    model: '',
    volcengineBaseUrl: 'https://ark.cn-beijing.volces.com/api/v3/responses',
    volcengineApiKey: '',
    volcengineModel: 'doubao-seed-2-1-pro-260628',
    systemPrompt: ''
  },
  promptTransform: createPromptTransform(),
  topazGigapixel: {
    exePath: 'C:\\Program Files\\Topaz Labs LLC\\Topaz Gigapixel AI\\gigapixel.exe',
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
    timeout: 600,
    descriptionVisibility: {
      intro: true,
      scale: true,
      model: true,
      sharpen: true,
      denoise: true,
      compression: true,
      fr: true,
      pre_downscaling: true
    }
  },
  // 编辑指令预设片段：用于编辑页一键追加固定提示词
  editPromptSnippets: {
    snippets: [],
    selectedSnippetId: null
  },
  // 制作人列表：用于生图/编辑页「制作人」下拉选项，默认 5 项
  creatorOptions: {
    options: ['李', '王苗', '王懿', '邢艳霞', '王龙']
  }
};

function migrateOldStorage(oldData) {
  /** 将旧版存储配置迁移到新版结构 */
  const newConfig = { ...defaultConfig };

  if (oldData.apiBaseUrl) {
    newConfig.imageApi.baseUrl = oldData.apiBaseUrl;
  }
  if (oldData.apiKey) {
    newConfig.imageApi.apiKey = oldData.apiKey;
  }
  if (oldData.port) {
    newConfig.server.port = oldData.port;
  }
  if (Array.isArray(oldData.models)) {
    newConfig.imageApi.imageModels = oldData.models;
  }

  return newConfig;
}

function loadFromStorage() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (!data) {
      return { ...defaultConfig };
    }

    const parsed = JSON.parse(data);

    if (!parsed.version || !parsed.imageApi || parsed.version < 4) {
      if (parsed.promptOptimize && typeof parsed.promptOptimize === 'object') {
        const merged = { ...defaultConfig };
        for (const key of Object.keys(parsed)) {
          if (key === 'version') continue;
          if (typeof parsed[key] === 'object' && parsed[key] !== null && !Array.isArray(parsed[key])) {
            merged[key] = { ...merged[key], ...parsed[key] };
          } else {
            merged[key] = parsed[key];
          }
        }
        merged.version = defaultConfig.version;
        saveToStorage(merged);
        return merged;
      }
      const migrated = migrateOldStorage(parsed);
      saveToStorage(migrated);
      return migrated;
    }

    const merged = { ...defaultConfig };
    for (const key of Object.keys(parsed)) {
      if (key === 'version') continue;
      if (typeof parsed[key] === 'object' && parsed[key] !== null && !Array.isArray(parsed[key])) {
        merged[key] = { ...merged[key], ...parsed[key] };
      } else {
        merged[key] = parsed[key];
      }
    }
    merged.version = defaultConfig.version;
    return merged;
  } catch {
    return { ...defaultConfig };
  }
}

function saveToStorage(config) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export const useConfigStore = defineStore('config', {
  state: () => ({
    version: defaultConfig.version,
    // T8 平台图像生成 API：包含余额查询共用字段
    imageApi: {
      baseUrl: defaultConfig.imageApi.baseUrl,
      apiKey: defaultConfig.imageApi.apiKey,
      isAsync: defaultConfig.imageApi.isAsync,
      imageModels: [...defaultConfig.imageApi.imageModels],
      balanceToken: defaultConfig.imageApi.balanceToken,
      balanceUserId: defaultConfig.imageApi.balanceUserId,
      balanceRefreshIntervalMinutes: defaultConfig.imageApi.balanceRefreshIntervalMinutes
    },
    server: {
      port: defaultConfig.server.port
    },
    promptOptimize: {
      baseUrl: defaultConfig.promptOptimize.baseUrl,
      apiKey: defaultConfig.promptOptimize.apiKey,
      model: defaultConfig.promptOptimize.model,
      mode: defaultConfig.promptOptimize.mode,
      enableWebSearch: defaultConfig.promptOptimize.enableWebSearch,
      systemPrompt: defaultConfig.promptOptimize.systemPrompt,
      provider: defaultConfig.promptOptimize.provider,
      deepseekApiKey: defaultConfig.promptOptimize.deepseekApiKey,
      deepseekModel: defaultConfig.promptOptimize.deepseekModel,
      thinkingEnabled: defaultConfig.promptOptimize.thinkingEnabled,
      reasoningEffort: defaultConfig.promptOptimize.reasoningEffort,
      xiaomiApiKey: defaultConfig.promptOptimize.xiaomiApiKey,
      xiaomiModel: defaultConfig.promptOptimize.xiaomiModel,
      xiaomiThinkingEnabled: defaultConfig.promptOptimize.xiaomiThinkingEnabled,
      xiaomiEnableWebSearch: defaultConfig.promptOptimize.xiaomiEnableWebSearch,
      volcengineBaseUrl: defaultConfig.promptOptimize.volcengineBaseUrl,
      volcengineApiKey: defaultConfig.promptOptimize.volcengineApiKey,
      volcengineModel: defaultConfig.promptOptimize.volcengineModel,
      systemPrompts: [...defaultConfig.promptOptimize.systemPrompts],
      selectedSystemPromptId: defaultConfig.promptOptimize.selectedSystemPromptId
    },
    falApi: {
      baseUrl: defaultConfig.falApi.baseUrl,
      apiKey: defaultConfig.falApi.apiKey,
      falModels: [...defaultConfig.falApi.falModels]
    },
    gptsapiApi: {
      baseUrl: defaultConfig.gptsapiApi.baseUrl,
      apiKey: defaultConfig.gptsapiApi.apiKey
    },
    // APIYI 状态：与 gptsapiApi 字段保持同级
    apiyiApi: {
      baseUrl: defaultConfig.apiyiApi.baseUrl,
      apiKey: defaultConfig.apiyiApi.apiKey,
      imageModels: [...defaultConfig.apiyiApi.imageModels],
      accessToken: defaultConfig.apiyiApi.accessToken
    },
    fileUpload: {
      baseUrl: defaultConfig.fileUpload.baseUrl,
      apiKey: defaultConfig.fileUpload.apiKey
    },
    socialCopyApi: {
      provider: defaultConfig.socialCopyApi.provider,
      baseUrl: defaultConfig.socialCopyApi.baseUrl,
      apiKey: defaultConfig.socialCopyApi.apiKey,
      model: defaultConfig.socialCopyApi.model,
      volcengineBaseUrl: defaultConfig.socialCopyApi.volcengineBaseUrl,
      volcengineApiKey: defaultConfig.socialCopyApi.volcengineApiKey,
      volcengineModel: defaultConfig.socialCopyApi.volcengineModel,
      systemPrompt: defaultConfig.socialCopyApi.systemPrompt
    },
    promptTransform: normalizePromptTransform(defaultConfig.promptTransform),
    topazGigapixel: {
      exePath: defaultConfig.topazGigapixel.exePath,
      useSystemCommand: defaultConfig.topazGigapixel.useSystemCommand,
      defaultScale: defaultConfig.topazGigapixel.defaultScale,
      defaultModel: defaultConfig.topazGigapixel.defaultModel,
      defaultEnabled: defaultConfig.topazGigapixel.defaultEnabled,
      defaultSharpen: defaultConfig.topazGigapixel.defaultSharpen,
      defaultDenoise: defaultConfig.topazGigapixel.defaultDenoise,
      defaultCompression: defaultConfig.topazGigapixel.defaultCompression,
      defaultFr: defaultConfig.topazGigapixel.defaultFr,
      defaultPreDownscaling: defaultConfig.topazGigapixel.defaultPreDownscaling,
      maxParallel: defaultConfig.topazGigapixel.maxParallel,
      timeout: defaultConfig.topazGigapixel.timeout,
      descriptionVisibility: { ...defaultConfig.topazGigapixel.descriptionVisibility }
    },
    // 编辑指令预设片段：默认空数组，等待用户在设置页中维护
    editPromptSnippets: {
      snippets: [...defaultConfig.editPromptSnippets.snippets],
      selectedSnippetId: defaultConfig.editPromptSnippets.selectedSnippetId
    },
    // 制作人列表：默认与 defaultConfig.creatorOptions.options 同步
    creatorOptions: {
      options: [...defaultConfig.creatorOptions.options]
    },
    // 图像生成页图片库「制作人」筛选持久化值
    // 缺省时回退到空串（全部制作人）
    imageLibraryCreatorFilter: {
      selectedCreator: ''
    },
    loading: false,
    error: null,
    initialized: false
  }),

  actions: {
    async fetchConfig() {
      this.loading = true;
      this.error = null;
      try {
        console.log('[ConfigStore] fetchConfig - 开始从后端API读取配置');
        const response = await getConfig();
        console.log('[ConfigStore] fetchConfig - API响应:', response);
        const configData = response?.config || response;

        if (configData) {
          console.log('[ConfigStore] fetchConfig - 解析到的配置数据:', configData);
          this.applyConfig(configData);
          this.saveToStorage();
          console.log('[ConfigStore] fetchConfig - 配置已应用到store并保存到localStorage');
        } else {
          console.warn('[ConfigStore] fetchConfig - API返回数据中无config字段');
        }
      } catch (err) {
        console.error('[ConfigStore] fetchConfig - 从后端获取配置失败:', err.message || err);
        const cachedConfig = loadFromStorage();
        console.log('[ConfigStore] fetchConfig - 使用localStorage缓存:', cachedConfig);
        this.applyConfig(cachedConfig);
        this.error = err.message || '获取配置失败';
        this.initialized = true;
        this.loading = false;
        throw new Error('无法连接到服务器获取配置，请确保后端服务正在运行');
      } finally {
        this.initialized = true;
        this.loading = false;
      }
    },

    async saveConfig(configData) {
      this.loading = true;
      this.error = null;
      try {
        console.log('[ConfigStore] saveConfig - 开始保存配置:', configData);
        await saveConfig(configData);
        console.log('[ConfigStore] saveConfig - 后端保存成功');

        if (configData.imageApi) {
          this.imageApi.baseUrl = configData.imageApi.baseUrl || this.imageApi.baseUrl;
          this.imageApi.apiKey = configData.imageApi.apiKey !== undefined ? configData.imageApi.apiKey : this.imageApi.apiKey;
          if (configData.imageApi.isAsync !== undefined) {
            this.imageApi.isAsync = configData.imageApi.isAsync;
          }
          if (configData.imageApi.imageModels !== undefined) {
            this.imageApi.imageModels = Array.isArray(configData.imageApi.imageModels) && configData.imageApi.imageModels.length > 0
              ? configData.imageApi.imageModels
              : [...defaultConfig.imageApi.imageModels];
          }
          // 余额查询字段：缺失时保留旧值，避免部分更新时清空用户已配置的 token/userId
          if (configData.imageApi.balanceToken !== undefined) {
            this.imageApi.balanceToken = configData.imageApi.balanceToken;
          }
          if (configData.imageApi.balanceUserId !== undefined) {
            this.imageApi.balanceUserId = configData.imageApi.balanceUserId;
          }
          if (configData.imageApi.balanceRefreshIntervalMinutes !== undefined) {
            const minutes = Number(configData.imageApi.balanceRefreshIntervalMinutes);
            if (Number.isFinite(minutes) && minutes >= 1) {
              this.imageApi.balanceRefreshIntervalMinutes = minutes;
            }
          }
        }

        if (configData.server) {
          this.server.port = configData.server.port !== undefined ? configData.server.port : this.server.port;
        }

        if (configData.promptOptimize) {
          this.promptOptimize.baseUrl = configData.promptOptimize.baseUrl || this.promptOptimize.baseUrl;
          this.promptOptimize.apiKey = configData.promptOptimize.apiKey !== undefined ? configData.promptOptimize.apiKey : this.promptOptimize.apiKey;
          this.promptOptimize.model = configData.promptOptimize.model || this.promptOptimize.model;
          this.promptOptimize.mode = configData.promptOptimize.mode || this.promptOptimize.mode;
          if (configData.promptOptimize.enableWebSearch !== undefined) {
            this.promptOptimize.enableWebSearch = configData.promptOptimize.enableWebSearch;
          }
          this.promptOptimize.systemPrompt = configData.promptOptimize.systemPrompt || this.promptOptimize.systemPrompt;
          this.promptOptimize.provider = configData.promptOptimize.provider || this.promptOptimize.provider;
          this.promptOptimize.deepseekApiKey = configData.promptOptimize.deepseekApiKey !== undefined ? configData.promptOptimize.deepseekApiKey : this.promptOptimize.deepseekApiKey;
          this.promptOptimize.deepseekModel = configData.promptOptimize.deepseekModel || this.promptOptimize.deepseekModel;
          if (configData.promptOptimize.thinkingEnabled !== undefined) {
            this.promptOptimize.thinkingEnabled = configData.promptOptimize.thinkingEnabled;
          }
          this.promptOptimize.reasoningEffort = configData.promptOptimize.reasoningEffort || this.promptOptimize.reasoningEffort;
          if (configData.promptOptimize.xiaomiApiKey !== undefined) {
            this.promptOptimize.xiaomiApiKey = configData.promptOptimize.xiaomiApiKey;
          }
          this.promptOptimize.xiaomiModel = configData.promptOptimize.xiaomiModel || this.promptOptimize.xiaomiModel;
          if (configData.promptOptimize.xiaomiThinkingEnabled !== undefined) {
            this.promptOptimize.xiaomiThinkingEnabled = configData.promptOptimize.xiaomiThinkingEnabled;
          }
          if (configData.promptOptimize.xiaomiEnableWebSearch !== undefined) {
            this.promptOptimize.xiaomiEnableWebSearch = configData.promptOptimize.xiaomiEnableWebSearch;
          }
          this.promptOptimize.volcengineBaseUrl = configData.promptOptimize.volcengineBaseUrl || this.promptOptimize.volcengineBaseUrl;
          if (configData.promptOptimize.volcengineApiKey !== undefined) {
            this.promptOptimize.volcengineApiKey = configData.promptOptimize.volcengineApiKey;
          }
          this.promptOptimize.volcengineModel = configData.promptOptimize.volcengineModel || this.promptOptimize.volcengineModel;
          if (configData.promptOptimize.systemPrompts !== undefined) {
            this.promptOptimize.systemPrompts = Array.isArray(configData.promptOptimize.systemPrompts) && configData.promptOptimize.systemPrompts.length > 0
              ? configData.promptOptimize.systemPrompts
              : [...defaultConfig.promptOptimize.systemPrompts];
          }
          if (configData.promptOptimize.selectedSystemPromptId !== undefined) {
            this.promptOptimize.selectedSystemPromptId = configData.promptOptimize.selectedSystemPromptId;
          }
        }

        if (configData.falApi) {
          this.falApi.baseUrl = configData.falApi.baseUrl !== undefined ? configData.falApi.baseUrl : this.falApi.baseUrl;
          this.falApi.apiKey = configData.falApi.apiKey !== undefined ? configData.falApi.apiKey : this.falApi.apiKey;
          if (configData.falApi.falModels !== undefined) {
            this.falApi.falModels = Array.isArray(configData.falApi.falModels) && configData.falApi.falModels.length > 0
              ? configData.falApi.falModels
              : [...defaultConfig.falApi.falModels];
          }
        }

        if (configData.gptsapiApi) {
          this.gptsapiApi.baseUrl = configData.gptsapiApi.baseUrl || this.gptsapiApi.baseUrl;
          this.gptsapiApi.apiKey = configData.gptsapiApi.apiKey !== undefined ? configData.gptsapiApi.apiKey : this.gptsapiApi.apiKey;
        }

        // APIYI 配置保存：缺失字段保留旧值，imageModels 留空时回退到默认
        if (configData.apiyiApi) {
          this.apiyiApi.baseUrl = configData.apiyiApi.baseUrl || this.apiyiApi.baseUrl;
          this.apiyiApi.apiKey = configData.apiyiApi.apiKey !== undefined ? configData.apiyiApi.apiKey : this.apiyiApi.apiKey;
          if (configData.apiyiApi.imageModels !== undefined) {
            this.apiyiApi.imageModels = Array.isArray(configData.apiyiApi.imageModels) && configData.apiyiApi.imageModels.length > 0
              ? configData.apiyiApi.imageModels
              : [...defaultConfig.apiyiApi.imageModels];
          }
          // accessToken 透传：undefined 时保留旧值，'' 时显式清空
          if (configData.apiyiApi.accessToken !== undefined) {
            this.apiyiApi.accessToken = configData.apiyiApi.accessToken;
          }
        }

        if (configData.fileUpload) {
          this.fileUpload.baseUrl = configData.fileUpload.baseUrl || this.fileUpload.baseUrl;
          this.fileUpload.apiKey = configData.fileUpload.apiKey !== undefined ? configData.fileUpload.apiKey : this.fileUpload.apiKey;
        }

        if (configData.socialCopyApi) {
          this.socialCopyApi.provider = configData.socialCopyApi.provider || this.socialCopyApi.provider;
          this.socialCopyApi.baseUrl = configData.socialCopyApi.baseUrl !== undefined ? configData.socialCopyApi.baseUrl : this.socialCopyApi.baseUrl;
          this.socialCopyApi.apiKey = configData.socialCopyApi.apiKey !== undefined ? configData.socialCopyApi.apiKey : this.socialCopyApi.apiKey;
          this.socialCopyApi.model = configData.socialCopyApi.model !== undefined ? configData.socialCopyApi.model : this.socialCopyApi.model;
          this.socialCopyApi.volcengineBaseUrl = configData.socialCopyApi.volcengineBaseUrl || this.socialCopyApi.volcengineBaseUrl;
          this.socialCopyApi.volcengineApiKey = configData.socialCopyApi.volcengineApiKey !== undefined ? configData.socialCopyApi.volcengineApiKey : this.socialCopyApi.volcengineApiKey;
          this.socialCopyApi.volcengineModel = configData.socialCopyApi.volcengineModel || this.socialCopyApi.volcengineModel;
          this.socialCopyApi.systemPrompt = configData.socialCopyApi.systemPrompt !== undefined ? configData.socialCopyApi.systemPrompt : this.socialCopyApi.systemPrompt;
        }

        if (configData.promptTransform) {
          this.promptTransform = normalizePromptTransform(configData.promptTransform);
        }

        if (configData.topazGigapixel) {
          const tg = configData.topazGigapixel;
          if (tg.exePath !== undefined) this.topazGigapixel.exePath = tg.exePath;
          if (tg.useSystemCommand !== undefined) this.topazGigapixel.useSystemCommand = tg.useSystemCommand;
          if (tg.defaultScale !== undefined) this.topazGigapixel.defaultScale = tg.defaultScale;
          if (tg.defaultModel !== undefined) this.topazGigapixel.defaultModel = tg.defaultModel;
          if (tg.defaultEnabled !== undefined) this.topazGigapixel.defaultEnabled = tg.defaultEnabled;
          if (tg.defaultSharpen !== undefined) this.topazGigapixel.defaultSharpen = tg.defaultSharpen;
          if (tg.defaultDenoise !== undefined) this.topazGigapixel.defaultDenoise = tg.defaultDenoise;
          if (tg.defaultCompression !== undefined) this.topazGigapixel.defaultCompression = tg.defaultCompression;
          if (tg.defaultFr !== undefined) this.topazGigapixel.defaultFr = tg.defaultFr;
          if (tg.defaultPreDownscaling !== undefined) this.topazGigapixel.defaultPreDownscaling = tg.defaultPreDownscaling;
          if (tg.maxParallel !== undefined) this.topazGigapixel.maxParallel = tg.maxParallel;
          if (tg.timeout !== undefined) this.topazGigapixel.timeout = tg.timeout;
          if (tg.descriptionVisibility !== undefined) {
            this.topazGigapixel.descriptionVisibility = { ...this.topazGigapixel.descriptionVisibility, ...tg.descriptionVisibility };
          }
        }

        if (configData.gigapixelDescVisibility) {
          this.topazGigapixel.descriptionVisibility = { ...this.topazGigapixel.descriptionVisibility, ...configData.gigapixelDescVisibility };
        }

        if (configData.editPromptSnippets) {
          if (Array.isArray(configData.editPromptSnippets.snippets)) {
            this.editPromptSnippets.snippets = configData.editPromptSnippets.snippets;
          }
          if (configData.editPromptSnippets.selectedSnippetId !== undefined) {
            this.editPromptSnippets.selectedSnippetId = configData.editPromptSnippets.selectedSnippetId;
          }
        }

        // 制作人列表：缺失字段保留旧值，空数组时回退到默认 5 项
        if (configData.creatorOptions) {
          if (Array.isArray(configData.creatorOptions.options)) {
            this.creatorOptions.options = configData.creatorOptions.options.length > 0
              ? configData.creatorOptions.options.map(o => String(o))
              : [...defaultConfig.creatorOptions.options];
          }
        }

        // 图像生成页「制作人」筛选持久化值：缺失字段保留旧值，undefined 透传 '' 兜底
        if (configData.imageLibraryCreatorFilter) {
          if (configData.imageLibraryCreatorFilter.selectedCreator !== undefined) {
            this.imageLibraryCreatorFilter.selectedCreator = String(configData.imageLibraryCreatorFilter.selectedCreator || '');
          }
        }

        // T8 余额相关字段已合并到 imageApi.balanceToken / imageApi.balanceUserId / imageApi.balanceRefreshIntervalMinutes，
        // 上面 imageApi 分支已统一处理，此处不再单独维护 userBalance

        this.saveToStorage();
      } catch (err) {
        console.error('[ConfigStore] saveConfig - 保存配置失败:', err.message || err);
        this.error = err.message || '保存配置失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    updateLocalConfig(configData) {
      if (configData.imageApi) {
        if (configData.imageApi.baseUrl) this.imageApi.baseUrl = configData.imageApi.baseUrl;
        if (configData.imageApi.apiKey !== undefined) this.imageApi.apiKey = configData.imageApi.apiKey;
        if (configData.imageApi.isAsync !== undefined) this.imageApi.isAsync = configData.imageApi.isAsync;
        if (configData.imageApi.imageModels !== undefined) {
          this.imageApi.imageModels = Array.isArray(configData.imageApi.imageModels) && configData.imageApi.imageModels.length > 0
            ? configData.imageApi.imageModels
            : [...defaultConfig.imageApi.imageModels];
        }
      }

      if (configData.server) {
        if (configData.server.port !== undefined) this.server.port = configData.server.port;
      }

      if (configData.promptOptimize) {
        if (configData.promptOptimize.baseUrl) this.promptOptimize.baseUrl = configData.promptOptimize.baseUrl;
        if (configData.promptOptimize.apiKey !== undefined) this.promptOptimize.apiKey = configData.promptOptimize.apiKey;
        if (configData.promptOptimize.model) this.promptOptimize.model = configData.promptOptimize.model;
        if (configData.promptOptimize.mode) this.promptOptimize.mode = configData.promptOptimize.mode;
        if (configData.promptOptimize.enableWebSearch !== undefined) this.promptOptimize.enableWebSearch = configData.promptOptimize.enableWebSearch;
        if (configData.promptOptimize.systemPrompt) this.promptOptimize.systemPrompt = configData.promptOptimize.systemPrompt;
        if (configData.promptOptimize.provider) this.promptOptimize.provider = configData.promptOptimize.provider;
        if (configData.promptOptimize.deepseekApiKey !== undefined) this.promptOptimize.deepseekApiKey = configData.promptOptimize.deepseekApiKey;
        if (configData.promptOptimize.deepseekModel) this.promptOptimize.deepseekModel = configData.promptOptimize.deepseekModel;
        if (configData.promptOptimize.thinkingEnabled !== undefined) this.promptOptimize.thinkingEnabled = configData.promptOptimize.thinkingEnabled;
        if (configData.promptOptimize.reasoningEffort) this.promptOptimize.reasoningEffort = configData.promptOptimize.reasoningEffort;
        if (configData.promptOptimize.xiaomiApiKey !== undefined) this.promptOptimize.xiaomiApiKey = configData.promptOptimize.xiaomiApiKey;
        if (configData.promptOptimize.xiaomiModel) this.promptOptimize.xiaomiModel = configData.promptOptimize.xiaomiModel;
        if (configData.promptOptimize.xiaomiThinkingEnabled !== undefined) this.promptOptimize.xiaomiThinkingEnabled = configData.promptOptimize.xiaomiThinkingEnabled;
        if (configData.promptOptimize.xiaomiEnableWebSearch !== undefined) this.promptOptimize.xiaomiEnableWebSearch = configData.promptOptimize.xiaomiEnableWebSearch;
        if (configData.promptOptimize.volcengineBaseUrl) this.promptOptimize.volcengineBaseUrl = configData.promptOptimize.volcengineBaseUrl;
        if (configData.promptOptimize.volcengineApiKey !== undefined) this.promptOptimize.volcengineApiKey = configData.promptOptimize.volcengineApiKey;
        if (configData.promptOptimize.volcengineModel) this.promptOptimize.volcengineModel = configData.promptOptimize.volcengineModel;
        if (configData.promptOptimize.systemPrompts !== undefined) {
          this.promptOptimize.systemPrompts = Array.isArray(configData.promptOptimize.systemPrompts) && configData.promptOptimize.systemPrompts.length > 0
            ? configData.promptOptimize.systemPrompts
            : [...defaultConfig.promptOptimize.systemPrompts];
        }
        if (configData.promptOptimize.selectedSystemPromptId !== undefined) {
          this.promptOptimize.selectedSystemPromptId = configData.promptOptimize.selectedSystemPromptId;
        }
      }

      if (configData.falApi) {
        if (configData.falApi.baseUrl !== undefined) this.falApi.baseUrl = configData.falApi.baseUrl;
        if (configData.falApi.apiKey !== undefined) this.falApi.apiKey = configData.falApi.apiKey;
        if (configData.falApi.falModels !== undefined) {
          this.falApi.falModels = Array.isArray(configData.falApi.falModels) && configData.falApi.falModels.length > 0
            ? configData.falApi.falModels
            : [...defaultConfig.falApi.falModels];
        }
      }

      if (configData.gptsapiApi) {
        if (configData.gptsapiApi.baseUrl) this.gptsapiApi.baseUrl = configData.gptsapiApi.baseUrl;
        if (configData.gptsapiApi.apiKey !== undefined) this.gptsapiApi.apiKey = configData.gptsapiApi.apiKey;
      }

      // APIYI 本地配置同步：与 saveConfig 写法对称
      if (configData.apiyiApi) {
        if (configData.apiyiApi.baseUrl) this.apiyiApi.baseUrl = configData.apiyiApi.baseUrl;
        if (configData.apiyiApi.apiKey !== undefined) this.apiyiApi.apiKey = configData.apiyiApi.apiKey;
        if (configData.apiyiApi.imageModels !== undefined) {
          this.apiyiApi.imageModels = Array.isArray(configData.apiyiApi.imageModels) && configData.apiyiApi.imageModels.length > 0
            ? configData.apiyiApi.imageModels
            : [...defaultConfig.apiyiApi.imageModels];
        }
        // accessToken 透传：undefined 时保留旧值
        if (configData.apiyiApi.accessToken !== undefined) {
          this.apiyiApi.accessToken = configData.apiyiApi.accessToken;
        }
      }

      if (configData.fileUpload) {
        if (configData.fileUpload.baseUrl) this.fileUpload.baseUrl = configData.fileUpload.baseUrl;
        if (configData.fileUpload.apiKey !== undefined) this.fileUpload.apiKey = configData.fileUpload.apiKey;
      }

      if (configData.socialCopyApi) {
        if (configData.socialCopyApi.provider !== undefined) this.socialCopyApi.provider = configData.socialCopyApi.provider || 'openai';
        if (configData.socialCopyApi.baseUrl !== undefined) this.socialCopyApi.baseUrl = configData.socialCopyApi.baseUrl;
        if (configData.socialCopyApi.apiKey !== undefined) this.socialCopyApi.apiKey = configData.socialCopyApi.apiKey;
        if (configData.socialCopyApi.model !== undefined) this.socialCopyApi.model = configData.socialCopyApi.model;
        if (configData.socialCopyApi.volcengineBaseUrl !== undefined) this.socialCopyApi.volcengineBaseUrl = configData.socialCopyApi.volcengineBaseUrl || defaultConfig.socialCopyApi.volcengineBaseUrl;
        if (configData.socialCopyApi.volcengineApiKey !== undefined) this.socialCopyApi.volcengineApiKey = configData.socialCopyApi.volcengineApiKey;
        if (configData.socialCopyApi.volcengineModel !== undefined) this.socialCopyApi.volcengineModel = configData.socialCopyApi.volcengineModel || defaultConfig.socialCopyApi.volcengineModel;
        if (configData.socialCopyApi.systemPrompt !== undefined) this.socialCopyApi.systemPrompt = configData.socialCopyApi.systemPrompt;
      }

      if (configData.promptTransform) {
        this.promptTransform = normalizePromptTransform(configData.promptTransform);
      }

      if (configData.topazGigapixel) {
        const tg = configData.topazGigapixel;
        if (tg.exePath !== undefined) this.topazGigapixel.exePath = tg.exePath;
        if (tg.useSystemCommand !== undefined) this.topazGigapixel.useSystemCommand = tg.useSystemCommand;
        if (tg.defaultScale !== undefined) this.topazGigapixel.defaultScale = tg.defaultScale;
        if (tg.defaultModel !== undefined) this.topazGigapixel.defaultModel = tg.defaultModel;
        if (tg.defaultEnabled !== undefined) this.topazGigapixel.defaultEnabled = tg.defaultEnabled;
        if (tg.defaultSharpen !== undefined) this.topazGigapixel.defaultSharpen = tg.defaultSharpen;
        if (tg.defaultDenoise !== undefined) this.topazGigapixel.defaultDenoise = tg.defaultDenoise;
        if (tg.defaultCompression !== undefined) this.topazGigapixel.defaultCompression = tg.defaultCompression;
        if (tg.defaultFr !== undefined) this.topazGigapixel.defaultFr = tg.defaultFr;
        if (tg.defaultPreDownscaling !== undefined) this.topazGigapixel.defaultPreDownscaling = tg.defaultPreDownscaling;
        if (tg.maxParallel !== undefined) this.topazGigapixel.maxParallel = tg.maxParallel;
        if (tg.timeout !== undefined) this.topazGigapixel.timeout = tg.timeout;
        if (tg.descriptionVisibility !== undefined) {
          this.topazGigapixel.descriptionVisibility = { ...this.topazGigapixel.descriptionVisibility, ...tg.descriptionVisibility };
        }
      }

      if (configData.gigapixelDescVisibility) {
        this.topazGigapixel.descriptionVisibility = { ...this.topazGigapixel.descriptionVisibility, ...configData.gigapixelDescVisibility };
      }

      if (configData.editPromptSnippets) {
        if (Array.isArray(configData.editPromptSnippets.snippets)) {
          this.editPromptSnippets.snippets = configData.editPromptSnippets.snippets;
        }
        if (configData.editPromptSnippets.selectedSnippetId !== undefined) {
          this.editPromptSnippets.selectedSnippetId = configData.editPromptSnippets.selectedSnippetId;
        }
      }

      // 制作人列表：与 saveConfig 写法对称；空数组时回退到默认 5 项
      if (configData.creatorOptions) {
        if (Array.isArray(configData.creatorOptions.options)) {
          this.creatorOptions.options = configData.creatorOptions.options.length > 0
            ? configData.creatorOptions.options.map(o => String(o))
            : [...defaultConfig.creatorOptions.options];
        }
      }

      // T8 余额相关字段已合并到 imageApi 中（balanceToken/balanceUserId/balanceRefreshIntervalMinutes），
      // 上面 imageApi 分支已统一处理，此处不再单独维护 userBalance

      this.saveToStorage();
    },

    applyConfig(configData) {
      const normalized = {
        version: configData?.version || defaultConfig.version,
        imageApi: {
          ...defaultConfig.imageApi,
          ...(configData?.imageApi || {})
        },
        server: {
          ...defaultConfig.server,
          ...(configData?.server || {})
        },
        promptOptimize: {
          ...defaultConfig.promptOptimize,
          ...(configData?.promptOptimize || {}),
          provider: (configData?.promptOptimize?.provider || defaultConfig.promptOptimize.provider),
          deepseekApiKey: (configData?.promptOptimize?.deepseekApiKey !== undefined ? configData.promptOptimize.deepseekApiKey : defaultConfig.promptOptimize.deepseekApiKey),
          deepseekModel: (configData?.promptOptimize?.deepseekModel || defaultConfig.promptOptimize.deepseekModel),
          thinkingEnabled: (configData?.promptOptimize?.thinkingEnabled !== undefined ? configData.promptOptimize.thinkingEnabled : defaultConfig.promptOptimize.thinkingEnabled),
          reasoningEffort: (configData?.promptOptimize?.reasoningEffort || defaultConfig.promptOptimize.reasoningEffort),
          systemPrompts: (configData?.promptOptimize?.systemPrompts !== undefined && Array.isArray(configData.promptOptimize.systemPrompts) && configData.promptOptimize.systemPrompts.length > 0
            ? configData.promptOptimize.systemPrompts
            : [...defaultConfig.promptOptimize.systemPrompts]),
          selectedSystemPromptId: (configData?.promptOptimize?.selectedSystemPromptId !== undefined ? configData.promptOptimize.selectedSystemPromptId : defaultConfig.promptOptimize.selectedSystemPromptId)
        },
        falApi: {
          ...defaultConfig.falApi,
          ...(configData?.falApi || {})
        },
        gptsapiApi: {
          ...defaultConfig.gptsapiApi,
          ...(configData?.gptsapiApi || {})
        },
        // APIYI 配置归一化：与 gptsapiApi 写法一致，缺失时用默认补齐
        apiyiApi: {
          ...defaultConfig.apiyiApi,
          ...(configData?.apiyiApi || {})
        },
        fileUpload: {
          ...defaultConfig.fileUpload,
          ...(configData?.fileUpload || {})
        },
        socialCopyApi: {
          ...defaultConfig.socialCopyApi,
          ...(configData?.socialCopyApi || {})
        },
        promptTransform: normalizePromptTransform(configData?.promptTransform || defaultConfig.promptTransform),
        topazGigapixel: {
          ...defaultConfig.topazGigapixel,
          ...(configData?.topazGigapixel || {}),
          descriptionVisibility: {
            ...defaultConfig.topazGigapixel.descriptionVisibility,
            ...(configData?.topazGigapixel?.descriptionVisibility || {}),
            ...(configData?.gigapixelDescVisibility || {})
          }
        },
        // 编辑指令预设片段：缺失时退化为默认值空数组，避免前端引用 undefined
        editPromptSnippets: {
          snippets: Array.isArray(configData?.editPromptSnippets?.snippets)
            ? configData.editPromptSnippets.snippets
            : [...defaultConfig.editPromptSnippets.snippets],
          selectedSnippetId: (configData?.editPromptSnippets?.selectedSnippetId !== undefined
            ? configData.editPromptSnippets.selectedSnippetId
            : defaultConfig.editPromptSnippets.selectedSnippetId)
        },
        // 制作人列表：缺失时回退到默认 5 项，确保生图/编辑页下拉有值可用
        creatorOptions: {
          options: Array.isArray(configData?.creatorOptions?.options) && configData.creatorOptions.options.length > 0
            ? configData.creatorOptions.options.map(o => String(o))
            : [...defaultConfig.creatorOptions.options]
        },
        // 图像生成页「制作人」筛选持久化值：缺省时回退到空串（全部制作人）
        imageLibraryCreatorFilter: {
          selectedCreator: String(configData?.imageLibraryCreatorFilter?.selectedCreator || '')
        }
        // T8 余额字段（balanceToken/balanceUserId/balanceRefreshIntervalMinutes）已合并到 imageApi 中，
        // 不再单独维护 userBalance 块
      };

      this.version = Math.max(normalized.version, defaultConfig.version);
      this.imageApi.baseUrl = normalized.imageApi.baseUrl;
      this.imageApi.apiKey = normalized.imageApi.apiKey;
      this.imageApi.isAsync = normalized.imageApi.isAsync !== undefined ? normalized.imageApi.isAsync : false;
      this.imageApi.imageModels = Array.isArray(normalized.imageApi.imageModels) && normalized.imageApi.imageModels.length > 0
        ? normalized.imageApi.imageModels
        : [...defaultConfig.imageApi.imageModels];
      // T8 余额字段（与生图共用 baseUrl）：Token / 用户 ID / 刷新间隔
      // 字段缺失时保留空字符串 / 5 分钟兜底，避免初始化时显示 undefined
      this.imageApi.balanceToken = normalized.imageApi.balanceToken !== undefined ? normalized.imageApi.balanceToken : '';
      this.imageApi.balanceUserId = normalized.imageApi.balanceUserId !== undefined ? normalized.imageApi.balanceUserId : '';
      const balanceMinutes = Number(normalized.imageApi.balanceRefreshIntervalMinutes);
      this.imageApi.balanceRefreshIntervalMinutes = Number.isFinite(balanceMinutes) && balanceMinutes >= 1 ? balanceMinutes : 5;
      this.server.port = normalized.server.port || defaultConfig.server.port;
      this.promptOptimize.baseUrl = normalized.promptOptimize.baseUrl;
      this.promptOptimize.apiKey = normalized.promptOptimize.apiKey;
      this.promptOptimize.model = normalized.promptOptimize.model;
      this.promptOptimize.mode = normalized.promptOptimize.mode;
      this.promptOptimize.enableWebSearch = normalized.promptOptimize.enableWebSearch;
      this.promptOptimize.systemPrompt = normalized.promptOptimize.systemPrompt;
      this.promptOptimize.provider = normalized.promptOptimize.provider || 'openai';
      this.promptOptimize.deepseekApiKey = normalized.promptOptimize.deepseekApiKey || '';
      this.promptOptimize.deepseekModel = normalized.promptOptimize.deepseekModel || 'deepseek-v4-pro';
      this.promptOptimize.thinkingEnabled = normalized.promptOptimize.thinkingEnabled || false;
      this.promptOptimize.reasoningEffort = normalized.promptOptimize.reasoningEffort || 'high';
      this.promptOptimize.xiaomiApiKey = normalized.promptOptimize.xiaomiApiKey || '';
      this.promptOptimize.xiaomiModel = normalized.promptOptimize.xiaomiModel || 'mimo-v2.5-pro';
      this.promptOptimize.xiaomiThinkingEnabled = normalized.promptOptimize.xiaomiThinkingEnabled || false;
      this.promptOptimize.xiaomiEnableWebSearch = normalized.promptOptimize.xiaomiEnableWebSearch || false;
      this.promptOptimize.volcengineBaseUrl = normalized.promptOptimize.volcengineBaseUrl || 'https://ark.cn-beijing.volces.com/api/v3/responses';
      this.promptOptimize.volcengineApiKey = normalized.promptOptimize.volcengineApiKey || '';
      this.promptOptimize.volcengineModel = normalized.promptOptimize.volcengineModel || 'doubao-seed-2-1-pro-260628';
      this.promptOptimize.systemPrompts = Array.isArray(normalized.promptOptimize.systemPrompts) && normalized.promptOptimize.systemPrompts.length > 0
        ? normalized.promptOptimize.systemPrompts
        : [...defaultConfig.promptOptimize.systemPrompts];
      this.promptOptimize.selectedSystemPromptId = normalized.promptOptimize.selectedSystemPromptId || 'default';
      this.falApi.baseUrl = normalized.falApi.baseUrl;
      this.falApi.apiKey = normalized.falApi.apiKey;
      this.falApi.falModels = Array.isArray(normalized.falApi.falModels) && normalized.falApi.falModels.length > 0
        ? normalized.falApi.falModels
        : [...defaultConfig.falApi.falModels];
      this.gptsapiApi.baseUrl = normalized.gptsapiApi.baseUrl;
      this.gptsapiApi.apiKey = normalized.gptsapiApi.apiKey;
      // APIYI 字段赋值：缺失时回退到默认 baseUrl 与默认模型列表
      this.apiyiApi.baseUrl = normalized.apiyiApi.baseUrl || defaultConfig.apiyiApi.baseUrl;
      this.apiyiApi.apiKey = normalized.apiyiApi.apiKey || '';
      this.apiyiApi.imageModels = Array.isArray(normalized.apiyiApi.imageModels) && normalized.apiyiApi.imageModels.length > 0
        ? normalized.apiyiApi.imageModels
        : [...defaultConfig.apiyiApi.imageModels];
      this.apiyiApi.accessToken = normalized.apiyiApi.accessToken !== undefined
        ? normalized.apiyiApi.accessToken
        : defaultConfig.apiyiApi.accessToken;
      this.fileUpload.baseUrl = normalized.fileUpload.baseUrl;
      this.fileUpload.apiKey = normalized.fileUpload.apiKey;
      this.socialCopyApi.provider = normalized.socialCopyApi.provider || 'openai';
      this.socialCopyApi.baseUrl = normalized.socialCopyApi.baseUrl;
      this.socialCopyApi.apiKey = normalized.socialCopyApi.apiKey;
      this.socialCopyApi.model = normalized.socialCopyApi.model;
      this.socialCopyApi.volcengineBaseUrl = normalized.socialCopyApi.volcengineBaseUrl || defaultConfig.socialCopyApi.volcengineBaseUrl;
      this.socialCopyApi.volcengineApiKey = normalized.socialCopyApi.volcengineApiKey || '';
      this.socialCopyApi.volcengineModel = normalized.socialCopyApi.volcengineModel || defaultConfig.socialCopyApi.volcengineModel;
      this.socialCopyApi.systemPrompt = normalized.socialCopyApi.systemPrompt;
      this.promptTransform = normalizePromptTransform(normalized.promptTransform);
      this.topazGigapixel.exePath = normalized.topazGigapixel.exePath || defaultConfig.topazGigapixel.exePath;
      this.topazGigapixel.useSystemCommand = normalized.topazGigapixel.useSystemCommand !== undefined ? normalized.topazGigapixel.useSystemCommand : false;
      this.topazGigapixel.defaultScale = normalized.topazGigapixel.defaultScale || defaultConfig.topazGigapixel.defaultScale;
      this.topazGigapixel.defaultModel = normalized.topazGigapixel.defaultModel || defaultConfig.topazGigapixel.defaultModel;
      this.topazGigapixel.defaultEnabled = normalized.topazGigapixel.defaultEnabled !== undefined ? normalized.topazGigapixel.defaultEnabled : true;
      this.topazGigapixel.defaultSharpen = normalized.topazGigapixel.defaultSharpen !== undefined ? normalized.topazGigapixel.defaultSharpen : 0;
      this.topazGigapixel.defaultDenoise = normalized.topazGigapixel.defaultDenoise !== undefined ? normalized.topazGigapixel.defaultDenoise : 0;
      this.topazGigapixel.defaultCompression = normalized.topazGigapixel.defaultCompression !== undefined ? normalized.topazGigapixel.defaultCompression : 67;
      this.topazGigapixel.defaultFr = normalized.topazGigapixel.defaultFr !== undefined ? normalized.topazGigapixel.defaultFr : 50;
      this.topazGigapixel.defaultPreDownscaling = normalized.topazGigapixel.defaultPreDownscaling !== undefined ? normalized.topazGigapixel.defaultPreDownscaling : 75;
      this.topazGigapixel.maxParallel = normalized.topazGigapixel.maxParallel !== undefined ? normalized.topazGigapixel.maxParallel : 1;
      this.topazGigapixel.timeout = normalized.topazGigapixel.timeout !== undefined ? normalized.topazGigapixel.timeout : 600;
      this.topazGigapixel.descriptionVisibility = { ...defaultConfig.topazGigapixel.descriptionVisibility, ...normalized.topazGigapixel.descriptionVisibility };

      this.editPromptSnippets.snippets = Array.isArray(normalized.editPromptSnippets.snippets)
        ? normalized.editPromptSnippets.snippets
        : [];
      this.editPromptSnippets.selectedSnippetId = normalized.editPromptSnippets.selectedSnippetId || null;
      // 制作人列表：缺失或为空时回退到默认 5 项
      this.creatorOptions.options = Array.isArray(normalized.creatorOptions.options) && normalized.creatorOptions.options.length > 0
        ? normalized.creatorOptions.options
        : [...defaultConfig.creatorOptions.options];
      // 图像生成页「制作人」筛选持久化值：缺省时回退到空串（全部制作人）
      this.imageLibraryCreatorFilter.selectedCreator = String(normalized.imageLibraryCreatorFilter?.selectedCreator || '');
      // T8 余额相关字段已合并到 imageApi 中，上面 imageApi 分支已统一处理
    },

    // 图像生成页「制作人」筛选持久化 action
    // 功能描述：
    //   切换图像库制作人筛选时立即调用，同步本地 state + 持久化到后端 app_config 表
    //   即使后端保存失败也不抛错（仅 console.error），UI 状态保持为用户所选
    // 实现逻辑：
    //   1. 同步更新 store 中 imageLibraryCreatorFilter.selectedCreator
    //   2. 调 saveConfig({ imageLibraryCreatorFilter: { selectedCreator } }) 走后端
    //   3. saveToStorage 同步刷新 localStorage
    // 失败处理：try/catch 包住，失败仅 console.error，不影响前端使用
    async setImageLibraryCreatorFilter(creator) {
      const safeCreator = creator === null || creator === undefined ? '' : String(creator);
      this.imageLibraryCreatorFilter.selectedCreator = safeCreator;
      this.saveToStorage();
      try {
        await this.saveConfig({ imageLibraryCreatorFilter: { selectedCreator: safeCreator } });
      } catch (err) {
        console.error('[ConfigStore] setImageLibraryCreatorFilter 保存失败:', err?.message || err);
      }
    },

    saveToStorage() {
      saveToStorage({
        version: this.version,
        imageApi: {
          baseUrl: this.imageApi.baseUrl,
          apiKey: this.imageApi.apiKey,
          isAsync: this.imageApi.isAsync,
          imageModels: this.imageApi.imageModels,
          // T8 余额查询字段：Token / 用户 ID / 自动刷新间隔
          balanceToken: this.imageApi.balanceToken,
          balanceUserId: this.imageApi.balanceUserId,
          balanceRefreshIntervalMinutes: this.imageApi.balanceRefreshIntervalMinutes
        },
        server: {
          port: this.server.port
        },
        promptOptimize: {
          baseUrl: this.promptOptimize.baseUrl,
          apiKey: this.promptOptimize.apiKey,
          model: this.promptOptimize.model,
          mode: this.promptOptimize.mode,
          enableWebSearch: this.promptOptimize.enableWebSearch,
          systemPrompt: this.promptOptimize.systemPrompt,
          provider: this.promptOptimize.provider,
          deepseekApiKey: this.promptOptimize.deepseekApiKey,
          deepseekModel: this.promptOptimize.deepseekModel,
          thinkingEnabled: this.promptOptimize.thinkingEnabled,
          reasoningEffort: this.promptOptimize.reasoningEffort,
          xiaomiApiKey: this.promptOptimize.xiaomiApiKey,
          xiaomiModel: this.promptOptimize.xiaomiModel,
          xiaomiThinkingEnabled: this.promptOptimize.xiaomiThinkingEnabled,
          xiaomiEnableWebSearch: this.promptOptimize.xiaomiEnableWebSearch,
          volcengineBaseUrl: this.promptOptimize.volcengineBaseUrl,
          volcengineApiKey: this.promptOptimize.volcengineApiKey,
          volcengineModel: this.promptOptimize.volcengineModel,
          systemPrompts: this.promptOptimize.systemPrompts,
          selectedSystemPromptId: this.promptOptimize.selectedSystemPromptId
        },
        falApi: {
          baseUrl: this.falApi.baseUrl,
          apiKey: this.falApi.apiKey,
          falModels: this.falApi.falModels
        },
        gptsapiApi: {
          baseUrl: this.gptsapiApi.baseUrl,
          apiKey: this.gptsapiApi.apiKey
        },
        // APIYI 完整保存：baseUrl + apiKey + imageModels + accessToken 四字段
        apiyiApi: {
          baseUrl: this.apiyiApi.baseUrl,
          apiKey: this.apiyiApi.apiKey,
          imageModels: this.apiyiApi.imageModels,
          accessToken: this.apiyiApi.accessToken
        },
        fileUpload: {
          baseUrl: this.fileUpload.baseUrl,
          apiKey: this.fileUpload.apiKey
        },
        socialCopyApi: {
          provider: this.socialCopyApi.provider,
          baseUrl: this.socialCopyApi.baseUrl,
          apiKey: this.socialCopyApi.apiKey,
          model: this.socialCopyApi.model,
          volcengineBaseUrl: this.socialCopyApi.volcengineBaseUrl,
          volcengineApiKey: this.socialCopyApi.volcengineApiKey,
          volcengineModel: this.socialCopyApi.volcengineModel,
          systemPrompt: this.socialCopyApi.systemPrompt
        },
        promptTransform: normalizePromptTransform(this.promptTransform),
        topazGigapixel: {
          exePath: this.topazGigapixel.exePath,
          useSystemCommand: this.topazGigapixel.useSystemCommand,
          defaultScale: this.topazGigapixel.defaultScale,
          defaultModel: this.topazGigapixel.defaultModel,
          defaultEnabled: this.topazGigapixel.defaultEnabled,
          defaultSharpen: this.topazGigapixel.defaultSharpen,
          defaultDenoise: this.topazGigapixel.defaultDenoise,
          defaultCompression: this.topazGigapixel.defaultCompression,
          defaultFr: this.topazGigapixel.defaultFr,
          defaultPreDownscaling: this.topazGigapixel.defaultPreDownscaling,
          maxParallel: this.topazGigapixel.maxParallel,
          timeout: this.topazGigapixel.timeout,
          descriptionVisibility: { ...this.topazGigapixel.descriptionVisibility }
        },
        // 编辑指令预设片段：snippets 数组整体保存，确保 localStorage 也能完整恢复
        editPromptSnippets: {
          snippets: this.editPromptSnippets.snippets,
          selectedSnippetId: this.editPromptSnippets.selectedSnippetId
        },
        // 制作人列表：整体保存到 localStorage
        creatorOptions: {
          options: this.creatorOptions.options
        },
        // 图像生成页「制作人」筛选持久化值：整体保存到 localStorage
        imageLibraryCreatorFilter: {
          selectedCreator: this.imageLibraryCreatorFilter.selectedCreator
        }
        // T8 余额字段已合并到 imageApi 中（balanceToken/balanceUserId/balanceRefreshIntervalMinutes），
        // 上面 imageApi 分支已统一持久化
      });
    }
  }
});
