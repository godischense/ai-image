<template>
  <Teleport to="body">
    <div
      v-if="show || image"
      class="image-preview__backdrop"
      @click.self="handleClose"
    >
      <div class="image-preview__modal">
        <div class="image-preview__header">
          <h3 class="image-preview__title">{{ resolvedTitle || '图像预览' }}</h3>
          <div class="image-preview__actions">
            <button
              class="image-preview__action-btn image-preview__action-btn--primary"
              @click="handleDownload"
              :disabled="!resolvedSrc || downloading"
            >
              <svg class="image-preview__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              <span>{{ downloading ? '下载�?..' : '下载' }}</span>
            </button>
          </div>
        </div>

        <div class="image-preview__content">
          <div class="image-preview__image-container">
            <img
              v-if="resolvedSrc && !loadError"
              :src="resolvedSrc"
              :alt="alt || resolvedTitle"
              class="image-preview__image"
              @load="handleImageLoad"
              @error="handleImageError"
            />
            <div v-else class="image-preview__error">
              <span>{{ resolvedSrc ? '原图加载失败，请检查图片地址是否有效' : '缺少可预览的图片地址' }}</span>
            </div>
            <button class="image-preview__close" @click="handleClose">
              <svg class="image-preview__close-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>

        <div v-if="showInfo" class="image-preview__info">
          <div class="image-preview__meta">
            <div v-if="width && height" class="image-preview__meta-item">
              <svg class="image-preview__meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              </svg>
              <span>{{ width }} × {{ height }}</span>
            </div>
            <div v-if="format" class="image-preview__meta-item">
              <svg class="image-preview__meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
              <span>{{ format.toUpperCase() }}</span>
            </div>
            <div v-if="size" class="image-preview__meta-item">
              <svg class="image-preview__meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
              </svg>
              <span>{{ formatSize(size) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import './ImagePreview.scss'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  image: {
    type: Object,
    default: null
  },
  src: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    default: ''
  },
  alt: {
    type: String,
    default: ''
  },
  showInfo: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['close', 'download'])

const resolvedSrc = computed(() => {
  return props.src || props.image?.url || props.image?.src || ''
})

const resolvedTitle = computed(() => {
  return props.title || props.image?.title || props.image?.prompt || ''
})

const width = ref(0)
const height = ref(0)
const format = ref('')
const size = ref(0)
const downloading = ref(false)
const loadError = ref(false)

const resetImageState = () => {
  width.value = 0
  height.value = 0
  format.value = ''
  size.value = 0
  loadError.value = false
}

const handleClose = () => {
  emit('close')
}

const handleDownload = async () => {
  if (!resolvedSrc.value) return

  downloading.value = true

  try {
    const response = await fetch(resolvedSrc.value)
    const blob = await response.blob()
    size.value = blob.size

    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = resolvedTitle.value || 'image'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)

    emit('download', { src: resolvedSrc.value, blob })
  } catch (error) {
    console.error('Download failed:', error)
  } finally {
    downloading.value = false
  }
}

const handleImageLoad = (event) => {
  loadError.value = false
  const img = event.target
  width.value = img.naturalWidth
  height.value = img.naturalHeight

  const urlParts = resolvedSrc.value.split('.')
  if (urlParts.length > 1) {
    format.value = urlParts[urlParts.length - 1].split('?')[0]
  }
}

const handleImageError = () => {
  resetImageState()
  loadError.value = true
  console.error('Failed to load image')
}

const formatSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const handleKeydown = (event) => {
  if (event.key === 'Escape' && props.show) {
    handleClose()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

watch(() => props.show, (newVal) => {
  if (newVal) {
    resetImageState()
    document.body.classList.add('body--overflow-hidden')
  } else {
    resetImageState()
    document.body.classList.remove('body--overflow-hidden')
  }
})

watch(resolvedSrc, () => {
  resetImageState()
})
</script>
