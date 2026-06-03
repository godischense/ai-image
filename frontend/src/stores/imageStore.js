import { defineStore } from 'pinia';
import { getImages, deleteImage, updateImage, moveToRecycleBin } from '../services/api';

const STORAGE_KEY = 'image_library';
const STORAGE_META_KEY = 'image_library_meta';
const PENDING_TASK_STATUSES = new Set([
  'PENDING',
  'IN_PROGRESS',
  'GENERATING',
  '未启动',
  'QUEUED',
  'NOT_STARTED',
  'NOT_START',
  'WAITING'
]);

function buildStaticUrlFromLocalPath(localPath = '') {
  if (!localPath || typeof localPath !== 'string') {
    return '';
  }

  const normalizedPath = localPath.replace(/\//g, '\\');
  if (normalizedPath.includes('\\generated_images\\')) {
    const idx = normalizedPath.indexOf('\\generated_images\\');
    const relativePath = normalizedPath.substring(idx + '\\generated_images\\'.length);
    return `/api/static/generated_images/${relativePath.replace(/\\/g, '/')}`;
  }

  if (normalizedPath.includes('\\edit_folders\\')) {
    const [, relativePath = ''] = normalizedPath.split('\\edit_folders\\');
    return relativePath ? `/api/static/edit_images/${relativePath.replace(/\\/g, '/')}` : '';
  }

  return '';
}

function parseSizeToAspectRatio(size) {
  if (!size || typeof size !== 'string' || !size.includes('x')) {
    return null;
  }
  const parts = size.split('x');
  if (parts.length !== 2) {
    return null;
  }
  const width = parseFloat(parts[0]);
  const height = parseFloat(parts[1]);
  if (!(width > 0) || !(height > 0)) {
    return null;
  }
  return width / height;
}

// 将远程 URL 包装为后端代理 URL，避免浏览器 ORB 拦截跨域图片
function proxyRemoteUrl(url) {
  if (!url || typeof url !== 'string') return ''
  if (url.startsWith('/api/') || url.startsWith('data:')) return url
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return `/api/proxy/image?url=${encodeURIComponent(url)}`
  }
  return url
}

function normalizeImage(image = {}) {
  const taskId = image.task_id || image.taskId || null;
  const status = typeof image.status === 'string' ? image.status.trim() : (image.status || null);
  const explicitGenerating = typeof image.generating === 'boolean' ? image.generating : null;
  const generating = explicitGenerating ?? PENDING_TASK_STATUSES.has(status);
  const imageType = image.image_type || image.imageType || 'generation';
  const rawUrl = buildStaticUrlFromLocalPath(image.local_path) || image.display_url || image.url || '';
  const resolvedUrl = proxyRemoteUrl(rawUrl);
  const sizeStr = image.size || '';
  let aspectRatio = image.aspect_ratio ?? image.aspectRatio;
  if (aspectRatio == null || aspectRatio <= 0 || Number.isNaN(Number(aspectRatio))) {
    const parsed = parseSizeToAspectRatio(sizeStr);
    if (parsed != null) {
      aspectRatio = parsed;
    }
  }

  return {
    ...image,
    task_id: taskId,
    taskId,
    image_type: imageType,
    imageType,
    status,
    progress: image.progress || '',
    fail_reason: image.fail_reason || '',
    download_error: image.download_error || '',
    generating,
    error: image.error || (status === 'FAILURE' ? (image.fail_reason || '图片生成失败') : ''),
    thumbnail: image.thumbnail || '',
    url: resolvedUrl,
    aspect_ratio: (typeof aspectRatio === 'number' && aspectRatio > 0 && Number.isFinite(aspectRatio))
      ? aspectRatio
      : image.aspect_ratio,
    aspectRatio: (typeof aspectRatio === 'number' && aspectRatio > 0 && Number.isFinite(aspectRatio))
      ? aspectRatio
      : image.aspectRatio
  };
}

function getImageIdentity(image = {}) {
  return image.id || image.task_id || image.taskId || null;
}

function mergeImages(primaryImages = [], secondaryImages = []) {
  const merged = [];
  const indexMap = new Map();

  const pushImage = (sourceImage) => {
    const normalizedImage = normalizeImage(sourceImage);
    const identity = getImageIdentity(normalizedImage);
    const taskId = normalizedImage.task_id;

    const existingIndex = identity && indexMap.has(identity)
      ? indexMap.get(identity)
      : taskId && indexMap.has(taskId)
        ? indexMap.get(taskId)
        : -1;

    if (existingIndex !== -1) {
      merged[existingIndex] = normalizeImage({
        ...merged[existingIndex],
        ...normalizedImage
      });
      if (identity) {
        indexMap.set(identity, existingIndex);
      }
      if (taskId) {
        indexMap.set(taskId, existingIndex);
      }
      return;
    }

    const nextIndex = merged.length;
    merged.push(normalizedImage);
    if (identity) {
      indexMap.set(identity, nextIndex);
    }
    if (taskId) {
      indexMap.set(taskId, nextIndex);
    }
  };

  primaryImages.forEach(pushImage);
  secondaryImages.forEach(pushImage);

  return merged;
}

function loadFromStorage() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? mergeImages(JSON.parse(data), []) : [];
  } catch {
    return [];
  }
}

function loadMetaFromStorage() {
  try {
    const data = localStorage.getItem(STORAGE_META_KEY);
    const parsed = data ? JSON.parse(data) : {};
    return {
      lastFetchedAt: typeof parsed.lastFetchedAt === 'number' ? parsed.lastFetchedAt : 0
    };
  } catch {
    return {
      lastFetchedAt: 0
    };
  }
}

function saveToStorage(images) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(mergeImages(images, [])));
  } catch (e) {
    console.warn('[imageStore] Failed to save to localStorage:', e);
  }
}

function saveMetaToStorage(meta = {}) {
  try {
    localStorage.setItem(STORAGE_META_KEY, JSON.stringify({
      lastFetchedAt: meta.lastFetchedAt || 0
    }));
  } catch (e) {
    console.warn('[imageStore] Failed to save meta to localStorage:', e);
  }
}

export const useImageStore = defineStore('image', {
  state: () => {
    const cachedImages = loadFromStorage();
    const cachedMeta = loadMetaFromStorage();

    return {
      images: cachedImages,
      loading: false,
      initialLoading: cachedImages.length === 0,
      refreshing: false,
      lastFetchedAt: cachedMeta.lastFetchedAt,
      error: null
    };
  },

  actions: {
    async fetchImages() {
      const hasCachedImages = this.images.length > 0;
      this.initialLoading = !hasCachedImages;
      this.refreshing = hasCachedImages;
      this.loading = !hasCachedImages;
      this.error = null;
      try {
        const data = await getImages();
        // 保留当前正在生成的占位卡片，避免被后端数据覆盖导致刷新/切页后消失
        const generatingCards = this.images.filter(img => img.generating === true);
        // 后端数据与保留的占位卡片合并
        this.images = mergeImages(data || [], generatingCards);
        this.lastFetchedAt = Date.now();
        saveToStorage(this.images);
        saveMetaToStorage({ lastFetchedAt: this.lastFetchedAt });
      } catch (err) {
        this.error = err.message || '获取图像列表失败';
      } finally {
        this.initialLoading = false;
        this.refreshing = false;
        this.loading = false;
      }
    },

    /**
     * 添加正在生成的占位图片
     * 用于在图片库中显示生成进度
     */
    addGeneratingImage(imageData) {
      this.upsertImage(imageData);
    },

    upsertImage(imageData) {
      const normalizedImage = normalizeImage(imageData);
      const imageId = normalizedImage.id;
      const taskId = normalizedImage.task_id;
      const index = this.images.findIndex((img) => {
        if (imageId && img.id === imageId) {
          return true;
        }

        const currentTaskId = img.task_id || img.taskId;
        return Boolean(taskId) && currentTaskId === taskId;
      });

      if (index === -1) {
        this.images.unshift(normalizedImage);
      } else {
        this.images[index] = normalizeImage({
          ...this.images[index],
          ...normalizedImage
        });
      }

      saveToStorage(this.images);
      return normalizedImage;
    },

    /**
     * 删除图片
     *
     * 功能描述：
     *   将图片移动到回收站（软删除）
     *   如果删除的是正在生成的占位图，直接从本地移除
     *
     * 参数：
     *   imageOrId: 图片对象或图片ID
     */
    async deleteImage(imageOrId) {
      this.loading = true;
      this.error = null;

      try {
        // 支持传入 image 对象或直接传入 id
        const imageId = typeof imageOrId === 'object' ? imageOrId.id : imageOrId;
        const taskId = typeof imageOrId === 'object' ? (imageOrId.task_id || imageOrId.taskId) : null;
        const isGenerating = typeof imageOrId === 'object' ? imageOrId.generating : false;

        if (isGenerating || (typeof imageId === 'string' && imageId.startsWith('generating-'))) {
          // 如果是正在生成的占位图，不调用后端，直接从本地移除
          this.images = this.images.filter((img) => img.id !== imageId && (img.task_id || img.taskId) !== taskId);
        } else {
          // 正常图片移动到回收站（软删除）
          const sourcePath = typeof imageOrId === 'object' ? (imageOrId.local_path || imageOrId.localUrl || '') : '';
          await moveToRecycleBin(imageId, sourcePath);
          // 从当前列表移除（后端会标记 is_deleted = 1）
          this.images = this.images.filter((img) => img.id !== imageId);
        }

        saveToStorage(this.images);
      } catch (err) {
        this.error = err.message || '删除图像失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    async updateImage(imageId, updateData) {
      this.loading = true;
      this.error = null;
      try {
        const response = await updateImage(imageId, updateData);
        return this.upsertImage({ ...updateData, ...(response?.image || response), id: imageId });
      } catch (err) {
        this.error = err.message || '更新图像失败';
        throw err;
      } finally {
        this.loading = false;
      }
    }
  }
});
