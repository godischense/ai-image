<template>
  <div
    :class="[
      'image-upload',
      {
        'image-upload--disabled': disabled,
        'image-upload--dragging': isDragging,
        'image-upload--has-image': previewUrl,
        'image-upload--uploading': uploading || compressing
      }
    ]"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
  >
    <input
      ref="fileInputRef"
      type="file"
      :accept="accept"
      class="image-upload__input"
      :disabled="disabled || uploading || compressing"
      @change="handleFileChange"
    />

    <div v-if="!previewUrl && !uploading && !compressing" class="image-upload__placeholder" @click="triggerUpload">
      <div class="image-upload__icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      </div>
      <p class="image-upload__text">拖拽图片到此处，或点击上传</p>
      <p class="image-upload__hint">支持 JPG、PNG、WebP 格式</p>
    </div>

    <div v-if="compressing" class="image-upload__uploading">
      <div class="image-upload__spinner"></div>
      <p class="image-upload__uploading-text">图片处理中...</p>
    </div>

    <div v-else-if="uploading" class="image-upload__uploading">
      <div class="image-upload__spinner"></div>
      <p class="image-upload__uploading-text">上传中...</p>
    </div>

    <div v-else-if="previewUrl" class="image-upload__preview">
      <img :src="previewUrl" alt="预览图片" class="image-upload__image" />
      <div v-if="!disabled" class="image-upload__overlay">
        <button type="button" class="image-upload__replace-btn" @click="triggerUpload">
          更换图片
        </button>
        <button type="button" class="image-upload__remove-btn" @click="removeImage">
          移除
        </button>
      </div>
    </div>

    <div v-if="progress > 0 && progress < 100" class="image-upload__progress">
      <div class="image-upload__progress-bar" :style="{ width: `${progress}%` }"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { compressImageIfOversize, readImageSize } from '@/utils/imageCompressor';

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  accept: {
    type: String,
    default: 'image/jpeg,image/png,image/webp'
  },
  // 最大边长限制（px），超过该值会按比例自动压缩
  // 设置为 0 或不传则不启用自动压缩
  maxEdge: {
    type: Number,
    default: 0
  },
  // 文件超过 maxEdge 时由父组件决定压缩目标分辨率的回调
  // 形如：async (info) => { return { maxEdge: number, abort?: boolean } }
  //   info = { file, originalSize, defaultMaxEdge }
  //   返回 { abort: true } 取消本次上传
  //   返回 { maxEdge: number } 压缩到指定边长
  //   不返回 / 抛错 时回退到 defaultMaxEdge 自动压缩
  // 设置为 null 时直接按 defaultMaxEdge 自动压缩，不弹窗
  onOversize: {
    type: Function,
    default: null
  }
});

const emit = defineEmits(['update:modelValue', 'file-selected', 'upload-complete', 'compressed']);

const fileInputRef = ref(null);
const previewUrl = ref('');
const isDragging = ref(false);
const progress = ref(0);
const uploading = ref(false);
const compressing = ref(false);
const uploadError = ref('');

const acceptedTypes = ['image/jpeg', 'image/png', 'image/webp'];

const validateFile = (file) => {
  if (!file) {
    return false;
  }
  if (!acceptedTypes.includes(file.type)) {
    console.warn('不支持的文件格式，仅支持 JPG、PNG、WebP');
    return false;
  }
  return true;
};

const readFileAsDataURL = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = (e) => reject(e);
    reader.readAsDataURL(file);
  });
};

const readFileAsBlobURL = (file) => {
  return URL.createObjectURL(file);
};

const uploadToServer = async (file) => {
  try {
    const formData = new FormData();
    formData.append('image', file);
    const response = await fetch('/api/images/upload', {
      method: 'POST',
      body: formData
    });
    if (!response.ok) {
      throw new Error(`上传失败: ${response.status}`);
    }
    const data = await response.json();
    if (data.status === 'success' && data.url) {
      return data.url;
    }
    if (data.image?.url) {
      return data.image.url;
    }
    throw new Error('服务器返回数据格式错误');
  } catch (error) {
    console.error('上传到服务器失败:', error);
    throw error;
  }
};

const handleFile = async (file) => {
  if (!validateFile(file)) {
    return;
  }

  emit('file-selected', file);
  progress.value = 10;

  // 处理图片：若设置了 maxEdge，按需自动压缩
  // 实现逻辑：
  //   1. 若 maxEdge <= 0：跳过压缩，直接使用原文件
  //   2. 读取原图尺寸，若未超过 maxEdge：跳过压缩，使用原文件
  //   3. 超过 maxEdge 时：
  //      a. 若设置了 onOversize：调用回调等待父组件决定目标分辨率
  //         - 返回 { abort: true }：取消本次上传
  //         - 返回 { maxEdge: N }：压缩到 N
  //         - 未返回 / 抛错：回退到默认 maxEdge 自动压缩
  //      b. 未设置 onOversize：直接按 maxEdge 自动压缩
  //   4. 压缩成功时通过 'compressed' 事件把原始尺寸/新尺寸回传给父组件
  //   5. 压缩失败时（异常/不支持等）静默回退到原文件，不阻塞上传
  let processResult = null
  let workingFile = file
  if (props.maxEdge && props.maxEdge > 0) {
    let targetMaxEdge = props.maxEdge
    let userAborted = false
    let originalSize = null
    try {
      originalSize = await readImageSize(file)
    } catch (err) {
      // 无法读取尺寸：跳过压缩，原文件上传
      originalSize = null
    }
    const longEdge = originalSize ? Math.max(originalSize.width, originalSize.height) : 0
    const needCompress = longEdge > props.maxEdge

    if (needCompress && typeof props.onOversize === 'function') {
      compressing.value = true
      try {
        const decision = await props.onOversize({
          file,
          originalSize,
          defaultMaxEdge: props.maxEdge
        })
        if (decision && decision.abort) {
          userAborted = true
        } else if (decision && typeof decision.maxEdge === 'number' && decision.maxEdge > 0) {
          targetMaxEdge = decision.maxEdge
        } else {
          targetMaxEdge = props.maxEdge
        }
      } catch (err) {
        console.warn('[ImageUpload] onOversize 回调异常，回退到默认 maxEdge:', err)
        targetMaxEdge = props.maxEdge
      } finally {
        compressing.value = false
      }
    }

    if (userAborted) {
      // 用户取消：清空进度，不上传
      progress.value = 0
      return
    }

    if (needCompress) {
      compressing.value = true
      try {
        processResult = await compressImageIfOversize(file, { maxEdge: targetMaxEdge })
        if (processResult.compressed) {
          workingFile = processResult.file
        }
      } catch (err) {
        console.warn('[ImageUpload] 压缩流程异常，回退到原文件:', err)
      } finally {
        compressing.value = false
      }
      if (processResult?.compressed) {
        emit('compressed', {
          originalSize: processResult.originalSize || originalSize,
          newSize: processResult.newSize,
          maxEdge: targetMaxEdge
        })
      }
    }
  }

  uploading.value = true;
  uploadError.value = '';
  progress.value = 30;

  try {
    const localPreview = await readFileAsDataURL(workingFile);
    previewUrl.value = localPreview;
    progress.value = 50;

    const serverUrl = await uploadToServer(workingFile);
    progress.value = 90;

    emit('update:modelValue', serverUrl);
    emit('upload-complete', {
      url: serverUrl,
      thumbnail: serverUrl,
      id: null,
      prompt: '新上传图片'
    });

    progress.value = 100;
  } catch (error) {
    console.error('上传失败，fallback 到 base64:', error);
    const dataUrl = await readFileAsDataURL(workingFile);
    previewUrl.value = dataUrl;
    emit('update:modelValue', dataUrl);
    emit('upload-complete', {
      url: dataUrl,
      thumbnail: dataUrl,
      id: null,
      prompt: '新上传图片'
    });
    progress.value = 100;
  } finally {
    uploading.value = false;
  }
};

const triggerUpload = () => {
  if (props.disabled) {
    return;
  }
  fileInputRef.value?.click();
};

const handleFileChange = (event) => {
  const file = event.target.files?.[0];
  if (file) {
    handleFile(file);
  }
  event.target.value = '';
};

const handleDragEnter = (event) => {
  if (props.disabled) {
    return;
  }
  isDragging.value = true;
};

const handleDragOver = (event) => {
  if (props.disabled) {
    return;
  }
  isDragging.value = true;
};

const handleDragLeave = (event) => {
  if (props.disabled) {
    return;
  }
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX;
  const y = event.clientY;
  if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
    isDragging.value = false;
  }
};

const handleDrop = (event) => {
  if (props.disabled) {
    return;
  }
  isDragging.value = false;

  const files = event.dataTransfer?.files;
  const file = files?.[0];
  if (file) {
    handleFile(file);
  }
};

const removeImage = () => {
  if (props.disabled) {
    return;
  }
  previewUrl.value = '';
  progress.value = 0;
  emit('update:modelValue', '');
};

watch(
  () => props.modelValue,
  (newVal) => {
    if (newVal !== previewUrl.value) {
      previewUrl.value = newVal || '';
    }
  },
  { immediate: true }
);
</script>

<script>
export default {
  name: 'ImageUpload'
};
</script>

<style lang="scss" src="./ImageUpload.scss"></style>
