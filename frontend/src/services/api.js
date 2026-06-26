import axios from 'axios';

function createAxiosInstance() {
  const instance = axios.create({
    baseURL: '',
    timeout: 120000
  });

  instance.interceptors.response.use(
    (response) => response.data,
    (error) => {
      const message = error.response?.data?.error || error.response?.data?.message || error.message || '请求失败'
      const wrappedError = new Error(message)
      wrappedError.code = error.code
      return Promise.reject(wrappedError)
    }
  );

  return instance;
}

const api = createAxiosInstance();

// 只保留 section 中实际存在的字段，不填充默认值
// 避免部分更新时用默认值覆盖数据库中其他字段
function normalizeSection(section) {
  if (!section || typeof section !== 'object') return {};
  const result = {};
  for (const key of Object.keys(section)) {
    result[key] = section[key];
  }
  return result;
}

function normalizeConfigPayload(payload = {}) {
  const rawConfig = payload.config || payload;
  const result = { version: rawConfig.version || 2 };

  if ('imageApi' in rawConfig || 'apiBaseUrl' in rawConfig || 'apiKey' in rawConfig || 'models' in rawConfig) {
    result.imageApi = normalizeSection(rawConfig.imageApi);
    if (rawConfig.imageApi?.baseUrl !== undefined || rawConfig.apiBaseUrl !== undefined || rawConfig.api_base_url !== undefined) {
      result.imageApi.baseUrl = rawConfig.imageApi?.baseUrl ?? rawConfig.apiBaseUrl ?? rawConfig.api_base_url;
    }
    if (rawConfig.imageApi?.apiKey !== undefined || rawConfig.apiKey !== undefined || rawConfig.api_key !== undefined) {
      result.imageApi.apiKey = rawConfig.imageApi?.apiKey ?? rawConfig.apiKey ?? rawConfig.api_key;
    }
    if (rawConfig.imageApi?.isAsync !== undefined) {
      result.imageApi.isAsync = rawConfig.imageApi.isAsync;
    }
    if (Array.isArray(rawConfig.imageApi?.imageModels) && rawConfig.imageApi.imageModels.length > 0) {
      result.imageApi.imageModels = rawConfig.imageApi.imageModels;
    }
    // T8 余额查询字段透传：与 imageApi.baseUrl 共用 Base URL
    // 余额字段名（quota）和换算除数（500000）已硬编码在后端，不暴露给用户
    if (rawConfig.imageApi?.balanceToken !== undefined) {
      result.imageApi.balanceToken = rawConfig.imageApi.balanceToken;
    }
    if (rawConfig.imageApi?.balanceUserId !== undefined) {
      result.imageApi.balanceUserId = rawConfig.imageApi.balanceUserId;
    }
    if (rawConfig.imageApi?.balanceRefreshIntervalMinutes !== undefined) {
      result.imageApi.balanceRefreshIntervalMinutes = rawConfig.imageApi.balanceRefreshIntervalMinutes;
    }
  }


  if ('server' in rawConfig || 'port' in rawConfig) {
    result.server = normalizeSection(rawConfig.server);
    if (rawConfig.server?.port !== undefined || rawConfig.port !== undefined) {
      result.server.port = rawConfig.server?.port ?? rawConfig.port;
    }
  }

  if ('promptOptimize' in rawConfig) {
    result.promptOptimize = normalizeSection(rawConfig.promptOptimize);
  }

  if ('promptTransform' in rawConfig) {
    result.promptTransform = normalizeSection(rawConfig.promptTransform);
  }

  if ('falApi' in rawConfig) {
    result.falApi = normalizeSection(rawConfig.falApi);
    if (rawConfig.falApi?.baseUrl !== undefined) {
      result.falApi.baseUrl = rawConfig.falApi.baseUrl;
    }
    if (rawConfig.falApi?.apiKey !== undefined) {
      result.falApi.apiKey = rawConfig.falApi.apiKey;
    }
    if (Array.isArray(rawConfig.falApi?.falModels) && rawConfig.falApi.falModels.length > 0) {
      result.falApi.falModels = rawConfig.falApi.falModels;
    }
  }

  if ('gptsapiApi' in rawConfig) {
    result.gptsapiApi = normalizeSection(rawConfig.gptsapiApi);
    if (rawConfig.gptsapiApi?.baseUrl !== undefined) {
      result.gptsapiApi.baseUrl = rawConfig.gptsapiApi.baseUrl;
    }
    if (rawConfig.gptsapiApi?.apiKey !== undefined) {
      result.gptsapiApi.apiKey = rawConfig.gptsapiApi.apiKey;
    }
  }

  // APIYI 端口配置：baseUrl + apiKey + imageModels 三字段透传
  // 缺失这一项时 configStore.saveConfig({ apiyiApi: {...} }) 的 payload 会被归一化成空对象，
  // 后端 POST /api/config 永远收不到 apiyiApi，数据库永远写不进去
  if ('apiyiApi' in rawConfig) {
    result.apiyiApi = normalizeSection(rawConfig.apiyiApi);
    if (rawConfig.apiyiApi?.baseUrl !== undefined) {
      result.apiyiApi.baseUrl = rawConfig.apiyiApi.baseUrl;
    }
    if (rawConfig.apiyiApi?.apiKey !== undefined) {
      result.apiyiApi.apiKey = rawConfig.apiyiApi.apiKey;
    }
    if (Array.isArray(rawConfig.apiyiApi?.imageModels) && rawConfig.apiyiApi.imageModels.length > 0) {
      result.apiyiApi.imageModels = rawConfig.apiyiApi.imageModels;
    }
    if (rawConfig.apiyiApi?.accessToken !== undefined) {
      result.apiyiApi.accessToken = rawConfig.apiyiApi.accessToken;
    }
  }

  if ('fileUpload' in rawConfig) {
    result.fileUpload = normalizeSection(rawConfig.fileUpload);
    if (rawConfig.fileUpload?.baseUrl !== undefined) {
      result.fileUpload.baseUrl = rawConfig.fileUpload.baseUrl;
    }
    if (rawConfig.fileUpload?.apiKey !== undefined) {
      result.fileUpload.apiKey = rawConfig.fileUpload.apiKey;
    }
  }

  if ('socialCopyApi' in rawConfig) {
    result.socialCopyApi = normalizeSection(rawConfig.socialCopyApi);
    if (rawConfig.socialCopyApi?.baseUrl !== undefined) {
      result.socialCopyApi.baseUrl = rawConfig.socialCopyApi.baseUrl;
    }
    if (rawConfig.socialCopyApi?.apiKey !== undefined) {
      result.socialCopyApi.apiKey = rawConfig.socialCopyApi.apiKey;
    }
    if (rawConfig.socialCopyApi?.model !== undefined) {
      result.socialCopyApi.model = rawConfig.socialCopyApi.model;
    }
    if (rawConfig.socialCopyApi?.systemPrompt !== undefined) {
      result.socialCopyApi.systemPrompt = rawConfig.socialCopyApi.systemPrompt;
    }
  }

  if ('topazGigapixel' in rawConfig) {
    result.topazGigapixel = normalizeSection(rawConfig.topazGigapixel);
  }

  if ('gigapixelDescVisibility' in rawConfig) {
    result.gigapixelDescVisibility = normalizeSection(rawConfig.gigapixelDescVisibility);
  }

  // 编辑指令预设片段：snippets 数组结构直接透传，不做归一化处理
  if ('editPromptSnippets' in rawConfig) {
    result.editPromptSnippets = normalizeSection(rawConfig.editPromptSnippets);
  }

  // 制作人列表：设置页维护的下拉选项，必须透传到后端 creator_options 配置
  if ('creatorOptions' in rawConfig) {
    result.creatorOptions = normalizeSection(rawConfig.creatorOptions);
    if (Array.isArray(rawConfig.creatorOptions?.options)) {
      result.creatorOptions.options = rawConfig.creatorOptions.options.map((item) => String(item));
    }
  }

  // 图像生成页「制作人」筛选持久化值：与 editPromptSnippets 写法对称
  // selectedCreator 强制转 String，避免后端收到 null/Number 类型造成解析异常
  if ('imageLibraryCreatorFilter' in rawConfig) {
    result.imageLibraryCreatorFilter = normalizeSection(rawConfig.imageLibraryCreatorFilter);
    if (rawConfig.imageLibraryCreatorFilter?.selectedCreator !== undefined) {
      const rawValue = rawConfig.imageLibraryCreatorFilter.selectedCreator;
      result.imageLibraryCreatorFilter.selectedCreator = rawValue === null || rawValue === undefined ? '' : String(rawValue);
    }
  }

  // T8 余额字段已合并到 imageApi 中（balanceToken/balanceUserId/balanceRefreshIntervalMinutes），
  // 不再单独透传 userBalance 块

  return result;
}

export async function getConfig() {
  return api.get('/api/config');
}

export async function saveConfig(config) {
  return api.post('/api/config', normalizeConfigPayload(config));
}

export async function generateImage(data) {
  return api.post('/api/images/generations', data, { timeout: 600000 });
}

export async function editImage(formData, asyncMode = false) {
  const url = asyncMode ? '/api/images/edits?async=true' : '/api/images/edits'
  return api.post(url, formData, { timeout: 600000 })
}

export async function getImages(params = {}) {
  const response = await api.get('/api/images', { params });
  return response.images || [];
}

export async function repairThumbnailsToJpg() {
  return api.post('/api/images/thumbnails/repair-jpg', {});
}

export async function getImageById(imageId) {
  return api.get(`/api/images/${imageId}`);
}

export async function deleteImage(imageId) {
  return api.delete(`/api/images/${imageId}`);
}

export async function updateImage(imageId, data) {
  return api.put(`/api/images/${imageId}`, data);
}

export async function getFolders() {
  return api.get('/api/folders');
}

export async function createFolder(name) {
  return api.post('/api/folders', { name });
}

export async function deleteFolder(folderId) {
  return api.delete(`/api/folders/${folderId}`);
}

export async function getFolderImages(folderId) {
  return api.get(`/api/folders/${folderId}/images`);
}

// 获取「未分配」虚拟文件夹下的图片列表
// 对应后端 /api/folders/unassigned/images 接口
// 返回的字段结构与 getFolderImages 保持一致
export async function getUnassignedImages() {
  return api.get('/api/folders/unassigned/images');
}

export async function moveImageToFolder(imageId, folderPath) {
  return api.put(`/api/images/${imageId}/folder`, { folderPath });
}

export async function generateAsync(data) {
  return api.post('/api/images/generations', { ...data, async: true });
}

export async function queryTask(taskId) {
  return api.get(`/api/images/tasks/${taskId}`);
}

export async function getEditFolder(folderId) {
  return api.get(`/api/images/edit/${folderId}`);
}

export async function createEditFolder(images) {
  return api.post('/api/images/edit', { images });
}

export async function deleteEditFolder(folderId) {
  return api.delete(`/api/images/edit/${folderId}`);
}

export async function uploadImage(file) {
  const formData = new FormData();
  formData.append('image', file);
  return api.post('/api/images/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
}

// 下载远程图片到本地
export async function downloadImage(imageUrl) {
  return api.post('/api/images/download', { image_url: imageUrl });
}

// 重命名图片
export async function renameImage(imageId, title) {
  return api.put(`/api/images/${imageId}/rename`, { title });
}

// 刷新图片（重新下载或更新URL）
export async function refreshImage(imageId, imageUrl) {
  return api.post(`/api/images/${imageId}/refresh`, { image_url: imageUrl });
}

// GPTsAPI 重试：通过查询 URL 重新获取结果
export async function gptsapiRetry(data) {
  return api.post('/api/images/gptsapi/retry', data);
}

// 移动图片到回收站（软删除）
export async function moveToRecycleBin(imageId, sourcePath) {
  return api.post(`/api/recycle/move/${imageId}`, { source_path: sourcePath });
}


export async function getImageAssets(imageId) {
  return api.get(`/api/images/${imageId}/assets`);
}

export async function deleteImageAssets(imageId) {
  return api.delete(`/api/images/${imageId}/assets`);
}

export async function getRecycleBin() {
  return api.get('/api/recycle/list');
}

export async function getRecycleBinImages() {
  return api.get('/api/recycle/images');
}

export async function getRecycleBinCount() {
  return api.get('/api/recycle/image-count');
}

export async function restoreFromRecycleBin(imageId) {
  return api.post(`/api/recycle/restore/${imageId}`, {});
}

export async function permanentDelete(imageId) {
  return api.delete(`/api/recycle/${imageId}`);
}

export async function clearRecycleBin() {
  return api.delete('/api/recycle/empty');
}

export async function getMaterials() {
  return api.get('/api/materials');
}

export async function addMaterial(name, folderPath) {
  return api.post('/api/materials', { name, folderPath });
}

export async function deleteMaterial(materialId) {
  return api.delete(`/api/materials/${materialId}`);
}

export async function updateMaterial(materialId, data) {
  return api.put(`/api/materials/${materialId}`, data);
}


export async function optimizePrompt(prompt) {
  return api.post('/api/prompt/optimize', { prompt }, { timeout: 0 });
}

export async function optimizePromptTransform(prompt, mediaType, systemPromptId = '') {
  return api.post('/api/prompt/transform-optimize', { prompt, mediaType, systemPromptId }, { timeout: 0 });
}

// 保存编辑结果到本地（edit_folders）
export async function saveEditResult(data) {
  return api.post('/api/edit-images/save', data);
}

// 保存编辑结果到素材库
export async function saveEditToLibrary(data) {
  return api.post('/api/edit-images/save-to-library', data);
}

export { api };

// 文案管理 API
export async function getCopyFiles() {
  return api.get('/api/copy/files');
}

// 获取所有当前被锁的文件 key 列表（用于侧边栏"正在编辑"徽章展示）
// 实现逻辑：调用后端 /api/copy/lock/all，返回 { success, locked_files: [...] }
export async function getLockedFiles() {
  return api.get('/api/copy/lock/all');
}

export async function saveCopyCountryNote(country, note) {
  return api.post('/api/copy/country-note', { country, note });
}

export async function getCopyContent(path) {
  return api.get('/api/copy/content', { params: { path } });
}

export async function saveCopyContent(path, content, token) {
  // 新增 token 形参：用于后端协作锁校验
  return api.post('/api/copy/content', { path, content, token });
}

export async function createCopyBoard(country) {
  return api.post('/api/copy/boards', { country });
}

export async function getCopyBoardContent(path) {
  return api.get('/api/copy/boards/content', { params: { path } });
}

export async function saveCopyBoardContent(path, cards, token) {
  // 新增 token 形参：用于后端协作锁校验
  return api.post('/api/copy/boards/content', { path, cards, token });
}

export async function deleteCopyBoard(path) {
  return api.delete('/api/copy/boards/content', { params: { path } });
}

export async function renameCopyBoard(path, name) {
  return api.post('/api/copy/boards/rename', { path, name });
}

// 上传HTML文案文件
export async function uploadCopyHtml(formData) {
  return api.post('/api/copy/upload-html', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
}

// 确认覆盖上传HTML文件
export async function confirmUploadCopyHtml(formData) {
  return api.post('/api/copy/upload-html-confirm', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
}

// 预备成品图片 API
export async function getPreparationList() {
  return api.get('/api/preparation/list');
}

export async function updatePreparationItem(itemId, data) {
  return api.put(`/api/preparation/update/${itemId}`, data);
}

export async function batchUpdatePreparationItems(ids, updates) {
  return api.post('/api/preparation/batch-update', { ids, updates });
}

export async function renamePreparationItem(itemId, newFilename) {
  return api.put(`/api/preparation/rename/${itemId}`, { new_filename: newFilename });
}

export async function syncPreparation() {
  return api.post('/api/preparation/sync');
}

export async function deletePreparationItem(itemId) {
  return api.delete(`/api/preparation/delete/${itemId}`);
}

export async function generateSocialCopy(itemId) {
  return api.post('/api/preparation/generate-social-copy', { item_id: itemId });
}

export async function openPreparationFolder(itemId) {
  return api.get(`/api/preparation/open-folder/${itemId}`);
}

export async function getPublishGroups() {
  return api.get('/api/preparation/publish-groups');
}

export async function createPublishGroup(publishDate) {
  return api.post('/api/preparation/publish-groups', { publish_date: publishDate });
}

export async function movePublishGroup(itemId, publishDate) {
  return api.post('/api/preparation/move-publish-group', { item_id: itemId, publish_date: publishDate });
}

export async function compressPublishGroup(publishDate) {
  return api.post('/api/preparation/compress-publish-group', { publish_date: publishDate }, { timeout: 600000 });
}

// Topaz Gigapixel AI 异步放大相关 API
// 检查本机 Topaz Gigapixel AI 是否可用（用于前端启动时探测）
export async function checkGigapixelAvailable() {
  return api.get('/api/gigapixel/check');
}

// 上传本地图片文件到服务器磁盘（multipart/form-data）
// 返回：{ success, uploaded_path, filename }
export async function uploadGigapixelFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  // 使用原始 axios（不带 response.data 拦截器），因为需要完整响应
  return axios.post('/api/gigapixel/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  }).then(r => r.data)
}

// 提交异步放大任务（返回 task_id，前端轮询）
export async function submitGigapixelUpscale(payload) {
  return api.post('/api/gigapixel/upscale', payload);
}

// 查询单个 gigapixel 任务状态
export async function queryGigapixelTask(taskId) {
  return api.get(`/api/gigapixel/task/${taskId}`);
}

// 列出所有 gigapixel 任务
// status: 可选，按状态过滤
// cleanupInvalid: 默认 true，自动过滤掉失败任务和图片不在 gigapixel_output 的任务
export async function listGigapixelTasks(status, cleanupInvalid = true) {
  const params = {};
  if (status) params.status = status;
  if (cleanupInvalid) params.cleanup_invalid = 'true';
  return api.get('/api/gigapixel/tasks', { params });
}

// 列出所有已完成的 gigapixel 结果图
export async function listGigapixelOutputs() {
  return api.get('/api/gigapixel/outputs');
}

// 取消一个 gigapixel 任务（IN_PROGRESS 状态才能取消）
export async function cancelGigapixelTask(taskId) {
  return api.delete(`/api/gigapixel/task/${taskId}`);
}

// 查询后台 worker 队列状态
export async function queryGigapixelQueue() {
  return api.get('/api/gigapixel/queue');
}

// 将 gigapixel 任务的放大结果复制到预备目录
// 仅 SUCCESS 状态可调用；返回新建的 preparation item 记录
export async function copyGigapixelToPreparation(taskId) {
  return api.post('/api/gigapixel/copy-to-preparation', { task_id: taskId });
}

// 查询外部平台的用户余额
// 返回结构：{ status, platformName, displayAmount, amount, message?, raw? }
// status 取值：'success' | 'error'
export async function getUserBalance() {
  return api.get('/api/user/balance');
}

// 查询 APIYI 平台账户余额
// 返回结构：{ status, platformName, displayAmount, amount, rawAmount, matchedField, divider, message?, raw? }
// 与 getUserBalance 的区别：使用 apiyi_api 配置中的 accessToken 字段，而非 user_balance 配置
// 后端按 e:\AI-image\新建文件夹\apiyi\查询余额.md 文档实现，Authorization 无 Bearer 前缀
export async function getApiyiBalance() {
  return api.get('/api/apiyi/balance');
}

export async function getPromptTemplates() {
  return api.get('/api/prompt-templates');
}

export async function createPromptTemplateCategory(data) {
  return api.post('/api/prompt-templates/categories', data);
}

export async function updatePromptTemplateCategory(categoryId, data) {
  return api.put(`/api/prompt-templates/categories/${categoryId}`, data);
}

export async function deletePromptTemplateCategory(categoryId) {
  return api.delete(`/api/prompt-templates/categories/${categoryId}`);
}

export async function createPromptTemplate(data) {
  return api.post('/api/prompt-templates', data);
}

export async function updatePromptTemplate(templateId, data) {
  return api.put(`/api/prompt-templates/${templateId}`, data);
}

export async function deletePromptTemplate(templateId) {
  return api.delete(`/api/prompt-templates/${templateId}`);
}

export async function uploadPromptTemplateExample(templateId, image) {
  return api.post(`/api/prompt-templates/${templateId}/example-image`, { image }, { timeout: 120000 });
}

export async function generatePromptTemplateExample(templateId, defaults = {}) {
  return api.post(`/api/prompt-templates/${templateId}/generate-example`, defaults, { timeout: 90000 });
}

export async function getGeoList() {
  return api.get('/api/geo/list');
}

export async function updateGeoItem(itemId, data) {
  return api.put(`/api/geo/update/${itemId}`, data);
}

export async function batchUpdateGeoItems(ids, updates) {
  return api.post('/api/geo/batch-update', { ids, updates });
}

export async function renameGeoItem(itemId, newFilename) {
  return api.put(`/api/geo/rename/${itemId}`, { new_filename: newFilename });
}

export async function syncGeo() {
  return api.post('/api/geo/sync');
}

export async function deleteGeoItem(itemId) {
  return api.delete(`/api/geo/delete/${itemId}`);
}

export async function openGeoFolder(itemId) {
  return api.get(`/api/geo/open-folder/${itemId}`);
}

export async function getGeoPublishGroups() {
  return api.get('/api/geo/publish-groups');
}

export async function createGeoPublishGroup(publishDate) {
  return api.post('/api/geo/publish-groups', { publish_date: publishDate });
}

export async function moveGeoPublishGroup(itemId, publishDate) {
  return api.post('/api/geo/move-publish-group', { item_id: itemId, publish_date: publishDate });
}

export async function compressGeoPublishGroup(publishDate) {
  return api.post('/api/geo/compress-publish-group', { publish_date: publishDate }, { timeout: 600000 });
}
