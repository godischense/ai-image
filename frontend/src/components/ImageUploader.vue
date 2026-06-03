<template>
  <div class="image-uploader">
    <div class="image-uploader__header">
      <h2 class="image-uploader__title">图像上传</h2>
    </div>

    <div
      class="image-uploader__dropzone"
      :class="{
        'image-uploader__dropzone--dragover': isDragOver,
        'image-uploader__dropzone--disabled': disabled || uploading
      }"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop"
    >
      <svg class="image-uploader__dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
      <p class="image-uploader__dropzone-text">
        拖拽图像到此处，�?span class="u-text-primary">点击上传</span>
      </p>
      <p class="image-uploader__dropzone-hint">
        支持 JPG、PNG、WebP，最�?10MB
      </p>
      <input
        type="file"
        class="image-uploader__input"
        accept="image/jpeg,image/png,image/webp"
        multiple
        :disabled="disabled || uploading"
        @change="handleFileSelect"
      />
    </div>

    <div v-if="uploading" class="image-uploader__loading">
      <div class="image-uploader__spinner"></div>
      <p class="image-uploader__loading-text">上传�?.. {{ uploadProgress }}%</p>
    </div>

    <div v-if="error" class="image-uploader__error">
      {{ error }}
    </div>

    <div v-if="uploadedImages.length > 0" class="image-uploader__preview">
      <div class="image-uploader__preview-header">
        <span class="image-uploader__preview-title">已上�?/span>
        <span class="image-uploader__preview-count">{{ uploadedImages.length }} 张图�?/span>
      </div>
      <div class="image-uploader__preview-grid">
        <div
          v-for="(image, index) in uploadedImages"
          :key="image.id || index"
          class="image-uploader__preview-item"
        >
          <img
            :src="image.url"
            :alt="image.name || '上传图像'"
            class="image-uploader__preview-image"
          />
          <div class="image-uploader__preview-overlay">
            <button
              class="image-uploader__preview-action"
              @click="handlePreview(image)"
            >
              <svg class="image-uploader__preview-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
            <button
              class="image-uploader__preview-action image-uploader__preview-action--danger"
              @click="handleRemove(image, index)"
            >
              <svg class="image-uploader__preview-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 内嵌简化版图片预览弹窗 -->
    <Teleport to="body">
      <div
        v-if="showPreview"
        class="image-uploader__preview-backdrop"
        @click.self="showPreview = false"
      >
        <div class="image-uploader__preview-modal">
          <div class="image-uploader__preview-modal-header">
            <h3 class="image-uploader__preview-modal-title">{{ previewImage?.name || '图像预览' }}</h3>
            <button class="image-uploader__preview-modal-close" @click="showPreview = false">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div class="image-uploader__preview-modal-content">
            <img
              v-if="previewImage?.url"
              :src="previewImage.url"
              :alt="previewImage.name || '预览图像'"
              class="image-uploader__preview-modal-image"
            />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import './ImageUploader.scss'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  maxSize: {
    type: Number,
    default: 10 * 1024 * 1024
  },
  acceptedTypes: {
    type: Array,
    default: () => ['image/jpeg', 'image/png', 'image/webp']
  }
})

const emit = defineEmits(['upload', 'remove', 'preview'])

const isDragOver = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const error = ref('')
const uploadedImages = ref([])
const showPreview = ref(false)
const previewImage = ref(null)

const validateFile = (file) => {
  if (!props.acceptedTypes.includes(file.type)) {
    error.value = `不支持的文件类型: ${file.type}`
    return false
  }

  if (file.size > props.maxSize) {
    error.value = `文件大小超过限制 (最�?${props.maxSize / 1024 / 1024}MB)`
    return false
  }

  return true
}

const handleDragOver = () => {
  if (!props.disabled && !uploading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = () => {
  isDragOver.value = false
}

const handleDrop = (event) => {
  isDragOver.value = false

  if (props.disabled || uploading.value) return

  const files = Array.from(event.dataTransfer.files)
  processFiles(files)
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  processFiles(files)
  event.target.value = ''
}

const processFiles = async (files) => {
  error.value = ''

  const validFiles = files.filter(file => {
    if (!validateFile(file)) {
      return false
    }
    return true
  })

  if (validFiles.length === 0) return

  uploading.value = true
  uploadProgress.value = 0

  try {
    for (let i = 0; i < validFiles.length; i++) {
      const file = validFiles[i]
      const imageData = await uploadFile(file)

      uploadedImages.value.push({
        id: Date.now() + i,
        url: imageData.url,
        name: file.name,
        size: file.size,
        type: file.type
      })

      uploadProgress.value = Math.round(((i + 1) / validFiles.length) * 100)
    }

    emit('upload', uploadedImages.value)
  } catch (err) {
    error.value = err.message || '上传失败，请重试'
  } finally {
    uploading.value = false
    uploadProgress.value = 0
  }
}

const uploadFile = (file) => {
  return new Promise((resolve) => {
    setTimeout(() => {
      const reader = new FileReader()
      reader.onload = (e) => {
        resolve({
          url: e.target.result,
          name: file.name,
          size: file.size
        })
      }
      reader.readAsDataURL(file)
    }, 500)
  })
}

const handlePreview = (image) => {
  previewImage.value = image
  showPreview.value = true
  emit('preview', image)
}

const handleRemove = (image, index) => {
  uploadedImages.value.splice(index, 1)
  emit('remove', image)
}

const clearAll = () => {
  uploadedImages.value = []
}

defineExpose({ clearAll })
</script>
