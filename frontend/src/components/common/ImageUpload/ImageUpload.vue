<template>
  <div
    :class="[
      'image-upload',
      {
        'image-upload--disabled': disabled,
        'image-upload--dragging': isDragging,
        'image-upload--has-image': previewUrl,
        'image-upload--uploading': uploading
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
      :disabled="disabled || uploading"
      @change="handleFileChange"
    />

    <div v-if="!previewUrl && !uploading" class="image-upload__placeholder" @click="triggerUpload">
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

    <div v-if="uploading" class="image-upload__uploading">
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
  }
});

const emit = defineEmits(['update:modelValue', 'file-selected', 'upload-complete']);

const fileInputRef = ref(null);
const previewUrl = ref('');
const isDragging = ref(false);
const progress = ref(0);
const uploading = ref(false);
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
  uploading.value = true;
  uploadError.value = '';
  progress.value = 10;

  try {
    const localPreview = await readFileAsDataURL(file);
    previewUrl.value = localPreview;
    progress.value = 30;

    const serverUrl = await uploadToServer(file);
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
    const dataUrl = await readFileAsDataURL(file);
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