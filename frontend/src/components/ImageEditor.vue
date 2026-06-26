
<template>
  <div class="image-editor">
    <div class="image-editor__header">
      <h2 class="image-editor__title">编辑指令</h2>
      <div v-if="selectedApiProvider !== 'fal' && selectedApiProvider !== 'apiyi'" class="image-editor__mode-toggle">
        <span :class="{ 'u-text-primary': !isAsync }">同步</span>
        <button
          class="image-editor__toggle-switch"
          :class="{ 'image-editor__toggle-switch--active': isAsync }"
          @click="toggleAsync"
          :disabled="loading"
        ></button>
        <span :class="{ 'u-text-primary': isAsync }">异步</span>
      </div>
    </div>

    <div class="image-editor__form">
      <div class="image-editor__field">
        <label class="image-editor__label">编辑指令</label>
        <textarea
          v-model="prompt"
          class="image-editor__textarea"
          placeholder="描述你想要对图像进行的修改..."
          :disabled="loading"
        ></textarea>
      </div>

      <!-- API 提供者选择器 -->
      <div class="image-editor__option-row">
        <div class="image-editor__option-group">
          <label class="image-editor__option-label">API</label>
          <select
            v-model="selectedApiProvider"
            class="image-editor__option-select"
            :disabled="loading"
          >
            <option value="openai">OpenAI 兼容</option>
            <option v-if="hasFalApiKey" value="fal">Fal API</option>
            <option v-if="hasApiyiApiKey" value="apiyi">APIYI</option>
          </select>
        </div>
      </div>

      <div class="image-editor__options">
        <div class="image-editor__option-row">
          <div v-if="selectedApiProvider === 'apiyi'" class="image-editor__option-group">
            <label class="image-editor__option-label">模型</label>
            <select
              v-model="selectedModel"
              class="image-editor__option-select"
              :disabled="loading"
            >
              <option v-for="model in modelOptions" :key="model.value" :value="model.value">
                {{ model.label }}
              </option>
            </select>
          </div>

          <div class="image-editor__option-group">
            <label class="image-editor__option-label">尺寸比例</label>
            <select
              v-model="selectedAspectRatio"
              class="image-editor__option-select"
              :disabled="loading"
            >
              <option v-for="option in aspectRatioOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>

          <div v-if="!isApiyiGptImage2Vip" class="image-editor__option-group">
            <label class="image-editor__option-label">RES</label>
            <select
              v-model="selectedResolution"
              class="image-editor__option-select"
              :disabled="loading"
            >
              <option v-for="resolution in currentResolutions" :key="resolution.value" :value="resolution.value">
                {{ resolution.label }}
              </option>
            </select>
          </div>

          <div class="image-editor__option-group">
            <label class="image-editor__option-label">清晰度</label>
            <select
              v-model="selectedQuality"
              class="image-editor__option-select"
              :disabled="loading"
            >
              <option value="auto">自动</option>
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </div>

          <!-- Fal 模式下显示生成数量和输出格式控制 -->
          <template v-if="selectedApiProvider === 'fal'">
            <div class="image-editor__option-group">
              <label class="image-editor__option-label">生成数量</label>
              <select
                v-model="selectedNumImages"
                class="image-editor__option-select"
                :disabled="loading"
              >
                <option :value="1">1</option>
                <option :value="2">2</option>
                <option :value="3">3</option>
                <option :value="4">4</option>
              </select>
            </div>
            <div class="image-editor__option-group">
              <label class="image-editor__option-label">输出格式</label>
              <select
                v-model="selectedOutputFormat"
                class="image-editor__option-select"
                :disabled="loading"
              >
                <option value="png">PNG</option>
                <option value="jpeg">JPEG</option>
                <option value="webp">WebP</option>
              </select>
            </div>
          </template>
        </div>

        <div class="image-editor__meta">
          <div class="image-editor__meta-item">
            <span class="image-editor__meta-label">实际尺寸</span>
            <span class="image-editor__meta-value">{{ resolvedSize }}</span>
          </div>
        </div>

        <div class="image-editor__option-row">
          <div class="image-editor__option-group image-editor__option-group--full">
            <label class="image-editor__option-label">参考图（可选，支持多张）</label>
            <div class="image-editor__reference-container">
              <div
                class="image-editor__reference-dropzone"
                :class="{ 'image-editor__reference-dropzone--dragover': isReferenceDragOver }"
                @dragover.prevent="handleReferenceDragOver"
                @dragleave.prevent="handleReferenceDragLeave"
                @drop.prevent="handleReferenceDrop"
                @click="triggerReferenceUpload"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <span>点击或拖拽添加参考图</span>
              </div>
              
              <div v-if="referenceImages.length > 0" class="image-editor__reference-list">
                <div
                  v-for="(img, index) in referenceImages"
                  :key="img.id"
                  class="image-editor__reference-item"
                >
                  <img :src="img.url" class="image-editor__reference-thumb" />
                  <button class="image-editor__reference-remove" @click.stop="removeReferenceImage(index)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                  </button>
                </div>
              </div>
            </div>
            <input
              type="file"
              ref="referenceInputRef"
              class="image-editor__reference-input"
              accept="image/jpeg,image/png,image/webp"
              multiple
              @change="handleReferenceFileSelect"
            />
          </div>
        </div>

      </div>

      <div v-if="showContentMaskPreview" class="image-editor__content-mask">
        <div class="image-editor__content-mask-header">
          <div class="image-editor__content-mask-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 10H4"></path>
              <path d="M14 14H4"></path>
              <path d="M14 18H4"></path>
              <path d="M20 4L14 10"></path>
              <path d="M20 8L14 14"></path>
              <path d="M20 12L14 18"></path>
            </svg>
            <span>已添加内容遮罩</span>
          </div>
          <button class="image-editor__content-mask-remove" @click="clearExternalMask">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="image-editor__content-mask-preview">
          <img
            :src="imageSrc"
            class="image-editor__content-mask-image"
            alt="当前编辑图片"
          />
          <img
            :src="props.externalMask"
            class="image-editor__content-mask-overlay"
            alt="内容遮罩预览"
          />
        </div>

        <div class="image-editor__content-mask-tip">
          <span>白色区域为将被编辑的内容遮罩范围</span>
        </div>
      </div>

      <div v-if="error" class="image-editor__error">
        {{ error }}
      </div>

      <div class="image-editor__actions">
        <button
          class="image-editor__btn image-editor__btn--secondary"
          @click="handleReset"
          :disabled="loading"
        >
          重置
        </button>
        <button
          class="image-editor__btn image-editor__btn--primary"
          @click="handleEdit"
          :disabled="!canEdit || loading"
        >
          <svg v-if="loading" class="image-editor__btn-icon image-editor__spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="2" x2="12" y2="6"></line>
            <line x1="12" y1="18" x2="12" y2="22"></line>
            <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
            <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
            <line x1="2" y1="12" x2="6" y2="12"></line>
            <line x1="18" y1="12" x2="22" y2="12"></line>
            <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
            <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
          </svg>
          <span>{{ loading ? (isAsync ? '提交中...' : '编辑中...') : '编辑图像' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useConfigStore } from '@/stores/configStore'
import { api } from '@/services/api'
import { APIYI_ASPECT_RATIO_OPTIONS, APIYI_RESOLUTIONS, resolveApiyiSize } from '@/utils/apiyiOptions'
import './ImageEditor.scss'

const props = defineProps({
  image: {
    type: [String, Object],
    default: ''
  },
  asyncMode: {
    type: Boolean,
    default: false
  },
  externalMask: {
    type: String,
    default: null
  },
  submitting: {
    type: Boolean,
    default: false
  },
  submitError: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['edit', 'reset', 'async-change'])

const configStore = useConfigStore()

function loadEditorPrefs() {
  try {
    const data = localStorage.getItem('image_editor_prefs')
    if (data) {
      return JSON.parse(data)
    }
  } catch {}
  return {}
}

function saveEditorPrefs(prefs) {
  try {
    const existing = loadEditorPrefs()
    localStorage.setItem('image_editor_prefs', JSON.stringify({ ...existing, ...prefs }))
  } catch {}
}

const savedEditorPrefs = loadEditorPrefs()

const imageSrc = ref('')
const referenceImages = ref([])
const referenceInputRef = ref(null)
const isReferenceDragOver = ref(false)

watch(() => props.image, (newVal) => {
  if (typeof newVal === 'string') {
    imageSrc.value = newVal
  } else if (newVal && newVal.url) {
    imageSrc.value = newVal.url
  }
}, { immediate: true })

const aspectRatios = [
  { value: '1:1', width: 1, height: 1 },
  { value: '3:2', width: 3, height: 2 },
  { value: '2:3', width: 2, height: 3 },
  { value: '4:3', width: 4, height: 3 },
  { value: '3:4', width: 3, height: 4 },
  { value: '5:4', width: 5, height: 4 },
  { value: '4:5', width: 4, height: 5 },
  { value: '16:9', width: 16, height: 9 },
  { value: '9:16', width: 9, height: 16 },
  { value: '2:1', width: 2, height: 1 },
  { value: '1:2', width: 1, height: 2 },
  { value: '21:9', width: 21, height: 9 },
  { value: '9:21', width: 9, height: 21 }
]

const resolutions = [
  { value: '1K', label: '1K', key: '1k' },
  { value: '2K', label: '2K', key: '2k' },
  { value: '4K', label: '4K', key: '4k' }
]

const sizeMap = {
  '1:1': { '1k': '1024x1024', '2k': '2048x2048', '4k': '2880x2880' },
  '16:9': { '1k': '1280x720', '2k': '2560x1440', '4k': '3840x2160' },
  '9:16': { '1k': '720x1280', '2k': '1440x2560', '4k': '2160x3840' },
  '4:3': { '1k': '1152x864', '2k': '2304x1728', '4k': '3264x2448' },
  '3:4': { '1k': '864x1152', '2k': '1728x2304', '4k': '2448x3264' },
  '3:2': { '1k': '1248x832', '2k': '2496x1664', '4k': '3504x2336' },
  '2:3': { '1k': '832x1248', '2k': '1664x2496', '4k': '2336x3504' },
  '5:4': { '1k': '1120x896', '2k': '2240x1792', '4k': '3200x2560' },
  '4:5': { '1k': '896x1120', '2k': '1792x2240', '4k': '2560x3200' },
  '21:9': { '1k': '1456x624', '2k': '3024x1296', '4k': '3696x1584' },
  '9:21': { '1k': '624x1456', '2k': '1296x3024', '4k': '1584x3696' },
  '2:1': { '1k': '2048x1024', '2k': '2688x1344', '4k': '3840x1920' },
  '1:2': { '1k': '1024x2048', '2k': '1344x2688', '4k': '1920x3840' },
  'fullscreen': { '1k': '688x1488', '2k': '1072x2336', '4k': '1760x3840' }
}

const defaultAspectRatioOptions = computed(() => {
  return [
    { value: 'auto', label: '自动' },
    ...aspectRatios.map((ratio) => ({ value: ratio.value, label: ratio.value })),
    { value: 'fullscreen', label: '全屏' }
  ]
})

const aspectRatioOptions = computed(() => {
  return selectedApiProvider.value === 'apiyi' && !isApiyiGptImage2.value
    ? APIYI_ASPECT_RATIO_OPTIONS
    : defaultAspectRatioOptions.value
})

const prompt = ref('')
const isAsync = ref(props.asyncMode)
const error = ref('')
const selectedAspectRatio = ref('auto')
const selectedResolution = ref('2K')
const selectedQuality = ref('auto')
// 当前选择的 API 提供者（openai 或 fal），从 localStorage 恢复
const selectedApiProvider = ref(savedEditorPrefs.selectedApiProvider || 'openai')
const selectedModel = ref(savedEditorPrefs.selectedModel || 'gpt-image-2')
// Fal 模式下选中的生成数量
const selectedNumImages = ref(1)
// Fal 模式下选中的输出格式
const selectedOutputFormat = ref('png')
const internalMask = ref(null)

// 判断是否已配置 Fal API Key，用于控制 Fal API 选项的显示
const hasFalApiKey = computed(() => {
  return Boolean(configStore?.falApi?.apiKey?.trim())
})

// 判断是否已配置 APIYI API Key，用于控制 APIYI 选项的显示
const hasApiyiApiKey = computed(() => {
  return Boolean(configStore?.apiyiApi?.apiKey?.trim())
})

const loading = computed(() => props.submitting)

const models = computed(() => {
  if (selectedApiProvider.value === 'fal') {
    return ['openai/gpt-image-2']
  }
  if (selectedApiProvider.value === 'apiyi') {
    const configuredModels = Array.isArray(configStore.apiyiApi?.imageModels) && configStore.apiyiApi.imageModels.length > 0
      ? configStore.apiyiApi.imageModels
      : ['gpt-image-2-vip', 'gpt-image-2']
    const mergedModels = Array.from(new Set([...configuredModels, 'gpt-image-2']))
    return mergedModels.map(model => model.startsWith('apiyi/') ? model : `apiyi/${model}`)
  }
  return Array.isArray(configStore.imageApi?.imageModels) && configStore.imageApi.imageModels.length > 0
    ? configStore.imageApi.imageModels
    : ['gpt-image-2']
})

const modelOptions = computed(() => {
  return models.value.map(model => ({ value: model, label: model }))
})

const isApiyiGptImage2 = computed(() => {
  return selectedApiProvider.value === 'apiyi' && selectedModel.value.replace('apiyi/', '') === 'gpt-image-2'
})

const isApiyiGptImage2Vip = computed(() => {
  return selectedApiProvider.value === 'apiyi' && selectedModel.value.replace('apiyi/', '') === 'gpt-image-2-vip'
})

const currentResolutions = computed(() => {
  if (isApiyiGptImage2Vip.value) {
    return []
  }
  if (selectedApiProvider.value === 'apiyi' && !isApiyiGptImage2.value) {
    return APIYI_RESOLUTIONS
  }
  return resolutions
})

const resolvedSize = computed(() => {
  if (selectedApiProvider.value === 'apiyi' && !isApiyiGptImage2.value) {
    return resolveApiyiSize(selectedAspectRatio.value, selectedResolution.value)
  }

  if (selectedAspectRatio.value === 'auto') {
    return 'auto'
  }
  
  const sizeByAspect = sizeMap[selectedAspectRatio.value]
  if (!sizeByAspect) {
    return ''
  }

  const resolutionKey = resolutions.find(r => r.value === selectedResolution.value)?.key || '2k'
  return sizeByAspect[resolutionKey] || ''
})

const canEdit = computed(() => {
  const allRefsReady = referenceImages.value.every(img => !img.uploading)
  return imageSrc.value && prompt.value.trim() && allRefsReady
})

const showContentMaskPreview = computed(() => {
  return Boolean(props.externalMask && imageSrc.value)
})

const toggleAsync = () => {
  isAsync.value = !isAsync.value
  emit('async-change', isAsync.value)
}

const clearExternalMask = () => {
  emit('reset')
}

const getMaskImageData = () => {
  return internalMask.value || props.externalMask || null
}

const handleEdit = async () => {
  if (!canEdit.value) return

  error.value = ''

  try {
    const maskData = getMaskImageData()

    // 计算 size：Fal 模式使用 {width, height} 对象，原模式保持 "WxH" 字符串
    let sizeValue = resolvedSize.value
    if (selectedApiProvider.value === 'fal' && resolvedSize.value && resolvedSize.value !== 'auto') {
      const parts = resolvedSize.value.split('x')
      sizeValue = parts.length === 2
        ? { width: parseInt(parts[0]), height: parseInt(parts[1]) }
        : resolvedSize.value
    }

    // APIYI 视为异步执行：强制 async=true 走后台线程任务卡
    // Fal 同样强制异步；其他端口使用用户切换的状态
    const isApiyiSelected = selectedApiProvider.value === 'apiyi'
    emit('edit', {
      imageSrc: imageSrc.value,
      prompt: prompt.value,
      api_provider: selectedApiProvider.value,
      model: selectedModel.value,
      isAsync: (selectedApiProvider.value === 'fal' || isApiyiSelected) ? true : isAsync.value,
      size: sizeValue,
      quality: selectedQuality.value,
      referenceImages: referenceImages.value,
      maskImage: maskData,
      num_images: selectedApiProvider.value === 'fal' ? selectedNumImages.value : undefined,
      output_format: selectedApiProvider.value === 'fal' ? selectedOutputFormat.value : undefined
    })
  } catch (err) {
    error.value = err.message || '编辑失败，请重试'
  }
}

const handleReset = () => {
  prompt.value = ''
  error.value = ''
  selectedApiProvider.value = 'openai'
  selectedModel.value = models.value[0] || 'gpt-image-2'
  selectedAspectRatio.value = 'auto'
  selectedResolution.value = '2K'
  selectedNumImages.value = 1
  selectedOutputFormat.value = 'png'
  selectedQuality.value = 'auto'
  referenceImages.value = []
  saveEditorPrefs({ selectedApiProvider: 'openai', selectedModel: selectedModel.value })
  emit('reset')
}

const triggerReferenceUpload = () => {
  referenceInputRef.value?.click()
}

const handleReferenceDragOver = () => {
  isReferenceDragOver.value = true
}

const handleReferenceDragLeave = () => {
  isReferenceDragOver.value = false
}

const handleReferenceDrop = (event) => {
  isReferenceDragOver.value = false
  const files = Array.from(event.dataTransfer.files)
  processReferenceFiles(files)
}

const handleReferenceFileSelect = (event) => {
  const files = Array.from(event.target.files)
  processReferenceFiles(files)
  event.target.value = ''
}

// 上传参考图到文件 API 获取 HTTP URL
const uploadReferenceImage = async (base64Url) => {
  try {
    const response = await api.post('/api/files/upload-reference', {
      image: base64Url
    })
    if (response?.status === 'success' && response?.url) {
      return response.url
    }
    console.warn('[ImageEditor] 参考图上传失败:', response?.data?.message || '未知错误')
    return null
  } catch (err) {
    console.error('[ImageEditor] 参考图上传异常:', err)
    return null
  }
}

const processReferenceFiles = (files) => {
  const validTypes = ['image/jpeg', 'image/png', 'image/webp']
  const maxSize = 10 * 1024 * 1024

  files.forEach(file => {
    if (!validTypes.includes(file.type)) {
      error.value = '仅支持 JPG、PNG、WebP 格式的图片'
      return
    }
    if (file.size > maxSize) {
      error.value = '图片大小不能超过 10MB'
      return
    }

    const reader = new FileReader()
    reader.onload = async (e) => {
      const base64Url = e.target.result
      const imgEntry = {
        id: Date.now() + Math.random(),
        url: base64Url,
        name: file.name,
        size: file.size,
        uploading: true
      }
      referenceImages.value.push(imgEntry)

      // 自动上传到文件 API 获取 HTTP URL
      const uploadedUrl = await uploadReferenceImage(base64Url)
      imgEntry.url = uploadedUrl || base64Url
      imgEntry.uploaded = !!uploadedUrl
      imgEntry.uploading = false
    }
    reader.readAsDataURL(file)
  })
}

const removeReferenceImage = (index) => {
  referenceImages.value.splice(index, 1)
}

watch(() => props.submitError, (newVal) => {
  error.value = newVal || ''
}, { immediate: true })

// API 提供者变化时保存到 localStorage；APIYI 同步强制异步模式
watch(selectedApiProvider, (val) => {
  saveEditorPrefs({ selectedApiProvider: val })
  if (!models.value.includes(selectedModel.value)) {
    selectedModel.value = models.value[0] || 'gpt-image-2'
  }
  if (val === 'apiyi' && !aspectRatioOptions.value.some(option => option.value === selectedAspectRatio.value)) {
    selectedAspectRatio.value = 'auto'
  }
  // APIYI 视为异步执行：UI 隐藏切换按钮后，确保内部状态为 true
  if (val === 'apiyi') {
    isAsync.value = true
    emit('async-change', true)
  }
})

watch(selectedModel, (val) => {
  saveEditorPrefs({ selectedModel: val })
})

watch(currentResolutions, (options) => {
  if (options.length > 0 && !options.some(option => option.value === selectedResolution.value)) {
    selectedResolution.value = options[0].value
  }
})

const setImage = (src) => {
  imageSrc.value = src
}

const setMask = (maskData) => {
  internalMask.value = maskData || null
}

const clearMask = () => {
  internalMask.value = null
}

defineExpose({ 
  setImage,
  setMask,
  clearMask,
  reset: handleReset
})
</script>
