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

  if ('falApi' in rawConfig) {
    result.falApi = normalizeSection(rawConfig.falApi);
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
  return api.post(url, formData, { timeout: 300000 })
}

export async function getImages(params = {}) {
  const response = await api.get('/api/images', { params });
  return response.images || [];
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

export async function saveCopyCountryNote(country, note) {
  return api.post('/api/copy/country-note', { country, note });
}

export async function getCopyContent(path) {
  return api.get('/api/copy/content', { params: { path } });
}

export async function saveCopyContent(path, content) {
  return api.post('/api/copy/content', { path, content });
}

export async function createCopyBoard(country) {
  return api.post('/api/copy/boards', { country });
}

export async function getCopyBoardContent(path) {
  return api.get('/api/copy/boards/content', { params: { path } });
}

export async function saveCopyBoardContent(path, cards) {
  return api.post('/api/copy/boards/content', { path, cards });
}

export async function deleteCopyBoard(path) {
  return api.delete('/api/copy/boards/content', { params: { path } });
}

export async function renameCopyBoard(path, name) {
  return api.post('/api/copy/boards/rename', { path, name });
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
