<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useImageStore } from '@/stores/imageStore'
import { useConfigStore } from '@/stores/configStore'
import { editImage, queryTask, api } from '@/services/api'
import ImageUpload from '@/components/common/ImageUpload/ImageUpload.vue'
import EditBoard from '@/components/common/EditBoard/EditBoard.vue'
import ImageSelector from '@/components/common/ImageSelector/ImageSelector.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'
import OptionDialog from '@/components/common/OptionDialog/OptionDialog.vue'
import Select from '@/components/common/Select/Select.vue'
import ImageCompare from '@/components/common/ImageCompare/ImageCompare.vue'
import SaveToLibraryDialog from '@/components/common/SaveToLibraryDialog/SaveToLibraryDialog.vue'
import ImageAnnotationModal from '@/components/ImageAnnotationModal.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import ImagePreview from '@/components/ImagePreview.vue'
import { formatApiSourceLabel } from '@/utils/platformDisplay'
import { APIYI_ASPECT_RATIO_OPTIONS, APIYI_RESOLUTIONS, resolveApiyiSize } from '@/utils/apiyiOptions'
// 引入 gpt-image-2 编辑接口的最大边长限制常量（详见 e:\AI-image\新建文件夹\修改图片.md）
// RESOLUTION_PRESETS 提供 1K / 2K / 4K 三个分辨率选项，供超限图片弹窗使用
import { GPT_IMAGE_MAX_EDGE, RESOLUTION_PRESETS, getMaxEdgeForPreset } from '@/utils/imageCompressor'

const imageStore = useImageStore()
const configStore = useConfigStore()
const router = useRouter()

const props = defineProps({
  imageId: {
    type: String,
    default: null
  }
})

const BOARD_STORAGE_KEY = 'edit_board_images'
const EDIT_VIEW_PREFS_KEY = 'edit_view_prefs'
const IMAGE_GENERATOR_PREFS_KEY = 'image_generator_prefs'

function loadEditViewPrefs() {
  try {
    const data = localStorage.getItem(EDIT_VIEW_PREFS_KEY)
    if (data) {
      return JSON.parse(data)
    }
  } catch {}
  return {}
}

function loadImageGeneratorPrefs() {
  try {
    const data = localStorage.getItem(IMAGE_GENERATOR_PREFS_KEY)
    if (data) {
      return JSON.parse(data)
    }
  } catch {}
  return {}
}

function saveEditViewPrefs(prefs) {
  try {
    const existing = loadEditViewPrefs()
    localStorage.setItem(EDIT_VIEW_PREFS_KEY, JSON.stringify({ ...existing, ...prefs }))
  } catch {}
}

const savedEditViewPrefs = loadEditViewPrefs()
const savedImageGeneratorPrefs = loadImageGeneratorPrefs()

const isAsync = ref(false)
const submitting = ref(false)
const submitError = ref('')
const initialLoading = ref(false)

const boardImages = ref([])
const selectedImageId = ref(null)
const currentEditingImage = ref(null)

const compareImage = ref(null)
const showSaveDialog = ref(false)
const savingImage = ref(null)
const showAnnotationModal = ref(false)
const annotationSaving = ref(false)
const saveNotification = ref(null)
let saveNotificationTimer = null

const showSaveNotification = (message, type = 'success') => {
  if (saveNotificationTimer) clearTimeout(saveNotificationTimer)
  saveNotification.value = { message, type }
  saveNotificationTimer = setTimeout(() => {
    saveNotification.value = null
  }, 4000)
}

const editReferenceImages = ref([])
const showEditMaterialSelector = ref(false)
const isEditRefDragOver = ref(false)
const editRefInputRef = ref(null)
const previewRefImage = ref(null)

const maxEditRefImages = computed(() => selectedApiProvider.value === 'fal' ? 4 : 16)

const editPrompt = ref('')
// 编辑指令预设片段弹窗显隐状态
const showSnippetMenu = ref(false)
// 编辑指令预设片段弹窗触发按钮的 ref，用于 click-outside 判定
const snippetMenuButtonRef = ref(null)
// 编辑指令预设片段弹窗根节点 ref
const snippetMenuPopoverRef = ref(null)
const editAspectRatio = ref('auto')
const editResolution = ref('2K')
const editQuality = ref('auto')
const editOutputFormat = ref('png')
const editOutputCompression = ref(100)
const editModeration = ref('auto')
// 当前选择的 API 提供者（openai 或 fal），从 localStorage 恢复
const selectedApiProvider = ref(savedEditViewPrefs.selectedApiProvider || 'openai')
// 当前选择的模型，从 localStorage 恢复
const selectedModel = ref(savedEditViewPrefs.selectedModel || 'gpt-image-2')
// 制作人：本地属性，保存到 images.creator，不发送到编辑 API
// 恢复顺序：currentEditingImage.creator（仅当为图库已有图片时）-> 编辑页偏好 -> 生图页偏好 -> 空字符串
const selectedCreator = ref(savedEditViewPrefs.creator || savedImageGeneratorPrefs.creator || '')
// 制作人下拉选项：从 configStore.creatorOptions.options 派生（设置页可配置）
const creatorOptions = computed(() => {
  const list = Array.isArray(configStore.creatorOptions?.options) ? configStore.creatorOptions.options : []
  return list.map((name) => ({ value: name, label: name }))
})
// 制作人筛选下拉选项：在画板工具栏使用；首项固定为「全部制作人」(value='')，
// 后续项来自 configStore.creatorOptions.options。与右侧编辑面板的 creatorOptions 区分开：
//   - 右侧编辑面板的 creatorOptions：不包含「全部」选项，用于设置新图片的 creator
//   - 画板工具栏的 filterCreatorOptions：包含「全部」选项，用于筛选显示的图片
// 两者共享 selectedCreator 状态：选「全部」时 selectedCreator 为空串，
// 过滤逻辑将空串视作"不过滤"，与生图页 ImageLibrary 的 creator 筛选行为一致
const filterCreatorOptions = computed(() => {
  return [
    { value: '', label: '全部制作人' },
    ...creatorOptions.value
  ]
})
// 按制作人筛选后的画板图片列表
// 实现逻辑：
//   1. selectedCreator 为空串时不过滤，返回完整 boardImages
//   2. selectedCreator 非空时，精确匹配每张图片的 creator 字段
//   3. 为每张图补齐默认 creator（空串），避免历史图片没有 creator 字段导致比较失败
// 边界场景：
//   - 临时图片（local/edited/pending- 前缀）若没有 creator，匹配不到任何非空筛选值，
//     用户在筛选非空制作人时不会看到这些临时图，这是符合预期的
const filteredBoardImages = computed(() => {
  const filterValue = selectedCreator.value || ''
  const source = Array.isArray(boardImages.value) ? boardImages.value : []
  if (!filterValue) return source
  return source.filter((img) => ((img && img.creator) || '') === filterValue)
})
const isGptsapiProvider = computed(() => selectedApiProvider.value === 'gptsapi')
// APIYI 也属于"仅异步"端口，gptsapi/apiyi/fal 共享比例/res 紧凑行 UI 与异步任务卡逻辑
const isApiyiProvider = computed(() => selectedApiProvider.value === 'apiyi')
const isApiyiGptImage2 = computed(() => selectedApiProvider.value === 'apiyi' && selectedModel.value.replace('apiyi/', '') === 'gpt-image-2')
const isApiyiGptImage2Vip = computed(() => selectedApiProvider.value === 'apiyi' && selectedModel.value.replace('apiyi/', '') === 'gpt-image-2-vip')
const isAsyncOnlyProvider = computed(() => isGptsapiProvider.value || isApiyiProvider.value || selectedApiProvider.value === 'fal')
const usesCompactEditSizeOptions = computed(() => isGptsapiProvider.value || (isApiyiProvider.value && !isApiyiGptImage2.value))

// 根据选择的 API 提供者返回对应的模型列表
// APIYI 固定返回带前缀的模型名，便于后端识别 apiSource 与剥离前缀
const editModels = computed(() => {
  if (selectedApiProvider.value === 'fal') {
    return ['openai/gpt-image-2']
  }
  if (selectedApiProvider.value === 'gptsapi') {
    return ['gptsapi/gpt-image-2']
  }
  if (selectedApiProvider.value === 'apiyi') {
    const configuredModels = Array.isArray(configStore.apiyiApi?.imageModels) && configStore.apiyiApi.imageModels.length > 0
      ? configStore.apiyiApi.imageModels
      : ['gpt-image-2-vip', 'gpt-image-2']
    const mergedModels = Array.from(new Set([...configuredModels, 'gpt-image-2']))
    return mergedModels.map(model => model.startsWith('apiyi/') ? model : `apiyi/${model}`)
  }
  return Array.isArray(configStore.imageApi.imageModels) && configStore.imageApi.imageModels.length > 0
    ? configStore.imageApi.imageModels
    : ['gpt-image-2']
})

const editModelOptions = computed(() => {
  return editModels.value.map((model) => ({
    value: model,
    label: model
  }))
})

// 根据是否有对应 API Key 动态生成 API 提供者选项
// 仅在用户已配置 API Key 时才显示对应端口（避免空 Key 提交失败）
const editApiProviderOptions = computed(() => {
  const options = [
    { value: 'openai', label: 'OpenAI 兼容' }
  ]
  const hasFalApiKey = configStore.falApi?.apiKey?.trim()
  if (hasFalApiKey) {
    options.push({ value: 'fal', label: 'Fal API' })
  }
  options.push({ value: 'gptsapi', label: 'GPTsAPI' })
  // APIYI 端口：仅在配置了 API Key 时显示，与 Fal 同样的策略
  const hasApiyiApiKey = configStore.apiyiApi?.apiKey?.trim()
  if (hasApiyiApiKey) {
    options.push({ value: 'apiyi', label: 'APIYI' })
  }
  return options
})

// 根据比例+分辨率查表得出实际尺寸，供画板卡片展示比例
// auto 时用 1:1 + 分辨率算出默认尺寸，确保卡片始终能正确显示比例
const resolvedEditSize = computed(() => {
  if (isApiyiProvider.value && !isApiyiGptImage2.value) {
    return resolveApiyiSize(editAspectRatio.value, editResolution.value)
  }

  const aspect = editAspectRatio.value === 'auto' ? '1:1' : editAspectRatio.value
  const key = resolutions.find(r => r.value === editResolution.value)?.key || '2k'
  return sizeMap[aspect]?.[key] || '1024x1024'
})

const showSelector = ref(false)
const showConfirmDialog = ref(false)
const confirmDialogConfig = ref({
  title: '',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  onConfirm: () => {}
})

// 超限图片压缩分辨率选择弹窗
// 字段说明：
//   visible: 是否显示弹窗
//   originalSize: 原图尺寸 { width, height }
//   pendingDecision: resolve 函数，等待用户选择后调用
//   弹窗会通过 select 事件接收分辨率值，调用 pendingDecision 唤醒 ImageUpload 的上传流程
const showResolutionDialog = ref(false)
const resolutionDialogContext = ref({
  originalSize: null,
  pendingResolve: null
})

const POLL_INTERVAL_MS = 3000
const MAX_POLL_ATTEMPTS = 1000
const MAX_POLL_TIME_MS = 3000000
const pollingIntervals = new Map()
const pollingMeta = new Map()

// 比例选项（与生图页 ImageGenerator 一致），增加 auto 作为默认
const aspectRatioOptions = [
  { value: 'auto', label: '自动' },
  { value: '1:1', label: '1:1' },
  { value: '3:2', label: '3:2' },
  { value: '2:3', label: '2:3' },
  { value: '16:9', label: '16:9' },
  { value: '9:16', label: '9:16' },
  { value: '4:3', label: '4:3' },
  { value: '3:4', label: '3:4' },
  { value: '5:4', label: '5:4' },
  { value: '4:5', label: '4:5' },
  { value: 'wechat-cover', label: '公众号封面' }
]

const gptsapiAspectRatioOptions = [
  { value: 'auto', label: '自动' },
  { value: '1:1', label: '1:1' },
  { value: '9:16', label: '9:16' },
  { value: '16:9', label: '16:9' },
  { value: '4:3', label: '4:3' },
  { value: '3:4', label: '3:4' }
]

// APIYI 也属于"仅异步"端口，gptsapi/apiyi/fal 都使用紧凑的「比例/res」布局，限制分辨率档位
const currentEditAspectRatioOptions = computed(() => {
  if (isApiyiProvider.value && !isApiyiGptImage2.value) return APIYI_ASPECT_RATIO_OPTIONS
  if (usesCompactEditSizeOptions.value) return gptsapiAspectRatioOptions
  return [...aspectRatioOptions, { value: 'fullscreen', label: '全屏' }]
})

// 分辨率选项（与生图页 ImageGenerator 一致）
const resolutions = [
  { value: '1K', label: '1K', key: '1k' },
  { value: '2K', label: '2K', key: '2k' },
  { value: '4K', label: '4K', key: '4k' }
]

const currentEditResolutions = computed(() => {
  if (isApiyiGptImage2Vip.value) {
    return []
  }
  if (isApiyiProvider.value) {
    if (isApiyiGptImage2.value) return resolutions
    return APIYI_RESOLUTIONS
  }
  if (!usesCompactEditSizeOptions.value) {
    return resolutions
  }
  if (editAspectRatio.value === 'auto') {
    return resolutions.filter(resolution => resolution.value === '1K')
  }
  if (editAspectRatio.value === '1:1') {
    return resolutions.filter(resolution => resolution.value !== '4K')
  }
  return resolutions
})

// 尺寸映射表（与生图页 ImageGenerator 一致）
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
  'wechat-cover': { '1k': '1456x624', '2k': '1456x624', '4k': '1456x624' },
  'fullscreen': { '1k': '688x1488', '2k': '1072x2336', '4k': '1760x3840' }
}

const qualityOptions = [
  { value: 'auto', label: '自动' },
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' }
]

const outputFormatOptions = [
  { value: 'png', label: 'PNG' },
  { value: 'jpeg', label: 'JPEG' },
  { value: 'webp', label: 'WebP' }
]

const moderationOptions = [
  { value: 'auto', label: 'Auto' },
  { value: 'low', label: 'Low' }
]

// 当前编辑图片，直接返回 currentEditingImage
const selectedImage = computed(() => {
  return currentEditingImage.value
})

const getNextEditPrompt = (basePrompt = '', editInstruction = '') => {
  const base = (basePrompt || '').trim()
  const instruction = (editInstruction || '').trim()
  const matches = [...base.matchAll(/编辑(\d+)次/g)].map(match => Number(match[1])).filter(Number.isFinite)
  const nextCount = matches.length > 0 ? Math.max(...matches) + 1 : 1
  return [base, `编辑${nextCount}次`, instruction].filter(Boolean).join('\n')
}

const hasEditHistory = (text = '') => /编辑\d+次/.test(text || '')

const getPreparationCopyText = (image = {}) => {
  const currentPrompt = image.prompt || ''
  if (hasEditHistory(currentPrompt)) {
    return currentPrompt
  }
  const basePrompt = image.originalImage?.prompt || image._original?.prompt || ''
  return basePrompt ? getNextEditPrompt(basePrompt, currentPrompt) : currentPrompt
}

const getImagePosterCopy = (image = {}) => (
  image.poster_copy ||
  image.posterCopy ||
  image.originalImage?.poster_copy ||
  image.originalImage?.posterCopy ||
  image._original?.poster_copy ||
  ''
)

// 保存画板数据到 localStorage
const saveBoardToStorage = () => {
  try {
    const data = boardImages.value.map(img => ({
      id: img.id,
      url: img.url,
      thumbnail: img.thumbnail,
      prompt: img.prompt,
      poster_copy: img.poster_copy || '',
      // 制作人：缓存到 localStorage，避免刷新后筛选失效
      creator: img.creator || '',
      generating: img.generating,
      error: img.error,
      taskId: img.taskId,
      parentId: img.parentId,
      isLocal: img.isLocal,
      size: img.size,
      aspect_ratio: img.aspect_ratio,
      apiSource: img.apiSource,
      originalImage: img.originalImage ? {
        id: img.originalImage.id,
        url: img.originalImage.url,
        thumbnail: img.originalImage.thumbnail,
        prompt: img.originalImage.prompt,
        poster_copy: img.originalImage.poster_copy || ''
      } : null
    }))
    localStorage.setItem(BOARD_STORAGE_KEY, JSON.stringify(data))
  } catch (e) {
    console.error('保存画板数据失败:', e)
  }
}

// 从 localStorage 恢复画板数据（用作快速初始展示，稍后会被 API 数据覆盖）
const loadBoardFromStorage = () => {
  try {
    const data = localStorage.getItem(BOARD_STORAGE_KEY)
    if (data) {
      const parsed = JSON.parse(data)
      if (Array.isArray(parsed) && parsed.length > 0) {
        boardImages.value = parsed.filter(img => {
          if (!img.generating) return true
          return !!img.taskId
        })
      }
    }
  } catch (e) {
    console.error('加载画板缓存数据失败:', e)
  }
}

// 从后端数据库加载编辑图片列表并恢复画板
const fetchEditImages = async () => {
  try {
    const response = await fetch('/api/images?image_type=edit')
    const data = await response.json()
    if (data.status === 'success' && Array.isArray(data.images) && data.images.length > 0) {
      let images = data.images.map(img => ({
        id: img.id,
        url: img.display_url || img.url || '',
        thumbnail: img.thumbnail || img.display_url || img.url || '',
        prompt: img.prompt || img.title || '',
        poster_copy: img.poster_copy || '',
        // 制作人：从 images.creator 字段读取，供画板工具栏筛选使用
        // 后端 serialize_image 通过 dict(image_item.__dict__) 输出该字段
        creator: img.creator || '',
        generating: !!img.generating,
        error: img.error || '',
        taskId: img.taskId || null,
        parentId: img.parent_id || null,
        isLocal: !!img.local_path,
        size: img.size || null,
        aspect_ratio: img.aspect_ratio || null,
        apiSource: img.apiSource || 'openai'
      }))

      // 补充 originalImage：从缓存+API 查找父图信息
      const parentIds = [...new Set(images.filter(i => i.parentId).map(i => i.parentId))]
      const cached = JSON.parse(localStorage.getItem(BOARD_STORAGE_KEY) || '[]')
      if (parentIds.length > 0) {
        const parentMap = {}
        // 先查 localStorage 缓存
        for (const c of cached) {
          if (c.originalImage) parentMap[c.parentId] = c.originalImage
          parentMap[c.id] = { id: c.id, url: c.url, thumbnail: c.thumbnail, prompt: c.prompt, poster_copy: c.poster_copy || '' }
        }
        // 缓存中没有的从 API 获取
        for (const pid of parentIds) {
          if (!parentMap[pid]) {
            // 跳过临时 ID（local-/edited-/pending-），这些不是数据库记录，无法通过 API 查找
            if (pid.startsWith('local-') || pid.startsWith('edited-') || pid.startsWith('pending-')) {
              continue
            }
            try {
              const pr = await fetch(`/api/images/${pid}`)
              const pd = await pr.json()
              if (pd.status === 'success' && pd.image) {
                parentMap[pid] = {
                  id: pd.image.id,
                  url: pd.image.display_url || pd.image.url,
                  thumbnail: pd.image.thumbnail || pd.image.url,
                  prompt: pd.image.prompt || '',
                  poster_copy: pd.image.poster_copy || ''
                }
              }
            } catch { /* skip */ }
          }
        }
        images = images.map(img => ({
          ...img,
          originalImage: img.parentId ? (parentMap[img.parentId] || null) : null
        }))
      }

      // 回退：对于仍无 originalImage 的图片，从缓存中按 id 匹配补充
      for (const img of images) {
        if (!img.originalImage) {
          const cachedMatch = cached.find(c => c.id === img.id && c.originalImage)
          if (cachedMatch) {
            img.originalImage = cachedMatch.originalImage
          }
        }
      }

      // 修正无有效尺寸的图片：从缩略图加载真实宽高
      for (const img of images) {
        const hasValidSize = img.size && typeof img.size === 'string' && img.size.includes('x')
        if (!hasValidSize && (img.thumbnail || img.url)) {
          try {
            const testImg = new Image()
            const src = img.thumbnail || img.url
            await new Promise((resolve) => { testImg.onload = resolve; testImg.onerror = resolve; testImg.src = src })
            if (testImg.naturalWidth && testImg.naturalHeight) {
              img.size = `${testImg.naturalWidth}x${testImg.naturalHeight}`
            }
          } catch { /* skip */ }
        }
      }

      // 将 API 数据合并到现有 boardImages 中，而非全量替换
      // 这样已缓存的 <img> 元素（:key="image.id"）不会被销毁重建
      // 避免进行中的图片请求被浏览器中断（ERR_ABORTED）
      for (const newImg of images) {
        const existingIndex = boardImages.value.findIndex(i => i.id === newImg.id)
        if (existingIndex >= 0) {
          boardImages.value[existingIndex] = { ...boardImages.value[existingIndex], ...newImg }
        } else {
          boardImages.value.push(newImg)
        }
      }
      saveBoardToStorage()

      // 恢复轮询：对刷新前正在生成中的图片重新启动状态轮询
      for (const img of images) {
        if (img.generating && img.taskId) {
          startPolling(img.taskId, img.id)
        }
      }
    }
  } catch (e) {
    console.error('加载编辑图片列表失败:', e)
  }
}

const handleUploadComplete = (imageData) => {
  if (imageData?.url) {
    editReferenceImages.value = []
    currentEditingImage.value = {
      id: imageData.id || `local-${Date.now()}`,
      url: imageData.url,
      thumbnail: imageData.thumbnail || imageData.url,
      prompt: imageData.prompt || '新上传图片',
      poster_copy: imageData.poster_copy || ''
    }
  }
}

const handleFileSelected = (file) => {
  console.log('File selected for editing:', file.name)
}

// 图片上传触发自动压缩后的回调：用于向用户提示「原图分辨率过高，已自动压缩」
// 实现逻辑：
//   1. 从事件 payload 中拿到原图尺寸 / 压缩后尺寸 / 最大边长
//   2. 复用页面现有的 toast 通知，提示压缩结果
//   3. 任何字段缺失时仍提示成功压缩，避免 UI 出现空白文案
const handleUploadCompressed = (info) => {
  if (!info || !info.compressed) return
  const { originalSize, newSize, maxEdge } = info
  const original = originalSize ? `${originalSize.width}x${originalSize.height}` : '未知'
  const next = newSize ? `${newSize.width}x${newSize.height}` : `≤${maxEdge}px`
  showSaveNotification(`图片分辨率超过限制，已自动压缩：${original} → ${next}`, 'success')
}

// 图片分辨率超过 maxEdge 时由 ImageUpload 调用的回调
// 实现逻辑：
//   1. 把 originalSize 写入 context，弹出分辨率选择弹窗
//   2. 返回 Promise，等待用户在弹窗里选择 1K / 2K / 4K / 取消
//   3. 用户选择分辨率 → resolve({ maxEdge })
//   4. 用户选择「取消」/ 关闭弹窗 → resolve({ abort: true })
//   5. 任何异常都通过 catch 兜底，回退到默认 maxEdge 自动压缩
const handleUploadOversize = ({ originalSize, defaultMaxEdge }) => {
  return new Promise((resolve) => {
    resolutionDialogContext.value = {
      originalSize,
      pendingResolve: resolve
    }
    showResolutionDialog.value = true
  })
}

// 分辨率选择弹窗：用户点选某个选项
// 实现逻辑：
//   1. 从 value (1K/2K/4K) 找到对应 maxEdge
//   2. 唤醒 pendingResolve，把决策交给 ImageUpload
//   3. 清空弹窗 context，关闭弹窗
const handleResolutionSelect = (value) => {
  const maxEdge = getMaxEdgeForPreset(value, GPT_IMAGE_MAX_EDGE)
  const resolve = resolutionDialogContext.value.pendingResolve
  if (typeof resolve === 'function') {
    resolve({ maxEdge })
  }
  resolutionDialogContext.value = { originalSize: null, pendingResolve: null }
  showResolutionDialog.value = false
}

// 分辨率选择弹窗：用户选择「取消」/ 关闭 / Esc / 点击遮罩
// 实现逻辑：把 abort 决策交给 ImageUpload，由组件清空进度且不上传
const handleResolutionCancel = () => {
  const resolve = resolutionDialogContext.value.pendingResolve
  if (typeof resolve === 'function') {
    resolve({ abort: true })
  }
  resolutionDialogContext.value = { originalSize: null, pendingResolve: null }
  showResolutionDialog.value = false
}

// 弹窗标题 / 描述：根据原图尺寸动态生成
// 实现逻辑：
//   1. 提示用户当前图片超出 gpt-image-2 编辑接口上限
//   2. 给出原图尺寸 + 接口上限 3840px
//   3. options 直接复用 RESOLUTION_PRESETS（imageCompressor 导出）
const resolutionDialogMessage = computed(() => {
  const size = resolutionDialogContext.value.originalSize
  const sizeText = size ? `${size.width} × ${size.height} px` : '当前分辨率过高'
  return `${sizeText}，超过 gpt-image-2 编辑接口的最大边长 ${GPT_IMAGE_MAX_EDGE}px。请选择压缩目标分辨率：`
})

const resolutionDialogOptions = RESOLUTION_PRESETS.map((preset) => ({
  value: preset.value,
  label: preset.label,
  description: preset.description
}))

const addImageToBoard = (image) => {
  boardImages.value.unshift(image)
  selectedImageId.value = image.id
  currentEditingImage.value = image
  saveBoardToStorage()
}

// 点击画板图片 → 打开对比预览（无原图时只展示新图）
const handleBoardCompare = (image) => {
  if (image.generating) return
  const original = image.originalImage || null
  compareImage.value = { new: image, original }
}

// 画板 hover 编辑按钮 → 设为当前编辑图
const handleBoardEdit = (image) => {
  editReferenceImages.value = []
  currentEditingImage.value = { ...image }
  if (image.originalImage) {
    currentEditingImage.value._original = image.originalImage
  }
  showAnnotationModal.value = false
}

// 画板 hover 删除按钮 → 确认删除（同步删除数据库记录）
const handleBoardDelete = (image) => {
  openConfirmDialog({
    title: '确认删除',
    message: '确定要删除这张编辑结果图片吗？',
    confirmText: '删除',
    cancelText: '取消',
    danger: true,
    onConfirm: async () => {
      if (image.taskId) stopPolling(image.taskId)
      // 跳过临时 ID（local-/edited-/pending-），这些不是数据库记录，无需向后端发送 DELETE
      const isTempId = image.id && (image.id.startsWith('local-') || image.id.startsWith('edited-') || image.id.startsWith('pending-'))
      if (!isTempId) {
        try {
          await fetch(`/api/images/${image.id}`, { method: 'DELETE' })
        } catch (e) {
          console.error('删除数据库图片失败:', image.id, e)
        }
      }
      const index = boardImages.value.findIndex(img => img.id === image.id)
      if (index !== -1) boardImages.value.splice(index, 1)
      saveBoardToStorage()
      if (selectedImageId.value === image.id) {
        selectedImageId.value = boardImages.value.length > 0 ? boardImages.value[0].id : null
      }
    }
  })
}

// 失败任务重试（仅 APIYI）
// 功能描述：
//     调后端 /api/images/apiyi/retry 把失败的 task 重新提交；后端校验通过后
//     会把 image 状态翻回 generating 并启动新一轮轮询
// 实现逻辑：
//     1. 校验 image.apiSource === 'apiyi' 且有 taskId
//     2. POST { task_id } 到重试接口
//     3. ok=true：把 image.error 清空、generating=true，调用 startPolling 重新轮询
//     4. ok=false：弹 confirmDialog 展示 error_code + error，提示用户重新提交
// 异常处理：网络/JSON 解析异常时弹 confirmDialog 提示；不动 image 状态
const handleBoardRetry = async (image) => {
  if (!image || !image.taskId) {
    openConfirmDialog({
      title: '重试失败',
      message: '该任务没有 taskId，无法重试',
      confirmText: '知道了',
      cancelText: '关闭',
      danger: false,
      onConfirm: () => {}
    })
    return
  }
  if (image.apiSource !== 'apiyi') {
    openConfirmDialog({
      title: '暂不支持',
      message: '当前仅 APIYI 平台支持失败任务重试',
      confirmText: '知道了',
      cancelText: '关闭',
      danger: false,
      onConfirm: () => {}
    })
    return
  }
  try {
    const resp = await fetch('/api/images/apiyi/retry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: image.taskId })
    })
    const data = await resp.json().catch(() => ({}))
    if (resp.ok && data.ok) {
      // 重置为生成中，让 EditBoard 显示 generating overlay，重新开始轮询
      Object.assign(image, {
        generating: true,
        error: '',
        retryCount: data.retry_count || (image.retryCount || 0) + 1
      })
      saveBoardToStorage()
      startPolling(image.taskId, image.id)
      return
    }
    // 失败时弹 confirmDialog 提示
    const errCode = data.error_code || 'unknown'
    const errMsg = data.error || `重试请求失败 (HTTP ${resp.status})`
    const hint = errCode === 'temp_files_missing'
      ? '临时文件已失效，请直接重新提交编辑任务'
      : errCode === 'image_missing'
        ? '图片记录已不存在，请重新提交'
        : errCode === 'status_not_failure'
          ? '该任务状态已变化，请刷新页面查看'
          : errMsg
    openConfirmDialog({
      title: '重试失败',
      message: `${hint}\n\n错误码：${errCode}`,
      confirmText: '重新提交',
      cancelText: '关闭',
      danger: false,
      onConfirm: () => {
        // 重新提交：把 image 从 board 移除（用户回到编辑面板手动重提）
        const index = boardImages.value.findIndex(img => img.id === image.id)
        if (index !== -1) boardImages.value.splice(index, 1)
        saveBoardToStorage()
      }
    })
  } catch (err) {
    openConfirmDialog({
      title: '重试异常',
      message: `网络异常：${err.message || err}`,
      confirmText: '知道了',
      cancelText: '关闭',
      danger: false,
      onConfirm: () => {}
    })
  }
}

// 批量删除（同步删除数据库记录）
const handleBatchDelete = (images) => {
  openConfirmDialog({
    title: `确认删除 (${images.length} 张)`,
    message: `确定要删除选中的 ${images.length} 张图片吗？`,
    confirmText: '删除',
    cancelText: '取消',
    danger: true,
    onConfirm: async () => {
      for (const img of images) {
        if (img.taskId) stopPolling(img.taskId)
        // 跳过临时 ID（local-/edited-/pending-），这些不是数据库记录，无需向后端发送 DELETE
        const isTempId = img.id && (img.id.startsWith('local-') || img.id.startsWith('edited-') || img.id.startsWith('pending-'))
        if (!isTempId) {
          try {
            await fetch(`/api/images/${img.id}`, { method: 'DELETE' })
          } catch (e) {
            console.error('批量删除数据库图片失败:', img.id, e)
          }
        }
      }
      const ids = new Set(images.map(img => img.id))
      boardImages.value = boardImages.value.filter(bi => !ids.has(bi.id))
      if (ids.has(selectedImageId.value)) {
        selectedImageId.value = boardImages.value.length > 0 ? boardImages.value[0].id : null
      }
      saveBoardToStorage()
    }
  })
}

// 批量保存到素材库
const handleBatchSave = (images) => {
  savingImage.value = images
  showSaveDialog.value = true
}

// 画板 hover 保存按钮 → 单张保存
const handleBoardSave = (image) => {
  savingImage.value = image
  showSaveDialog.value = true
}

// 画板 hover 下载按钮 → 下载原图到本地计算机
const handleBoardDownload = (image) => {
  if (!image?.url) {
    showSaveNotification('没有可下载的图片', 'error')
    return
  }

  const imageUrl = image.url.startsWith('http') ? image.url : window.location.origin + image.url
  const filename = (image.prompt ? image.prompt.slice(0, 30) : 'edit_image').replace(/[\\/:*?"<>|]/g, '_') + '.png'

  fetch(imageUrl)
    .then(response => {
      if (!response.ok) throw new Error('下载失败')
      return response.blob()
    })
    .then(blob => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      showSaveNotification(`已下载: ${filename}`, 'success')
    })
    .catch(err => {
      showSaveNotification('下载失败: ' + err.message, 'error')
    })
}

// 保存到图片库完成回调
const handleSavedToLibrary = () => {
  showSaveDialog.value = false
  savingImage.value = null
  showSaveNotification('已保存到图片库', 'success')
}

const handleAddToPreparation = (image) => {
  const imageUrl = image.url || image.thumbnail || ''
  if (!imageUrl) return
  openConfirmDialog({
    title: '确认添加',
    message: '确定要将此图片添加到预备目录吗？',
    confirmText: '确定',
    cancelText: '取消',
    onConfirm: async () => {
      const displayName = image.title || image.display_name || image.prompt?.slice(0, 30) || ''
      const platform = formatApiSourceLabel(image.apiSource)
      const copyText = getPreparationCopyText(image)
      const posterCopy = getImagePosterCopy(image)
      // 制作人：随图片一起透传到后端，保存到 preparation_items.creator
      const creatorValue = (selectedCreator.value || '').trim()
      try {
        await api.post('/api/preparation/copy-from', {
          image_url: imageUrl,
          display_name: displayName,
          platform: platform,
          copy_text: copyText,
          poster_copy: posterCopy,
          creator: creatorValue
        })
        showSaveNotification('已添加到预备目录', 'success')
      } catch (e) {
        showSaveNotification('添加到预备目录失败', 'error')
      }
    }
  })
}

const handleAddToGeo = (image) => {
  const imageUrl = image.url || image.thumbnail || ''
  if (!imageUrl) return
  openConfirmDialog({
    title: '确认添加',
    message: '确定要将此图片添加到GEO目录吗？',
    confirmText: '确定',
    cancelText: '取消',
    onConfirm: async () => {
      const displayName = image.title || image.display_name || image.prompt?.slice(0, 30) || ''
      const platform = formatApiSourceLabel(image.apiSource)
      const copyText = getPreparationCopyText(image)
      const posterCopy = image.poster_copy || ''
      // 制作人：随图片一起透传到后端，保存到 geo_items.creator
      const creatorValue = (selectedCreator.value || '').trim()
      try {
        await api.post('/api/geo/copy-from', {
          image_url: imageUrl,
          display_name: displayName,
          platform: platform,
          copy_text: copyText,
          poster_copy: posterCopy,
          creator: creatorValue
        })
        showSaveNotification('已添加到GEO目录', 'success')
        router.push('/geo')
      } catch (e) {
        showSaveNotification('添加到GEO目录失败', 'error')
      }
    }
  })
}

const handleOpenSelector = () => {
  showSelector.value = true
}

const handleSelectFromLibrary = (image) => {
  editReferenceImages.value = []
  currentEditingImage.value = {
    id: image.id,
    url: image.url,
    thumbnail: image.thumbnail || image.url,
    prompt: image.prompt || image.title || '已选择图片',
    poster_copy: image.poster_copy || '',
    // 制作人：从图库选中的图片保留原 creator，用于右侧编辑面板的初始值
    // 当用户后续点击「开始编辑」时，watch(currentEditingImage) 会用此值覆盖 selectedCreator
    creator: image.creator || ''
  }
  showSelector.value = false
}

const handleOpenAnnotationModal = () => {
  if (!currentEditingImage.value?.url) {
    return
  }

  showAnnotationModal.value = true
}

const handleAnnotationClose = () => {
  showAnnotationModal.value = false
  annotationSaving.value = false
}

const handleCloseEditor = () => {
  currentEditingImage.value = null
  editReferenceImages.value = []
}

// 上传参考图到文件服务

const uploadEditRefImage = async (base64Url) => {
  try {
    const response = await api.post('/api/files/upload-reference', { image: base64Url })
    if (response?.status === 'success' && response?.url) {
      return response.url
    }
    return null
  } catch (err) {
    console.error('[EditView] 参考图上传异常:', err)
    return null
  }
}

const processEditRefFiles = (files) => {
  const validTypes = ['image/jpeg', 'image/png', 'image/webp']
  files.forEach(file => {
    if (!validTypes.includes(file.type) || file.size > 10 * 1024 * 1024) return
    if (editReferenceImages.value.length >= maxEditRefImages.value) return

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
      editReferenceImages.value.push(imgEntry)
      const uploadedUrl = await uploadEditRefImage(base64Url)
      imgEntry.url = uploadedUrl || base64Url
      imgEntry.uploaded = !!uploadedUrl
      imgEntry.uploading = false
    }
    reader.readAsDataURL(file)
  })
}

const handleEditRefDrop = (e) => processEditRefFiles(Array.from(e.dataTransfer.files))
const handleEditRefFileSelect = (e) => {
  processEditRefFiles(Array.from(e.target.files))
  e.target.value = ''
}
const triggerEditRefUpload = () => editRefInputRef.value?.click()
const removeEditRefImage = (index) => editReferenceImages.value.splice(index, 1)
const handlePreviewRefImage = (url) => {
  previewRefImage.value = { url }
}

const handleEditMaterialSelect = async (materials) => {
  for (const material of materials) {
    if (editReferenceImages.value.length >= maxEditRefImages.value) break
    if (material.manual_url) {
      // 优先使用手动填写的 URL，无需上传
      const imgEntry = {
        id: Date.now() + Math.random(),
        url: material.manual_url,
        name: material.filename || 'material',
        size: material.size || 0,
        uploaded: true,
        uploading: false
      }
      editReferenceImages.value.push(imgEntry)
    } else {
      // 没有 manual_url，走原有的获取+上传流程
      try {
        const url = material.folder
          ? `/api/static/material/${encodeURIComponent(material.folder)}/${encodeURIComponent(material.filename)}`
          : `/api/static/material/${encodeURIComponent(material.filename)}`
        const response = await fetch(url)
        if (!response.ok) continue
        const blob = await response.blob()
        const base64Url = await new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result)
          reader.onerror = reject
          reader.readAsDataURL(blob)
        })
        const imgEntry = {
          id: Date.now() + Math.random(),
          url: base64Url,
          name: material.filename || 'material',
          size: blob.size,
          uploading: true
        }
        editReferenceImages.value.push(imgEntry)
        const uploadedUrl = await uploadEditRefImage(base64Url)
        imgEntry.url = uploadedUrl || base64Url
        imgEntry.uploaded = !!uploadedUrl
        imgEntry.uploading = false
      } catch (e) {
        console.error('[EditView] 素材加载失败:', e)
      }
    }
  }
}

const handleAnnotationSave = async (data) => {
  if (!currentEditingImage.value || !data) {
    showAnnotationModal.value = false
    return
  }

  const update = { ...currentEditingImage.value }

  if (data.annotatedImage) {
    annotationSaving.value = true
    update.annotatedPreview = data.annotatedImage
    try {
      const uploadResult = await api.post('/api/files/upload-reference', {
        image: data.annotatedImage
      })
      if (uploadResult?.status === 'success' && uploadResult?.url) {
        update.annotatedUrl = uploadResult.url
        showSaveNotification('标注图已上传成功')
      } else {
        update.annotatedUrl = data.annotatedImage
        showSaveNotification('标注图上传失败，已使用本地数据', 'warning')
      }
    } catch (e) {
      console.error('[EditView] 标注图上传失败:', e)
      update.annotatedUrl = data.annotatedImage
      showSaveNotification('标注图上传异常，已使用本地数据', 'error')
    } finally {
      annotationSaving.value = false
    }
  }

  if (data.maskImage) {
    update.maskImage = data.maskImage
    update.maskPreview = data.maskImage
    showSaveNotification('遮罩图已保存')
  }

  currentEditingImage.value = update
  showAnnotationModal.value = false
}

const toggleAsync = () => {
  isAsync.value = !isAsync.value
}

// 切换预设片段弹窗显示状态
const toggleSnippetMenu = () => {
  showSnippetMenu.value = !showSnippetMenu.value
}

// 关闭预设片段弹窗
const closeSnippetMenu = () => {
  showSnippetMenu.value = false
}

// 将选中片段的 content 追加到 editPrompt 末尾
// 实现逻辑：
//   1. 若 editPrompt 已存在非空内容，前置换行以确保与原文分隔
//   2. textarea 自身的 maxlength=1000 负责最终截断（提示用户追加后可能超长）
//   3. 追加完成后弹窗自动关闭，光标自动聚焦到 textarea
const appendSnippetToPrompt = (snippet) => {
  if (!snippet || typeof snippet.content !== 'string') return
  const content = snippet.content
  if (editPrompt.value && editPrompt.value.trim().length > 0) {
    // 已存在内容：换行 + 片段内容
    editPrompt.value = editPrompt.value.replace(/\s*$/, '') + '\n' + content
  } else {
    editPrompt.value = content
  }
  closeSnippetMenu()
  // 焦点回到 textarea（nextTick 确保弹窗已关闭再聚焦）
  nextTick(() => {
    const ta = document.querySelector('.edit-view__textarea')
    if (ta) {
      ta.focus()
      // 把光标移到末尾
      const len = editPrompt.value.length
      ta.setSelectionRange(len, len)
    }
  })
}

// 全局 mousedown 监听：点击片段按钮 / popover 外部时关闭 popover
// 兜底逻辑：同时考虑 mousedown 阶段关闭，避免与按钮 click 事件竞态
const handleDocumentMouseDown = (event) => {
  if (!showSnippetMenu.value) return
  const target = event.target
  const buttonEl = snippetMenuButtonRef.value
  const popoverEl = snippetMenuPopoverRef.value
  const inButton = buttonEl && (buttonEl === target || buttonEl.contains(target))
  const inPopover = popoverEl && (popoverEl === target || popoverEl.contains(target))
  if (!inButton && !inPopover) {
    closeSnippetMenu()
  }
}

const handleEditSubmit = async () => {
  if (!currentEditingImage.value) {
    submitError.value = '请先选择要编辑的图片'
    return
  }
  if (!editPrompt.value.trim()) {
    submitError.value = '请输入编辑指令'
    return
  }

  const sourceImage = currentEditingImage.value

  submitting.value = true
  submitError.value = ''

  try {
    // 判断使用哪种源图：
    // 1. 标注模式：用户圈出了需要修改的位置 → 使用 annotatedUrl（标注合并后的图片）作为源图
    // 2. 遮罩模式：用户涂抹了遮罩 → 使用原始图片作为源图，遮罩图额外传输
    // 3. 无标注无遮罩：使用原始图片
    const useAnnotated = !!sourceImage.annotatedUrl && !sourceImage.maskImage
    const sourceUrl = useAnnotated ? sourceImage.annotatedUrl : sourceImage.url

    if (!sourceUrl) {
      submitError.value = '无法获取源图，请重新选择图片'
      submitting.value = false
      return
    }

    const response = await fetch(sourceUrl)
    if (!response.ok) {
      throw new Error('获取图片失败')
    }
    const blob = await response.blob()
    const file = new File([blob], 'edit-image.png', { type: 'image/png' })

    // 获取原图实际尺寸，用于画板卡片正确展示比例
    let sourceSize = resolvedEditSize.value
    try {
      const img = new Image()
      const objectUrl = URL.createObjectURL(blob)
      await new Promise((resolve) => { img.onload = resolve; img.onerror = resolve; img.src = objectUrl })
      if (img.naturalWidth && img.naturalHeight) {
        sourceSize = `${img.naturalWidth}x${img.naturalHeight}`
      }
      URL.revokeObjectURL(objectUrl)
    } catch { /* 失败时沿用 resolvedEditSize */ }

    const formData = new FormData()
    formData.append('image', file)  // 主图

    // 参考图作为额外的 image 字段添加到 FormData
    console.log(`[EditView] 参考图数量: ${editReferenceImages.value.length}, 详情:`, editReferenceImages.value.map(r => ({ id: r.id, url: r.url?.slice(0, 50), uploaded: r.uploaded, uploading: r.uploading })))
    let refAddedCount = 0
    const refUrlFallbackList = []
    // _ref_image_urls 仅 Fal 编辑通道使用（见 routes/images.py 第 2626 行）
    // APIYI / gptsapi / openai 通道后端未读取此字段，避免无效负载
    const supportsRefUrlFallback = selectedApiProvider.value === 'fal'
    for (const refImg of editReferenceImages.value) {
      try {
        const refResp = await fetch(refImg.url)
        if (!refResp.ok) continue
        const refBlob = await refResp.blob()
        const refFile = new File([refBlob], refImg.name || 'ref.png', { type: 'image/png' })
        formData.append('image', refFile)
        refAddedCount++
      } catch (e) {
        if (supportsRefUrlFallback) {
          // CORS 限制时无法通过 fetch 获取图片，将 URL 发给后端处理
          console.warn('[EditView] 参考图 fetch 失败，改用 URL 方式:', refImg.url?.slice(0, 80), e)
          refUrlFallbackList.push(refImg.url)
        } else {
          // APIYI / openai / gptsapi 不支持 URL fallback，记录后跳过
          console.warn('[EditView] 参考图 fetch 失败且当前通道不支持 URL fallback，跳过:', refImg.url?.slice(0, 80), e)
        }
      }
    }
    if (refUrlFallbackList.length > 0) {
      formData.append('_ref_image_urls', JSON.stringify(refUrlFallbackList))
      refAddedCount += refUrlFallbackList.length
    }
    // _diagnostic_ref_count 仅用于后端 print 日志（routes/images.py:2312），APIYI 通道无意义
    if (selectedApiProvider.value !== 'apiyi') {
      formData.append('_diagnostic_ref_count', String(refAddedCount))
    }

    formData.append('prompt', editPrompt.value)
    formData.append('model', selectedModel.value)
    formData.append('api_provider', selectedApiProvider.value)
    if (sourceImage.id) formData.append('parent_id', sourceImage.id)
    // 制作人：本地属性，作为图片元数据保存到 images.creator（后端 images.py 已读取 data.get('creator')）
    formData.append('creator', selectedCreator.value || '')

    // 如果有遮罩，转换为文件并添加到请求
    // APIYI 不支持 mask（详见 e:\AI-image\新建文件夹\apiyi\图片编辑.md，文档未列出该字段），避免无效负载
    // 其他通道（openai/fal/gptsapi）保留 mask 上传
    if (sourceImage.maskImage && (selectedApiProvider.value !== 'apiyi' || isApiyiGptImage2.value)) {
      const maskBlob = dataURItoBlob(sourceImage.maskImage)
      if (maskBlob) {
        const maskFile = new File([maskBlob], 'mask.png', { type: 'image/png' })
        formData.append('mask', maskFile)
      }
    }
    // 当 aspect ratio 为 auto 时，使用源图的实际尺寸发送给后端
    const editSize = selectedApiProvider.value === 'apiyi' && !isApiyiGptImage2.value
      ? resolvedEditSize.value
      : (editAspectRatio.value === 'auto' ? sourceSize : resolvedEditSize.value)
    formData.append('size', editSize)

    if (selectedApiProvider.value === 'gptsapi') {
      formData.append('aspect_ratio', editAspectRatio.value)
      formData.append('resolution', editResolution.value)
    } else if (selectedApiProvider.value === 'apiyi') {
      if (isApiyiGptImage2.value) {
        formData.append('background', 'auto')
        formData.append('moderation', editModeration.value)
        formData.append('quality', editQuality.value)
        formData.append('output_format', editOutputFormat.value)
        if (editOutputFormat.value === 'jpeg' || editOutputFormat.value === 'webp') {
          formData.append('output_compression', editOutputCompression.value)
        }
      }
    } else {
      if (editQuality.value !== 'auto') formData.append('quality', editQuality.value)
      if (editOutputFormat.value !== 'png') formData.append('output_format', editOutputFormat.value)
      if (editOutputCompression.value !== 100 && (editOutputFormat.value === 'jpeg' || editOutputFormat.value === 'webp')) {
        formData.append('output_compression', editOutputCompression.value)
      }
    }

    const effectiveAsync = (selectedApiProvider.value === 'fal' || selectedApiProvider.value === 'apiyi')
      ? true
      : isAsync.value
    const result = await editImage(formData, effectiveAsync)

    if (effectiveAsync) {
      if (!result?.task_id) {
        throw new Error('异步编辑提交成功但未返回 task_id')
      }

      const newImage = {
        id: result.image?.id || `pending-${Date.now()}`,
        url: result.image?.display_url || '',
        thumbnail: result.image?.thumbnail || '',
        prompt: result.image?.prompt || getNextEditPrompt(sourceImage.prompt, editPrompt.value),
        poster_copy: result.image?.poster_copy || getImagePosterCopy(sourceImage),
        // 制作人：随编辑请求提交到后端（后端 edit_image 已读取 formData.creator 写入 images.creator），
        // 此处保存到前端 boardImages 是为了让画板筛选立刻生效，无需等待后端轮询
        // 回退顺序：后端返回的 creator（异步任务可能未落库）-> selectedCreator -> 源图 creator
        creator: (result.image?.creator || selectedCreator.value || sourceImage.creator || '').trim(),
        size: editSize,
        generating: true,
        error: '',
        taskId: result.task_id,
        parentId: sourceImage.id,
        isLocal: false,
        apiSource: selectedApiProvider.value,
        originalImage: {
          id: sourceImage.id,
          url: sourceImage.url,
          thumbnail: sourceImage.thumbnail,
          prompt: sourceImage.prompt,
          poster_copy: getImagePosterCopy(sourceImage)
        }
      }

      boardImages.value.unshift(newImage)
      selectedImageId.value = newImage.id
      saveBoardToStorage()
      startPolling(result.task_id, newImage.id)
    } else {
      const resultSize = result.image?.size || sourceSize
      const newImage = {
        id: result.image?.id || `edited-${Date.now()}`,
        url: result.image?.display_url || result.image?.url || sourceImage.url,
        thumbnail: result.image?.thumbnail || result.image?.display_url || result.image?.url || '',
        prompt: result.image?.prompt || getNextEditPrompt(sourceImage.prompt, editPrompt.value),
        poster_copy: result.image?.poster_copy || getImagePosterCopy(sourceImage),
        // 制作人：回退到后端返回的 creator -> selectedCreator -> 源图 creator，确保画板筛选可用
        creator: (result.image?.creator || selectedCreator.value || sourceImage.creator || '').trim(),
        size: resultSize,
        generating: false,
        error: '',
        taskId: null,
        parentId: sourceImage.id,
        isLocal: false,
        apiSource: selectedApiProvider.value,
        originalImage: {
          id: sourceImage.id,
          url: sourceImage.url,
          thumbnail: sourceImage.thumbnail,
          prompt: sourceImage.prompt,
          poster_copy: getImagePosterCopy(sourceImage)
        }
      }

      // 后端 edit_image 路由已根据 parent_id 自动创建 folder_path
      // 同步模式下图片已由后端落盘到 edit_folders + edit_thumbnails
      // 直接使用后端返回的图片 URL，无需前端二次保存
      boardImages.value.unshift(newImage)
      selectedImageId.value = newImage.id
      saveBoardToStorage()
    }
  } catch (err) {
    submitError.value = err.message || '编辑失败，请重试'
    console.error('Edit error:', err)
  } finally {
    submitting.value = false
  }
}

const dataURItoBlob = (dataURI) => {
  if (!dataURI) return null
  const byteString = atob(dataURI.split(',')[1])
  const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0]
  const ab = new ArrayBuffer(byteString.length)
  const ia = new Uint8Array(ab)
  for (let i = 0; i < byteString.length; i++) {
    ia[i] = byteString.charCodeAt(i)
  }
  return new Blob([ab], { type: mimeString })
}

const startPolling = (taskId, imageId) => {
  if (!taskId || pollingIntervals.has(taskId)) return

  pollingMeta.set(taskId, { attempts: 0, startTime: Date.now() })

  const timer = setInterval(async () => {
    try {
      const meta = pollingMeta.get(taskId)
      if (!meta) {
        stopPolling(taskId)
        return
      }

      const elapsed = Date.now() - meta.startTime
      meta.attempts++

      if (meta.attempts > MAX_POLL_ATTEMPTS || elapsed > MAX_POLL_TIME_MS) {
        console.log(`[EditView] Polling task ${taskId} exceeded limits, stopping`)
        stopPolling(taskId)
        const image = boardImages.value.find(img => img.id === imageId)
        if (image) {
          image.generating = false
          image.error = '查询超时'
        }
        return
      }

      const result = await queryTask(taskId)
      // 后端返回的任务状态字段是 task_status，而非 status（status 是 HTTP 级别的 "success"）
      const taskStatus = result?.task_status || result?.data?.status || result?.status

      const image = boardImages.value.find(img => img.id === imageId)
      if (!image) {
        stopPolling(taskId)
        return
      }

      if (taskStatus === 'SUCCESS') {
        stopPolling(taskId)
        const displayUrl = result.image?.display_url || result.image?.url || image.url
        const imageSize = result.image?.size || image.size
        Object.assign(image, {
          url: displayUrl,
          thumbnail: result.image?.thumbnail || displayUrl || image.thumbnail,
          size: imageSize,
          generating: false,
          error: '',
          taskId: null,
          // 制作人：用后端返回的 creator 覆盖（后端是 source of truth），
          // 避免异步任务创建占位记录时未带 creator 导致筛选不命中
          creator: (result.image?.creator || image.creator || '').trim()
        })

        // 后端 query_task 路由已自动将图片落盘到 edit_folders + edit_thumbnails
        // result.image 中的 url/thumbnail 已是本地地址，直接使用
        if (result.image) {
          image.url = result.image.display_url || result.image.url || image.url
          image.thumbnail = result.image.thumbnail || result.image.display_url || image.url || image.thumbnail
        }
        saveBoardToStorage()
      } else if (taskStatus === 'FAILURE') {
        stopPolling(taskId)
        Object.assign(image, {
          generating: false,
          error: result.fail_reason || '编辑失败'
        })
      }
    } catch (err) {
      console.error('Poll error:', err)
    }
  }, POLL_INTERVAL_MS)

  pollingIntervals.set(taskId, timer)
}

const stopPolling = (taskId = null) => {
  if (!taskId) {
    pollingIntervals.forEach((timer) => clearInterval(timer))
    pollingIntervals.clear()
    return
  }
  if (pollingIntervals.has(taskId)) {
    clearInterval(pollingIntervals.get(taskId))
    pollingIntervals.delete(taskId)
  }
}

const openConfirmDialog = (options) => {
  confirmDialogConfig.value = {
    title: options.title || '确认',
    message: options.message || '确定要执行此操作吗？',
    confirmText: options.confirmText || '确定',
    cancelText: options.cancelText || '取消',
    danger: options.danger || false,
    onConfirm: options.onConfirm || (() => {})
  }
  showConfirmDialog.value = true
}

// 页面挂载时获取配置，先从缓存快速展示画板，再从数据库加载编辑图片列表
// 图片库数据在后台静默预加载，不阻塞页面渲染
onMounted(async () => {
  try {
    // 注册全局 mousedown 监听，实现点击 popover / 按钮外部时自动关闭
    document.addEventListener('mousedown', handleDocumentMouseDown)
    loadBoardFromStorage()
    fetchEditImages()

    if (!configStore.initialized) {
      await configStore.fetchConfig()
    }
    isAsync.value = configStore.imageApi.isAsync

    if (props.imageId) {
      initialLoading.value = true
      await imageStore.fetchImages()
      const image = imageStore.images.find(img => img.id === props.imageId)
      if (image) {
        currentEditingImage.value = {
          id: image.id,
          url: image.url,
          thumbnail: image.thumbnail || image.url,
          prompt: image.prompt || image.title || '已选择图片'
        }
      }
    } else {
      imageStore.fetchImages().catch(err => console.error('预加载图片库失败:', err))
    }
  } finally {
    initialLoading.value = false
  }
})

onUnmounted(() => {
  stopPolling()
  // 卸载全局 mousedown 监听，避免组件销毁后仍响应点击
  document.removeEventListener('mousedown', handleDocumentMouseDown)
})

watch(isAsync, async (newVal) => {
  try {
    await configStore.saveConfig({
      imageApi: { isAsync: newVal }
    })
  } catch (err) {
    console.error('Failed to save isAsync preference:', err)
  }
})

// API 提供者变化时保存到 localStorage，并联动更新模型
// APIYI 切换时强制 isAsync = true（视为异步执行，走后台线程任务卡）
watch(selectedApiProvider, (val) => {
  saveEditViewPrefs({ selectedApiProvider: val })
  if (val === 'apiyi') {
    if (!APIYI_ASPECT_RATIO_OPTIONS.some(option => option.value === editAspectRatio.value)) {
      editAspectRatio.value = 'auto'
    }
  }
  if (val === 'gptsapi') {
    if (!gptsapiAspectRatioOptions.some(option => option.value === editAspectRatio.value)) {
      editAspectRatio.value = 'auto'
    }
  }
  if (val === 'apiyi') {
    isAsync.value = true
  }
  if (!editModels.value.includes(selectedModel.value)) {
    selectedModel.value = editModels.value[0] || 'gpt-image-2'
  }
})

// 模型选择变化时保存到 localStorage
watch(selectedModel, (val) => {
  saveEditViewPrefs({ selectedModel: val })
})

// 制作人变化时保存到 localStorage，确保下次进入编辑页能恢复用户上次的选择
watch(selectedCreator, (val) => {
  saveEditViewPrefs({ creator: val || '' })
})

// EditBoard 工具栏中制作人筛选变更的处理函数
// 功能描述：
//     接收 EditBoard 抛出的 update:creator 事件，更新顶层 selectedCreator；
//     watch(selectedCreator) 会自动把新值持久化到 editViewPrefs，
//     下次进入编辑页时优先用此值（除非用户主动清空，则回退到生图页偏好）。
// 实现逻辑：
//     1. 直接覆盖 selectedCreator，保持工具栏与右侧编辑面板 Select 同步
//     2. 不在此处手动调用 saveEditViewPrefs，避免双写；由 watch 统一负责
const handleCreatorChange = (val) => {
  selectedCreator.value = val || ''
}

// 制作人继承逻辑：
//   1. 从图库选择（id 存在且非 local/edited/pending 前缀）→ 自动继承父图 creator
//   2. 本地上传/临时图片 → 使用上次保存的偏好（强制用户重新确认或修改）
watch(currentEditingImage, (img) => {
  const fallbackCreator = savedEditViewPrefs.creator || savedImageGeneratorPrefs.creator || ''
  if (img && img.id && !/^(local|edited|pending)-/.test(img.id)) {
    const source = imageStore.images.find((x) => x.id === img.id)
    selectedCreator.value = source?.creator || fallbackCreator
  } else {
    selectedCreator.value = fallbackCreator
  }
}, { immediate: true })

watch(editModels, (nextModels) => {
  if (!nextModels.includes(selectedModel.value)) {
    selectedModel.value = nextModels[0] || 'gpt-image-2'
  }
}, { deep: true })

watch([editAspectRatio, selectedApiProvider], () => {
  if (!currentEditResolutions.value.some(option => option.value === editResolution.value)) {
    editResolution.value = currentEditResolutions.value[0]?.value || '1K'
  }
})

watch(selectedImageId, () => {
  editPrompt.value = ''
  editAspectRatio.value = 'auto'
  editResolution.value = usesCompactEditSizeOptions.value ? '1K' : '2K'
  editQuality.value = 'auto'
  showAnnotationModal.value = false
})
</script>

<template>
  <div class="edit-view">
    <main class="edit-view__main">
      <aside class="edit-view__sidebar">
        <div class="edit-view__section">
          <div class="edit-view__section-header">
            <svg class="edit-view__section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <span class="edit-view__section-title">上传图片</span>
          </div>
          <ImageUpload
            :max-edge="GPT_IMAGE_MAX_EDGE"
            :on-oversize="handleUploadOversize"
            @update:model-value="handleUploadComplete"
            @file-selected="handleFileSelected"
            @upload-complete="handleUploadComplete"
            @compressed="handleUploadCompressed"
          />
        </div>

        <div class="edit-view__section">
          <button class="edit-view__select-btn" @click="handleOpenSelector">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <circle cx="8.5" cy="8.5" r="1.5"/>
              <polyline points="21 15 16 10 5 21"/>
            </svg>
            从图片库选择
          </button>
        </div>

        <div v-if="selectedImage" class="edit-view__section edit-view__section--preview">
          <div class="edit-view__section-header">
            <svg class="edit-view__section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <circle cx="8.5" cy="8.5" r="1.5"></circle>
              <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
            <span class="edit-view__section-title">当前编辑图片</span>
          </div>
          <button
            class="edit-view__preview-card"
            type="button"
            @click="handleOpenAnnotationModal"
          >
            <span class="edit-view__preview-badge">点击编辑（标注/遮罩）</span>
            <img :src="selectedImage.annotatedPreview || selectedImage.url" :alt="selectedImage.prompt" class="edit-view__preview-img" />
            <p class="edit-view__preview-prompt">{{ selectedImage.prompt }}</p>
          </button>

          <div v-if="selectedImage.maskPreview || selectedImage.annotatedPreview" class="edit-view__preview-masks">
            <div
              v-if="selectedImage.annotatedPreview"
              class="edit-view__preview-mask-item"
              @click="handleOpenAnnotationModal"
            >
              <span class="edit-view__preview-mask-label">标注</span>
              <img :src="selectedImage.annotatedPreview" class="edit-view__preview-mask-thumb" />
            </div>
            <div
              v-if="selectedImage.maskPreview"
              class="edit-view__preview-mask-item edit-view__preview-mask-item--mask"
              @click="handleOpenAnnotationModal"
            >
              <span class="edit-view__preview-mask-label">遮罩</span>
              <img :src="selectedImage.maskPreview" class="edit-view__preview-mask-thumb" />
              <div class="edit-view__preview-mask-overlay"></div>
            </div>
          </div>
        </div>
      </aside>

      <section class="edit-view__board">
        <div v-if="initialLoading" class="edit-view__loading">
          <div class="edit-view__spinner"></div>
          <p class="edit-view__loading-text">加载中...</p>
        </div>

        <template v-else>
          <EditBoard
            :images="filteredBoardImages"
            :selected-id="selectedImageId"
            :creator="selectedCreator"
            :creator-options="filterCreatorOptions"
            @select="handleBoardCompare"
            @edit="handleBoardEdit"
            @delete="handleBoardDelete"
            @save="handleBoardSave"
            @download="handleBoardDownload"
            @batchDelete="handleBatchDelete"
            @batchSave="handleBatchSave"
            @add-to-preparation="handleAddToPreparation"
            @add-to-geo="handleAddToGeo"
            @retry="handleBoardRetry"
            @update:creator="handleCreatorChange"
          />

          <div v-if="boardImages.length === 0" class="edit-view__empty">
            <div class="edit-view__empty-icon-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21 15 16 10 5 21"/>
              </svg>
            </div>
            <p class="edit-view__empty-title">开始编辑</p>
            <p class="edit-view__empty-hint">上传图片或从图片库选择，然后输入编辑指令</p>
          </div>
        </template>
      </section>

      <aside class="edit-view__editor-panel" :class="{ 'edit-view__editor-panel--active': currentEditingImage }">
        <div v-if="currentEditingImage" class="edit-view__editor">
          <div class="edit-view__editor-header">
            <div class="edit-view__editor-header-left">
              <svg class="edit-view__editor-header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
              <h3 class="edit-view__editor-title">编辑参数</h3>
            </div>
            <div class="edit-view__editor-header-right">
              <div class="edit-view__mode-toggle">
                <span :class="{ 'edit-view__mode-label--active': !isAsync }">同步</span>
                <button
                  class="edit-view__toggle-switch"
                  :class="{ 'edit-view__toggle-switch--active': isAsync }"
                  @click="toggleAsync"
                  :disabled="submitting"
                ></button>
                <span :class="{ 'edit-view__mode-label--active': isAsync }">异步</span>
              </div>
              <button class="edit-view__editor-close" @click="handleCloseEditor">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>

          <div class="edit-view__editor-form">
            <div class="edit-view__field">
              <div class="edit-view__field-header">
                <label class="edit-view__label">
                  <svg class="edit-view__label-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 20h9"></path>
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7.5 18H4v-3.667L16.5 3.5z"></path>
                  </svg>
                  编辑指令
                  <span class="edit-view__label-required">*</span>
                </label>
                <div class="edit-view__field-actions">
                  <span class="edit-view__counter">{{ editPrompt.length }}/1000</span>
                  <button
                    ref="snippetMenuButtonRef"
                    type="button"
                    class="edit-view__snippet-btn"
                    :class="{ 'edit-view__snippet-btn--active': showSnippetMenu }"
                    :disabled="submitting"
                    title="从设置中选用预设片段"
                    @click.stop="toggleSnippetMenu"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="8" y="2" width="12" height="12" rx="2"></rect>
                      <path d="M16 14H8a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2z"></path>
                    </svg>
                    <span>片段</span>
                  </button>
                </div>
                <!-- 编辑指令预设片段 popover：点击片段按钮时弹出 -->
                <div
                  v-if="showSnippetMenu"
                  ref="snippetMenuPopoverRef"
                  class="edit-view__snippet-popover"
                  role="menu"
                  @click.stop
                >
                  <div class="edit-view__snippet-popover-header">从设置中选择预设片段</div>
                  <div v-if="!configStore.editPromptSnippets?.snippets?.length" class="edit-view__snippet-empty">
                    暂无预设片段，请先在「设置 → 编辑指令预设」中添加
                  </div>
                  <ul v-else class="edit-view__snippet-list">
                    <li
                      v-for="snippet in configStore.editPromptSnippets.snippets"
                      :key="snippet.id"
                      class="edit-view__snippet-item"
                      role="menuitem"
                      tabindex="0"
                      @click="appendSnippetToPrompt(snippet)"
                      @keydown.enter.prevent="appendSnippetToPrompt(snippet)"
                    >
                      <div class="edit-view__snippet-item-name">{{ snippet.name || '未命名片段' }}</div>
                      <div class="edit-view__snippet-item-preview">{{ snippet.content || '（空内容）' }}</div>
                    </li>
                  </ul>
                </div>
              </div>
              <div class="edit-view__textarea-wrapper">
                <textarea
                  v-model="editPrompt"
                  class="edit-view__textarea"
                  placeholder="描述你想要对图像进行的修改..."
                  :disabled="submitting"
                  maxlength="1000"
                ></textarea>
                <svg class="edit-view__textarea-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 20h9"></path>
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7.5 18H4v-3.667L16.5 3.5z"></path>
                </svg>
              </div>
            </div>

            <!-- 参考图上传区域 -->
            <div class="edit-view__field">
              <div class="edit-view__reference-header">
                <label class="edit-view__label">
                  <svg class="edit-view__label-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    <circle cx="8.5" cy="8.5" r="1.5"></circle>
                    <polyline points="21 15 16 10 5 21"></polyline>
                  </svg>
                  参考图
                </label>
                <div class="edit-view__reference-actions">
                  <button class="edit-view__reference-action-btn" @click="showEditMaterialSelector = true" type="button">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="3" y="3" width="7" height="7"></rect>
                      <rect x="14" y="3" width="7" height="7"></rect>
                      <rect x="14" y="14" width="7" height="7"></rect>
                      <rect x="3" y="14" width="7" height="7"></rect>
                    </svg>
                    素材库
                  </button>
                  <span class="edit-view__reference-count">{{ editReferenceImages.length }}/{{ maxEditRefImages }}</span>
                </div>
              </div>
              <div class="edit-view__reference">
                <div
                  class="edit-view__reference-dropzone"
                  :class="{ 'edit-view__reference-dropzone--dragover': isEditRefDragOver }"
                  @dragover.prevent="isEditRefDragOver = true"
                  @dragleave.prevent="isEditRefDragOver = false"
                  @drop.prevent="handleEditRefDrop"
                  @click="triggerEditRefUpload"
                >
                  <div class="edit-view__reference-icon-wrapper">
                    <svg class="edit-view__reference-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                      <polyline points="17 8 12 3 7 8"></polyline>
                      <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                  </div>
                  <span class="edit-view__reference-text">点击或拖拽上传参考图</span>
                  <span class="edit-view__reference-hint">支持 JPG、PNG、WebP，最多 {{ maxEditRefImages }} 张</span>
                  <input type="file" ref="editRefInputRef" accept="image/jpeg,image/png,image/webp" multiple @change="handleEditRefFileSelect" class="edit-view__reference-input" />
                </div>
                <div v-if="editReferenceImages.length > 0" class="edit-view__reference-grid">
                  <div v-for="(img, index) in editReferenceImages" :key="img.id" class="edit-view__reference-item">
                    <img v-if="!img.uploading" :src="img.url" class="edit-view__reference-thumb" />
                    <div v-else class="edit-view__reference-uploading">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line>
                        <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                        <line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line>
                        <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
                      </svg>
                    </div>
                    <div v-if="!img.uploading" class="edit-view__reference-overlay">
                      <button class="edit-view__reference-btn" @click.stop="handlePreviewRefImage(img.url)" title="预览">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                          <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                      </button>
                      <button class="edit-view__reference-btn edit-view__reference-btn--danger" @click.stop="removeEditRefImage(index)" title="删除">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="3 6 5 6 21 6"></polyline>
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="edit-view__selectors">
              <!-- API 提供者选择器 - 独立一行 -->
              <div class="edit-view__selector-row edit-view__selector-row--full">
                <div class="edit-view__selector">
                  <label class="edit-view__label edit-view__label--select">API</label>
                  <Select
                    v-model="selectedApiProvider"
                    :options="editApiProviderOptions"
                    wrapper-class="edit-view__select-wrapper"
                  />
                </div>
              </div>

              <!-- 制作人选择器 - 独立一行；本地属性，不发送到编辑 API，仅作为图片元数据保存到 images.creator -->
              <div class="edit-view__selector-row edit-view__selector-row--full">
                <div class="edit-view__selector">
                  <label class="edit-view__label edit-view__label--select">制作人</label>
                  <Select
                    v-model="selectedCreator"
                    :options="creatorOptions"
                    :disabled="submitting"
                    placeholder="选择制作人"
                    wrapper-class="edit-view__select-wrapper"
                  />
                </div>
              </div>

              <div class="edit-view__selector-row">
                <div v-if="!isAsyncOnlyProvider || isApiyiProvider" class="edit-view__selector">
                  <label class="edit-view__label edit-view__label--select">模型</label>
                  <Select
                    v-model="selectedModel"
                    :options="editModelOptions"
                    wrapper-class="edit-view__select-wrapper"
                  />
                </div>
                <div class="edit-view__selector">
                  <label class="edit-view__label edit-view__label--select">
                    <svg class="edit-view__label-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                      <line x1="3" y1="9" x2="21" y2="9"></line>
                      <line x1="9" y1="21" x2="9" y2="9"></line>
                    </svg>
                    比例
                  </label>
                  <Select
                    v-model="editAspectRatio"
                    :options="currentEditAspectRatioOptions"
                    wrapper-class="edit-view__select-wrapper"
                  />
                </div>
              </div>
              <div class="edit-view__selector-row">
                <div v-if="!isGptsapiProvider && (!isApiyiProvider || isApiyiGptImage2)" class="edit-view__selector">
                  <label class="edit-view__label edit-view__label--select">
                    <svg class="edit-view__label-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path>
                    </svg>
                    清晰度
                  </label>
                  <Select
                    v-model="editQuality"
                    :options="qualityOptions"
                    wrapper-class="edit-view__select-wrapper"
                  />
                </div>
                <div v-if="!isApiyiGptImage2Vip" class="edit-view__selector">
                  <label class="edit-view__label edit-view__label--select">res</label>
                  <div class="edit-view__res-buttons">
                    <button
                      v-for="res in currentEditResolutions"
                      :key="res.value"
                      type="button"
                      :class="['edit-view__res-btn', { 'edit-view__res-btn--active': editResolution === res.value }]"
                      @click="editResolution = res.value"
                      :disabled="submitting"
                    >
                      {{ res.label }}
                    </button>
                  </div>
                </div>
              </div>

            <div v-if="!isAsyncOnlyProvider || isApiyiGptImage2" class="edit-view__selector-row">
              <div class="edit-view__selector">
                <label class="edit-view__label edit-view__label--select">输出</label>
                <Select
                  v-model="editOutputFormat"
                  :options="outputFormatOptions"
                  wrapper-class="edit-view__select-wrapper"
                />
              </div>
              <div v-if="isApiyiGptImage2" class="edit-view__selector">
                <label class="edit-view__label edit-view__label--select">Moderation</label>
                <Select
                  v-model="editModeration"
                  :options="moderationOptions"
                  wrapper-class="edit-view__select-wrapper"
                />
              </div>
            </div>

            <div
              v-if="(!isAsyncOnlyProvider || isApiyiGptImage2) && (editOutputFormat === 'jpeg' || editOutputFormat === 'webp')"
              class="edit-view__compression-row"
            >
              <label class="edit-view__label">
                压缩率: {{ editOutputCompression }}%
              </label>
              <input
                v-model.number="editOutputCompression"
                type="range"
                min="0"
                max="100"
                class="edit-view__compression-slider"
                :disabled="submitting"
              />
            </div>
          </div>

          <p v-if="submitError" class="edit-view__error">
              <svg class="edit-view__error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              {{ submitError }}
            </p>

            <div class="edit-view__actions">
              <button
                class="edit-view__btn edit-view__btn--primary"
                :disabled="submitting || !editPrompt.trim()"
                @click="handleEditSubmit"
              >
                <svg v-if="!submitting" class="edit-view__btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                <svg v-else class="edit-view__btn-icon edit-view__spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
                </svg>
                {{ submitting ? '提交中...' : '开始编辑' }}
              </button>
            </div>
          </div>
        </div>
      </aside>
    </main>

    <ImageSelector
      :visible="showSelector"
      :images="imageStore.images"
      @update:visible="showSelector = $event"
      @select="handleSelectFromLibrary"
    />

    <ConfirmDialog
      v-model:visible="showConfirmDialog"
      :title="confirmDialogConfig.title"
      :message="confirmDialogConfig.message"
      :confirm-text="confirmDialogConfig.confirmText"
      :cancel-text="confirmDialogConfig.cancelText"
      :danger="confirmDialogConfig.danger"
      @confirm="confirmDialogConfig.onConfirm"
    />

    <OptionDialog
      v-model:visible="showResolutionDialog"
      title="选择压缩分辨率"
      :message="resolutionDialogMessage"
      :options="resolutionDialogOptions"
      cancel-text="取消上传"
      @select="handleResolutionSelect"
      @cancel="handleResolutionCancel"
    />

    <ImageCompare
      v-if="compareImage"
      :new-image="compareImage.new"
      :original-image="compareImage.original"
      @close="compareImage = null"
    />

    <SaveToLibraryDialog
      v-model:visible="showSaveDialog"
      :image="savingImage"
      @saved="handleSavedToLibrary"
    />

    <ImageAnnotationModal
      :visible="showAnnotationModal"
      :image-url="(selectedImage?.annotatedPreview || selectedImage?.url) || ''"
      :mask-image="currentEditingImage?.maskImage || ''"
      :saving="annotationSaving"
      @close="handleAnnotationClose"
      @save="handleAnnotationSave"
    />

    <ImagePreview
      v-if="previewRefImage"
      :image="previewRefImage"
      @close="previewRefImage = null"
    />

    <MaterialSelector
      :show="showEditMaterialSelector"
      :multiple="true"
      :max-count="maxEditRefImages - editReferenceImages.length"
      @close="showEditMaterialSelector = false"
      @select="handleEditMaterialSelect"
    />

    <div v-if="saveNotification" class="edit-view__notification" :class="`edit-view__notification--${saveNotification.type}`">
      <svg class="edit-view__notification-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <template v-if="saveNotification.type === 'success'">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </template>
        <template v-else-if="saveNotification.type === 'warning'">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
          <line x1="12" y1="9" x2="12" y2="13"></line>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </template>
        <template v-else>
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </template>
      </svg>
      <span class="edit-view__notification-text">{{ saveNotification.message }}</span>
      <button class="edit-view__notification-close" @click="saveNotification = null">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>
  </div>
</template>

<style lang="scss">
@use '@/styles/variables' as *;
@use '@/styles/mixins' as *;
@import '@/styles/EditView.scss';

.edit-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: $color-bg;

  &__main {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  &__sidebar {
    width: 280px;
    padding: $spacing-lg;
    background: $color-bg-card;
    border-right: 1px solid $color-border-light;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: $spacing-md;
  }

  &__section {
    &--preview {
      padding-top: $spacing-md;
      border-top: 1px solid $color-border-light;
    }
  }

  &__section-header {
    display: flex;
    align-items: center;
    gap: $spacing-xs;
    margin-bottom: $spacing-sm;
  }

  &__section-icon {
    width: 14px;
    height: 14px;
    color: $color-text-tertiary;
  }

  &__section-title {
    margin: 0;
    font-size: 9px;
    font-weight: 600;
    color: $color-text-secondary;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  &__select-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: $spacing-sm;
    width: 100%;
    padding: $spacing-sm $spacing-md;
    background: linear-gradient(135deg, rgba($color-primary, 0.1) 0%, rgba($color-primary, 0.05) 100%);
    border: 1px solid rgba($color-primary, 0.2);
    border-radius: $radius-lg;
    color: $color-primary;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: all $transition-fast;

    svg {
      width: 16px;
      height: 16px;
    }

    &:hover {
      background: linear-gradient(135deg, rgba($color-primary, 0.15) 0%, rgba($color-primary, 0.1) 100%);
      border-color: rgba($color-primary, 0.3);
      transform: translateY(-1px);
    }
  }

  &__preview-card {
    position: relative;
    width: 100%;
    padding: 0;
    border-radius: $radius-lg;
    overflow: hidden;
    border: 1px solid $color-border;
    background: $color-bg-card;
    cursor: pointer;
    text-align: left;
    transition: transform $transition-fast, box-shadow $transition-fast, border-color $transition-fast;

    &:hover {
      transform: translateY(-1px);
      border-color: rgba($color-primary, 0.4);
      box-shadow: 0 16px 36px rgba($color-primary, 0.12);
    }
  }

  &__preview-img {
    width: 100%;
    display: block;
    object-fit: cover;
  }

  &__preview-prompt {
    margin: 0;
    padding: $spacing-sm;
    font-size: 10px;
    color: $color-text-secondary;
    line-height: 1.4;
    @include truncate;
    background: $color-bg-secondary;
  }

  &__preview-badge {
    position: absolute;
    top: $spacing-sm;
    left: $spacing-sm;
    z-index: 1;
    padding: 6px 10px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: $radius-full;
    background: rgba(17, 24, 39, 0.7);
    color: $color-text-inverse;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.04em;
    backdrop-filter: blur(8px);
  }

  &__board {
    flex: 1;
    padding: $spacing-lg;
    overflow-y: auto;
    position: relative;
    background: $color-bg-secondary;
  }

  &__empty {
    @include flex-column-center;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
  }

  &__empty-icon-wrapper {
    @include flex-center;
    width: 72px;
    height: 72px;
    background: $color-bg-card;
    border-radius: $radius-xl;
    box-shadow: $shadow-md;
    margin-bottom: $spacing-lg;

    svg {
      width: 36px;
      height: 36px;
      color: $color-text-tertiary;
    }
  }

  &__empty-title {
    margin: 0 0 $spacing-xs;
    font-size: $font-size-base;
    font-weight: 500;
    color: $color-text-secondary;
  }

  &__empty-hint {
    margin: 0;
    font-size: $font-size-xs;
    color: $color-text-tertiary;
  }

  &__loading {
    @include flex-column-center;
    padding: $spacing-3xl;
    gap: $spacing-md;
  }

  &__spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba($color-primary, 0.2);
    border-top-color: $color-primary;
    border-radius: $radius-full;
    animation: spin 1s linear infinite;
  }

  &__loading-text {
    font-size: $font-size-sm;
    color: $color-text-secondary;
    margin: 0;
  }

  &__editor-panel {
    width: 0;
    overflow: hidden;
    background: $color-bg-card;
    border-left: 1px solid $color-border-light;
    transition: width $transition-slow;

    &--active {
      width: 380px;
    }
  }

  &__editor {
    width: 380px;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  &__editor-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $spacing-md $spacing-lg;
    border-bottom: 1px solid $color-border-light;
  }

  &__editor-header-left {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
  }

  &__editor-header-icon {
    width: 18px;
    height: 18px;
    color: $color-text-tertiary;
  }

  &__editor-title {
    margin: 0;
    font-size: $font-size-lg;
    font-weight: $font-weight-semibold;
    color: $color-text-primary;
    letter-spacing: -0.02em;
  }

  &__editor-header-right {
    display: flex;
    align-items: center;
    gap: $spacing-md;
  }

  &__editor-close {
    @include flex-center;
    width: 32px;
    height: 32px;
    background: $color-bg-secondary;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    color: $color-text-secondary;
    cursor: pointer;
    transition: all $transition-fast;

    svg {
      width: 14px;
      height: 14px;
    }

    &:hover {
      background: rgba($color-danger, 0.1);
      border-color: rgba($color-danger, 0.3);
      color: $color-danger;
    }
  }

  &__mode-toggle {
    display: flex;
    align-items: center;
    gap: $spacing-xs;
    font-size: $font-size-xs;
    padding: 2px 6px;
    background: $color-bg-secondary;
    border-radius: $radius-lg;
  }

  &__mode-label--active {
    padding: 2px 6px;
    border-radius: $radius-md;
    background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
    color: $color-text-inverse;
    font-weight: $font-weight-medium;
  }

  &__toggle-switch {
    position: relative;
    width: 40px;
    height: 22px;
    background: linear-gradient(135deg, rgba($color-text-tertiary, 0.3) 0%, rgba($color-text-tertiary, 0.2) 100%);
    border: none;
    border-radius: $radius-full;
    cursor: pointer;
    transition: all $transition-fast;
    padding: 0;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.08);

    &--active {
      background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
      box-shadow: 0 2px 8px rgba($color-primary, 0.3);
    }

    &::after {
      content: '';
      position: absolute;
      top: 2px;
      left: 2px;
      width: 18px;
      height: 18px;
      background: $color-bg-card;
      border-radius: $radius-full;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
      transition: all $transition-fast;
    }

    &--active::after {
      transform: translateX(18px);
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  &__editor-form {
    flex: 1;
    padding: $spacing-lg;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: $spacing-md;
  }

  &__field {
    display: flex;
    flex-direction: column;
    gap: $spacing-xs;
  }

  &__field-header {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__label {
    display: flex;
    align-items: center;
    gap: $spacing-xs;
    font-size: $font-size-xs;
    font-weight: $font-weight-semibold;
    color: $color-text-primary;
    line-height: 1.4;
    user-select: none;

    &--select {
      font-size: 11px;
      font-weight: 500;
      color: $color-text-secondary;
      margin-bottom: $spacing-xs;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }
  }

  &__label-icon {
    width: 14px;
    height: 14px;
    color: $color-text-tertiary;
  }

  &__label-required {
    color: $color-danger;
    font-size: 12px;
  }

  &__counter {
    font-size: 9px;
    color: $color-text-tertiary;
    font-variant-numeric: tabular-nums;
  }

  // 编辑指令 field-header 右侧 actions 容器：横向排布 counter 与片段按钮
  &__field-actions {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
  }

  // 编辑指令预设片段按钮：与 reference-header 内的参考图按钮风格保持一致
  &__snippet-btn {
    display: inline-flex;
    align-items: center;
    gap: $spacing-xs;
    padding: 2px $spacing-sm;
    background: linear-gradient(135deg, rgba($color-primary, 0.1) 0%, rgba($color-primary, 0.05) 100%);
    border: 1px solid rgba($color-primary, 0.2);
    border-radius: $radius-md;
    color: $color-primary;
    font-size: 10px;
    font-weight: 500;
    cursor: pointer;
    transition: all $transition-fast;
    line-height: 1.4;

    svg {
      width: 12px;
      height: 12px;
    }

    &:hover:not(:disabled) {
      background: linear-gradient(135deg, rgba($color-primary, 0.18) 0%, rgba($color-primary, 0.1) 100%);
      border-color: rgba($color-primary, 0.4);
      transform: translateY(-1px);
    }

    &--active {
      background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
      border-color: $color-primary;
      color: $color-text-inverse;
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  // 编辑指令预设片段 popover：相对 field-header 右上角定位
  // 关键样式：z-index 高于 textarea，背景不透明，阴影与圆角与项目其它 popover 一致
  &__snippet-popover {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    z-index: 50;
    min-width: 240px;
    max-width: 320px;
    max-height: 280px;
    overflow-y: auto;
    background: $color-bg-card;
    border: 1px solid $color-border;
    border-radius: $radius-lg;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.06);
    padding: $spacing-xs 0;
  }

  &__snippet-popover-header {
    padding: $spacing-xs $spacing-md;
    font-size: 10px;
    font-weight: 600;
    color: $color-text-tertiary;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid $color-border-light;
  }

  &__snippet-empty {
    padding: $spacing-md;
    font-size: 11px;
    color: $color-text-tertiary;
    line-height: 1.5;
  }

  &__snippet-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  &__snippet-item {
    padding: $spacing-xs $spacing-md;
    cursor: pointer;
    border-bottom: 1px solid $color-border-light;
    transition: background $transition-fast;

    &:last-child {
      border-bottom: none;
    }

    &:hover,
    &:focus {
      background: linear-gradient(135deg, rgba($color-primary, 0.08) 0%, rgba($color-primary, 0.03) 100%);
      outline: none;
    }
  }

  &__snippet-item-name {
    font-size: 11px;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: 2px;
  }

  &__snippet-item-preview {
    font-size: 10px;
    color: $color-text-tertiary;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
    word-break: break-all;
    white-space: pre-wrap;
  }

  &__textarea-wrapper {
    position: relative;
  }

  &__textarea {
    width: 100%;
    min-height: 6rem;
    padding: $spacing-sm $spacing-md;
    background: linear-gradient(180deg, $color-bg-secondary 0%, $color-bg-tertiary 100%);
    border: 1px solid $color-border;
    border-radius: $radius-md;
    font-size: $font-size-xs;
    color: $color-text-primary;
    line-height: 1.5;
    resize: vertical;
    transition: all $transition-fast;
    box-sizing: border-box;

    &:focus {
      outline: none;
      border-color: $color-border-focus;
      box-shadow: 0 0 0 3px rgba($color-primary, 0.08);
    }

    &::placeholder {
      color: $color-text-tertiary;
    }
  }

  &__textarea-icon {
    position: absolute;
    top: $spacing-md;
    right: $spacing-md;
    width: 14px;
    height: 14px;
    color: $color-text-tertiary;
    pointer-events: none;
  }

  &__selectors {
    display: flex;
    flex-direction: column;
    gap: $spacing-xs;
  }

  &__selector-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: $spacing-sm;

    &--full {
      grid-template-columns: 1fr;
    }
  }

  &__selector {
    display: flex;
    flex-direction: column;
  }

  &__select-wrapper {
    // custom select in editor panel
  }

  &__res-buttons {
    display: flex;
    gap: 4px;
  }

  &__res-btn {
    flex: 1;
    padding: 6px 8px;
    background: $color-bg-secondary;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    color: $color-text-secondary;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: all $transition-fast;

    &:hover:not(:disabled) {
      border-color: $color-primary;
      color: $color-primary;
    }

    &--active {
      background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
      border-color: $color-primary;
      color: $color-text-inverse;
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  &__error {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    padding: $spacing-sm $spacing-md;
    background: linear-gradient(135deg, rgba($color-danger, 0.1) 0%, rgba($color-danger, 0.05) 100%);
    border: 1px solid rgba($color-danger, 0.25);
    border-radius: $radius-lg;
    color: $color-danger;
    font-size: $font-size-xs;
    margin: 0;
  }

  &__error-icon {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
  }

  &__actions {
    margin-top: $spacing-md;
    padding-top: $spacing-md;
    border-top: 1px solid $color-border-light;
  }

  &__btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: $spacing-sm;
    width: 100%;
    min-height: 44px;
    padding: $spacing-sm $spacing-lg;
    border-radius: $radius-lg;
    font-size: $font-size-sm;
    font-weight: 600;
    letter-spacing: 0.02em;
    transition: all $transition-fast;
    cursor: pointer;
    border: none;

    &--primary {
      background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
      color: $color-text-inverse;
      box-shadow: 0 4px 15px rgba($color-primary, 0.35);

      &:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba($color-primary, 0.45);
      }

      &:active:not(:disabled) {
        transform: translateY(0);
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        box-shadow: none;
      }
    }
  }

  &__btn-icon {
    width: 16px;
    height: 16px;
  }

  &__spinner {
    animation: spin 1s linear infinite;
  }

  // 保存操作结果通知
  &__notification {
    position: fixed;
    bottom: $spacing-lg;
    right: $spacing-lg;
    z-index: 2000;
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    padding: $spacing-sm $spacing-md;
    background: $color-bg-card;
    border-radius: $radius-lg;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.06);
    border: 1px solid $color-border;
    animation: slideUp 0.3s ease;
    max-width: 400px;

    &--success {
      border-color: rgba(#22c55e, 0.3);
      .edit-view__notification-icon { color: #22c55e; }
    }

    &--warning {
      border-color: rgba(#f59e0b, 0.3);
      .edit-view__notification-icon { color: #f59e0b; }
    }

    &--error {
      border-color: rgba($danger-color, 0.3);
      .edit-view__notification-icon { color: $danger-color; }
    }
  }

  &__notification-icon {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
  }

  &__notification-text {
    font-size: $font-size-xs;
    color: $color-text-primary;
    line-height: 1.4;
  }

  &__notification-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    background: none;
    color: $color-text-tertiary;
    cursor: pointer;
    border-radius: $radius-sm;
    flex-shrink: 0;
    transition: all $transition-fast;

    &:hover {
      background: $color-bg-secondary;
      color: $color-text-primary;
    }

    svg {
      width: 12px;
      height: 12px;
    }
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

