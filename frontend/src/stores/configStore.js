import { defineStore } from 'pinia';
import { getConfig, saveConfig } from '../services/api';

const STORAGE_KEY = 'app_config';

const defaultConfig = {
  version: 5,
  imageApi: {
    baseUrl: 'https://ai.t8star.cn ',
    apiKey: '',
    isAsync: false,
    imageModels: ['gpt-image-2']
  },
  server: {
    port: 5678
  },
  promptOptimize: {
    baseUrl: 'https://ai.t8star.cn',
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
    apiKey: '',
    falModels: ['openai/gpt-image-2', 'openai/gpt-image-2/edit']
  },
  gptsapiApi: {
    baseUrl: 'https://api.gptsapi.net',
    apiKey: ''
  },
  fileUpload: {
    baseUrl: 'https://ai.t8star.cn',
    apiKey: ''
  },
  socialCopyApi: {
    baseUrl: '',
    apiKey: '',
    model: '',
    systemPrompt: ''
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
    imageApi: {
      baseUrl: defaultConfig.imageApi.baseUrl,
      apiKey: defaultConfig.imageApi.apiKey,
      isAsync: defaultConfig.imageApi.isAsync,
      imageModels: [...defaultConfig.imageApi.imageModels]
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
      systemPrompts: [...defaultConfig.promptOptimize.systemPrompts],
      selectedSystemPromptId: defaultConfig.promptOptimize.selectedSystemPromptId
    },
    falApi: {
      apiKey: defaultConfig.falApi.apiKey,
      falModels: [...defaultConfig.falApi.falModels]
    },
    gptsapiApi: {
      baseUrl: defaultConfig.gptsapiApi.baseUrl,
      apiKey: defaultConfig.gptsapiApi.apiKey
    },
    fileUpload: {
      baseUrl: defaultConfig.fileUpload.baseUrl,
      apiKey: defaultConfig.fileUpload.apiKey
    },
    socialCopyApi: {
      baseUrl: defaultConfig.socialCopyApi.baseUrl,
      apiKey: defaultConfig.socialCopyApi.apiKey,
      model: defaultConfig.socialCopyApi.model,
      systemPrompt: defaultConfig.socialCopyApi.systemPrompt
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

        if (configData.fileUpload) {
          this.fileUpload.baseUrl = configData.fileUpload.baseUrl || this.fileUpload.baseUrl;
          this.fileUpload.apiKey = configData.fileUpload.apiKey !== undefined ? configData.fileUpload.apiKey : this.fileUpload.apiKey;
        }

        if (configData.socialCopyApi) {
          this.socialCopyApi.baseUrl = configData.socialCopyApi.baseUrl !== undefined ? configData.socialCopyApi.baseUrl : this.socialCopyApi.baseUrl;
          this.socialCopyApi.apiKey = configData.socialCopyApi.apiKey !== undefined ? configData.socialCopyApi.apiKey : this.socialCopyApi.apiKey;
          this.socialCopyApi.model = configData.socialCopyApi.model !== undefined ? configData.socialCopyApi.model : this.socialCopyApi.model;
          this.socialCopyApi.systemPrompt = configData.socialCopyApi.systemPrompt !== undefined ? configData.socialCopyApi.systemPrompt : this.socialCopyApi.systemPrompt;
        }

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

      if (configData.fileUpload) {
        if (configData.fileUpload.baseUrl) this.fileUpload.baseUrl = configData.fileUpload.baseUrl;
        if (configData.fileUpload.apiKey !== undefined) this.fileUpload.apiKey = configData.fileUpload.apiKey;
      }

      if (configData.socialCopyApi) {
        if (configData.socialCopyApi.baseUrl !== undefined) this.socialCopyApi.baseUrl = configData.socialCopyApi.baseUrl;
        if (configData.socialCopyApi.apiKey !== undefined) this.socialCopyApi.apiKey = configData.socialCopyApi.apiKey;
        if (configData.socialCopyApi.model !== undefined) this.socialCopyApi.model = configData.socialCopyApi.model;
        if (configData.socialCopyApi.systemPrompt !== undefined) this.socialCopyApi.systemPrompt = configData.socialCopyApi.systemPrompt;
      }

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
        fileUpload: {
          ...defaultConfig.fileUpload,
          ...(configData?.fileUpload || {})
        },
        socialCopyApi: {
          ...defaultConfig.socialCopyApi,
          ...(configData?.socialCopyApi || {})
        }
      };

      this.version = Math.max(normalized.version, defaultConfig.version);
      this.imageApi.baseUrl = normalized.imageApi.baseUrl;
      this.imageApi.apiKey = normalized.imageApi.apiKey;
      this.imageApi.isAsync = normalized.imageApi.isAsync !== undefined ? normalized.imageApi.isAsync : false;
      this.imageApi.imageModels = Array.isArray(normalized.imageApi.imageModels) && normalized.imageApi.imageModels.length > 0
        ? normalized.imageApi.imageModels
        : [...defaultConfig.imageApi.imageModels];
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
      this.promptOptimize.systemPrompts = Array.isArray(normalized.promptOptimize.systemPrompts) && normalized.promptOptimize.systemPrompts.length > 0
        ? normalized.promptOptimize.systemPrompts
        : [...defaultConfig.promptOptimize.systemPrompts];
      this.promptOptimize.selectedSystemPromptId = normalized.promptOptimize.selectedSystemPromptId || 'default';
      this.falApi.apiKey = normalized.falApi.apiKey;
      this.falApi.falModels = Array.isArray(normalized.falApi.falModels) && normalized.falApi.falModels.length > 0
        ? normalized.falApi.falModels
        : [...defaultConfig.falApi.falModels];
      this.gptsapiApi.baseUrl = normalized.gptsapiApi.baseUrl;
      this.gptsapiApi.apiKey = normalized.gptsapiApi.apiKey;
      this.fileUpload.baseUrl = normalized.fileUpload.baseUrl;
      this.fileUpload.apiKey = normalized.fileUpload.apiKey;
      this.socialCopyApi.baseUrl = normalized.socialCopyApi.baseUrl;
      this.socialCopyApi.apiKey = normalized.socialCopyApi.apiKey;
      this.socialCopyApi.model = normalized.socialCopyApi.model;
      this.socialCopyApi.systemPrompt = normalized.socialCopyApi.systemPrompt;
    },

    saveToStorage() {
      saveToStorage({
        version: this.version,
        imageApi: {
          baseUrl: this.imageApi.baseUrl,
          apiKey: this.imageApi.apiKey,
          isAsync: this.imageApi.isAsync,
          imageModels: this.imageApi.imageModels
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
          systemPrompts: this.promptOptimize.systemPrompts,
          selectedSystemPromptId: this.promptOptimize.selectedSystemPromptId
        },
        falApi: {
          apiKey: this.falApi.apiKey,
          falModels: this.falApi.falModels
        },
        gptsapiApi: {
          baseUrl: this.gptsapiApi.baseUrl,
          apiKey: this.gptsapiApi.apiKey
        },
        fileUpload: {
          baseUrl: this.fileUpload.baseUrl,
          apiKey: this.fileUpload.apiKey
        },
        socialCopyApi: {
          baseUrl: this.socialCopyApi.baseUrl,
          apiKey: this.socialCopyApi.apiKey,
          model: this.socialCopyApi.model,
          systemPrompt: this.socialCopyApi.systemPrompt
        }
      });
    }
  }
});
