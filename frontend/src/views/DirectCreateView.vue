<template>
  <div class="create-view">
    <div class="create-view__content">
      <div class="create-view__generator">
        <ImageGenerator
          ref="imageGeneratorRef"
          :generating="generating"
          @generate="handleGenerate"
          @generate-start="handleGenerateStart"
          @error="handleError"
        />
      </div>

      <div class="create-view__library">
        <ImageLibrary
          ref="imageLibraryRef"
          :images="images"
          :loading="loading"
          :initialLoading="initialLoading"
          :refreshing="refreshing"
          :totalCount="imageStore.images.length"
          @select="handleImageSelect"
          @view="handleImagePreview"
          @delete="handleImageDelete"
          @edit="handleImageEdit"
          @rename="handleImageRename"
          @refresh="handleRefresh"
          @reuse-prompt="handleReusePrompt"
          @batch-reference="handleBatchReference"
          @select-folder="handleSelectFolder"
          @enter-recycle-bin="handleEnterRecycleBin"
          @add-to-preparation="handleAddToPreparation"
          @gptsapi-retry="handleGptsapiRetry"
        />
      </div>
    </div>

    <ImagePreview
      v-if="previewImage"
      :image="previewImage"
      @close="previewImage = null"
    />

    <div v-if="showRenameModal" class="rename-modal" @click.self="closeRenameModal">
      <div class="rename-modal__content">
        <h3 class="rename-modal__title">重命名图片</h3>
        <input
          v-model="newImageTitle"
          class="rename-modal__input"
          placeholder="请输入新名称"
          @keyup.enter="confirmRename"
          ref="renameInputRef"
        />
        <div class="rename-modal__actions">
          <button class="rename-modal__btn rename-modal__btn--cancel" @click="closeRenameModal">
            取消
          </button>
          <button class="rename-modal__btn rename-modal__btn--confirm" @click="confirmRename">
            确认
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      v-model:visible="showConfirmDialog"
      :title="confirmDialogConfig.title"
      :message="confirmDialogConfig.message"
      :confirm-text="confirmDialogConfig.confirmText"
      :cancel-text="confirmDialogConfig.cancelText"
      :danger="confirmDialogConfig.danger"
      @confirm="confirmDialogConfig.onConfirm"
      @cancel="confirmDialogConfig.onCancel"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useImageStore } from '@/stores/imageStore'
import { queryTask, downloadImage, renameImage, refreshImage, gptsapiRetry, getFolderImages, api } from '@/services/api'
import ImageGenerator from '@/components/ImageGenerator.vue'
import ImageLibrary from '@/components/ImageLibrary.vue'
import ImagePreview from '@/components/ImagePreview.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'

const router = useRouter()
const imageStore = useImageStore()

const previewImage = ref(null)
const imageGeneratorRef = ref(null)
const activePollingCount = ref(0)
const generatingCardIds = ref([])
const generatingTaskId = ref(null)

// 初始化时读取 localStorage 中保存的文件夹，直接进入对应视图
const savedFolder = typeof window !== 'undefined' ? localStorage.getItem('image-library-folder') : null
const currentFolderId = ref(savedFolder && savedFolder !== 'recycle' ? savedFolder : 'all')
const folderImages = ref(null)
const isFolderLoading = ref(false)

// 异步任务轮询状态
const pollingIntervals = new Map()
const pollingMeta = new Map()

const POLL_INTERVAL_MS = 3000
const MAX_POLL_ATTEMPTS = 1000
const MAX_POLL_TIME_MS = 3000000
const PENDING_TASK_STATUSES = new Set([
  'PENDING',
  'IN_PROGRESS',
  'GENERATING',
  '未启动',
  'QUEUED',
  'NOT_STARTED',
  'NOT_START',
  'WAITING'
])
const FINAL_TASK_STATUSES = new Set(['SUCCESS', 'FAILURE'])

// 重命名弹窗状态
const showRenameModal = ref(false)
const newImageTitle = ref('')
const renamingImageId = ref(null)
const renameInputRef = ref(null)
const imageLibraryRef = ref(null)

// 确认弹窗状态
const showConfirmDialog = ref(false)
const confirmDialogConfig = ref({
  title: '',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  onConfirm: () => {},
  onCancel: () => {}
})

const openConfirmDialog = (options) => {
  confirmDialogConfig.value = {
    title: options.title || '确认',
    message: options.message || '确定要执行此操作吗？',
    confirmText: options.confirmText || '确定',
    cancelText: options.cancelText || '取消',
    danger: options.danger || false,
    onConfirm: options.onConfirm || (() => {}),
    onCancel: options.onCancel || (() => {})
  }
  showConfirmDialog.value = true
}

const images = computed(() => {
  if (currentFolderId.value !== 'all') {
    return folderImages.value || []
  }
  return imageStore.images.filter((image) => (image.imageType || image.image_type || 'generation') !== 'edit')
})
const loading = computed(() => {
  if (currentFolderId.value !== 'all') {
    return isFolderLoading.value
  }
  return imageStore.loading
})
const initialLoading = computed(() => imageStore.initialLoading)
const refreshing = computed(() => imageStore.refreshing)
const generating = computed(() => {
  return activePollingCount.value > 0 || images.value.some((image) => isImagePending(image))
})

const getTaskId = (image) => {
  return image?.task_id || image?.taskId || null
}

const normalizeTaskStatus = (status) => {
  return typeof status === 'string' ? status.trim() : (status || 'UNKNOWN')
}

const isImagePending = (image) => {
  const taskId = getTaskId(image)
  const imageStatus = normalizeTaskStatus(image?.status)
  return Boolean(taskId) && (
    image?.generating === true ||
    PENDING_TASK_STATUSES.has(imageStatus)
  )
}

const findImageByTaskId = (taskId) => {
  return imageStore.images.find((image) => getTaskId(image) === taskId)
}

const syncPollingState = () => {
  activePollingCount.value = pollingIntervals.size
}

const stopPolling = (taskId = null) => {
  if (!taskId) {
    pollingIntervals.forEach((timer) => clearTimeout(timer))
    pollingIntervals.clear()
    pollingMeta.clear()
    syncPollingState()
    return
  }

  if (pollingIntervals.has(taskId)) {
    clearTimeout(pollingIntervals.get(taskId))
    pollingIntervals.delete(taskId)
  }

  pollingMeta.delete(taskId)
  syncPollingState()
}

const applyTaskResult = (result, taskId) => {
  const rawTaskStatus = normalizeTaskStatus(result?.task_status || result?.data?.status || result?.status)
  const existingImage = findImageByTaskId(taskId)
  const fallbackTaskStatus = existingImage ? normalizeTaskStatus(existingImage.status) : 'UNKNOWN'
  const taskStatus = rawTaskStatus === 'UNKNOWN'
    ? fallbackTaskStatus
    : rawTaskStatus
  const updatedImage = result?.image

  if (updatedImage) {
    imageStore.upsertImage({
      ...updatedImage,
      created_at: existingImage?.created_at || existingImage?.createdAt || updatedImage.created_at || new Date().toISOString(),
      status: taskStatus,
      generating: !FINAL_TASK_STATUSES.has(taskStatus),
      error: taskStatus === 'FAILURE' ? (result?.fail_reason || updatedImage.fail_reason || '图片生成失败') : ''
    })

    // 任务成功时刷新图片列表，拉取 TaskProcessor 异步创建的多张图片记录
    if (taskStatus === 'SUCCESS') {
      imageStore.fetchImages().catch(err => console.error('[applyTaskResult] 刷新图片列表失败:', err))
    }

    return taskStatus
  }

  if (taskStatus === 'SUCCESS') {
    imageStore.upsertImage({
      id: `task-${taskId}`,
      task_id: taskId,
      status: taskStatus,
      generating: false,
      error: ''
    })
    // 刷新列表拉取多图
    imageStore.fetchImages().catch(err => console.error('[applyTaskResult] 刷新图片列表失败:', err))
  }

  if (taskStatus === 'FAILURE') {
    imageStore.upsertImage({
      id: existingImage?.id || `task-${taskId}`,
      task_id: taskId,
      status: taskStatus,
      generating: false,
      error: result?.fail_reason || '图片生成失败',
      fail_reason: result?.fail_reason || '图片生成失败'
    })
  }
  return taskStatus
}

const startPolling = (taskId) => {
  if (!taskId || pollingIntervals.has(taskId)) {
    return
  }

  pollingMeta.set(taskId, { attempts: 0, startTime: Date.now() })
  syncPollingState()

  const start = Date.now()

  const poll = async () => {
    if (!pollingIntervals.has(taskId)) {
      return
    }

    const meta = pollingMeta.get(taskId)
    if (!meta) {
      return
    }

    const elapsed = Date.now() - start

    if (meta.attempts > MAX_POLL_ATTEMPTS || elapsed > MAX_POLL_TIME_MS) {
      console.log(`[Polling] Task ${taskId} exceeded limits, stopping`)
      stopPolling(taskId)
      imageStore.upsertImage({
        id: `task-${taskId}`,
        task_id: taskId,
        generating: false,
        error: '查询超时'
      })
      return
    }

    try {
      const result = await queryTask(taskId)

      const taskStatus = applyTaskResult(result, taskId)

      if (FINAL_TASK_STATUSES.has(taskStatus)) {
        stopPolling(taskId)
        return
      }
    } catch (err) {
      console.error(`[Polling] Task ${taskId} error:`, err)
    }

    meta.attempts++
    if (pollingIntervals.has(taskId)) {
      const timer = setTimeout(poll, POLL_INTERVAL_MS)
      pollingIntervals.set(taskId, timer)
    }
  }

  const timer = setTimeout(poll, POLL_INTERVAL_MS)
  pollingIntervals.set(taskId, timer)
}

// 将 payload.size 统一转为 "WxH" 显示字符串和 aspect_ratio
// 功能描述：
//     Fal 模式 size 为 {width, height} 对象，OpenAI 模式为 "WxH" 字符串
//     需要统一转换为显示格式和宽高比，确保卡片以正确尺寸渲染
const parsePayloadSize = (size) => {
  if (!size) return { displaySize: '', aspectRatio: null }
  if (typeof size === 'object' && size.width && size.height) {
    const w = Number(size.width)
    const h = Number(size.height)
    return { displaySize: `${w}x${h}`, aspectRatio: w / h }
  }
  if (typeof size === 'string' && size.includes('x')) {
    const parts = size.split('x')
    const w = parseFloat(parts[0])
    const h = parseFloat(parts[1])
    if (w > 0 && h > 0) {
      return { displaySize: size, aspectRatio: w / h }
    }
  }
  return { displaySize: String(size), aspectRatio: null }
}

const handleGenerateStart = ({ payload, isAsync }) => {
  // 根据 payload.n 或 payload.num_images（Fal 模式）确定生成数量
  const imageCount = payload.n || payload.num_images || 1
  generatingCardIds.value = []

  const { displaySize, aspectRatio } = parsePayloadSize(payload.size)

  for (let i = 0; i < imageCount; i++) {
    const cardId = `generating-${Date.now()}-${i}`
    generatingCardIds.value.push(cardId)

    imageStore.upsertImage({
      id: cardId,
      task_id: '',
      prompt: payload.prompt || '',
      poster_copy: payload.poster_copy || '',
      model: payload.model || '',
      apiSource: payload.api_provider || 'openai',
      size: displaySize,
      aspect_ratio: aspectRatio,
      aspectRatio,
      created_at: new Date().toISOString(),
      status: 'GENERATING',
      generating: true,
      progress: '1%',
      image_type: 'generation',
      imageType: 'generation',
      url: '',
      thumbnail: '',
      error: ''
    })
  }
}

const handleGenerate = async (result) => {
  console.log('[DirectCreateView] handleGenerate received:', JSON.stringify({ task_id: result?.response?.task_id, size: result?.payload?.size }, null, 2))
  const { response, payload, isAsync } = result || {}
  if (!response || !payload) {
    console.error('handleGenerate: 无效的 generate 事件参数', result)
    return
  }

  const taskId = response?.task_id
  const { displaySize, aspectRatio } = parsePayloadSize(payload.size)

  if (isAsync) {
    // 异步模式：所有占位卡片标记为 IN_PROGRESS，启动轮询
    generatingCardIds.value.forEach(cardId => {
      imageStore.upsertImage({
        id: cardId,
        task_id: taskId || '',
        prompt: payload.prompt || '',
        poster_copy: payload.poster_copy || '',
        model: payload.model || '',
        apiSource: payload.api_provider || 'openai',
        size: displaySize,
        aspect_ratio: aspectRatio,
        aspectRatio,
        created_at: new Date().toISOString(),
        status: 'IN_PROGRESS',
        generating: true,
        progress: '3%',
        image_type: 'generation',
        imageType: 'generation',
        url: '',
        thumbnail: '',
        error: ''
      })
    })

    generatingTaskId.value = taskId

    if (taskId) {
      startPolling(taskId)
    }
  } else {
    // 同步模式：从 response.images 数组填充占位卡片
    const allImages = response.images || []
    const firstImage = response.image

    if (allImages.length > 0) {
      // 用返回的图片数组逐一填充占位卡片
      for (let i = 0; i < generatingCardIds.value.length; i++) {
        const cardId = generatingCardIds.value[i]
        const img = allImages[i] || (i === 0 ? firstImage : null)
        if (img) {
          imageStore.upsertImage({
            id: cardId,
            task_id: taskId || '',
            prompt: img.prompt || payload.prompt || '',
            poster_copy: img.poster_copy || payload.poster_copy || '',
            model: payload.model || '',
            apiSource: payload.api_provider || 'openai',
            size: img.size || displaySize,
            aspect_ratio: img.aspect_ratio || aspectRatio,
            aspectRatio: img.aspect_ratio || aspectRatio,
            created_at: new Date().toISOString(),
            status: 'SUCCESS',
            generating: false,
            progress: '100%',
            image_type: 'generation',
            imageType: 'generation',
            url: img.display_url || img.url || '',
            thumbnail: img.thumbnail || '',
            error: ''
          })
        }
      }
    } else if (firstImage) {
      // 兼容旧格式：只有单张 image
      const cardId = generatingCardIds.value[0] || `generating-${Date.now()}`
      imageStore.upsertImage({
        id: cardId,
        task_id: taskId || '',
        prompt: firstImage.prompt || payload.prompt || '',
        poster_copy: firstImage.poster_copy || payload.poster_copy || '',
        model: payload.model || '',
        apiSource: payload.api_provider || 'openai',
        size: firstImage.size || displaySize,
        aspect_ratio: firstImage.aspect_ratio || aspectRatio,
        aspectRatio: firstImage.aspect_ratio || aspectRatio,
        created_at: new Date().toISOString(),
        status: 'SUCCESS',
        generating: false,
        progress: '100%',
        image_type: 'generation',
        imageType: 'generation',
        url: firstImage.display_url || firstImage.url || '',
        thumbnail: firstImage.thumbnail || '',
        error: ''
      })
    }
  }

  generatingCardIds.value = []

  return response
}

// 生成失败时更新所有占位卡片为错误状态
const handleError = (err) => {
  console.error('生成错误:', err)
  const errorMessage = err?.message || err?.error || '图片生成失败，请重试'
  const rawResult = err?.rawResult || null
  if (generatingCardIds.value.length > 0) {
    generatingCardIds.value.forEach(cardId => {
      imageStore.upsertImage({
        id: cardId,
        generating: false,
        error: errorMessage,
        gptsapiRawResult: rawResult
      })
    })
    generatingCardIds.value = []
  }
}

const handleImageSelect = async (image) => {
  const taskId = getTaskId(image)
  if (image.generating && taskId) {
    startPolling(taskId)
  }
}

const handleImagePreview = (image) => {
  previewImage.value = {
    ...image,
    url: image.url || image.display_url || '',
    thumbnail: image.thumbnail || ''
  }
}

const handleImageDelete = async (imageId) => {
  try {
    await imageStore.deleteImage(imageId)
    // 如果在文件夹视图中，同步从本地数据中移除，使删除立即生效
    if (currentFolderId.value !== 'all' && folderImages.value) {
      folderImages.value = folderImages.value.filter(img => img.id !== imageId)
    }
    imageLibraryRef.value?.refreshFolders()
  } catch (err) {
    console.error('删除图片失败:', err)
  }
}

const handleImageEdit = (image) => {
  router.push(`/edit/${image.id}`)
}

const handleImageRename = async (image) => {
  const imageId = image.id || image
  renamingImageId.value = imageId
  const imageData = imageStore.images.find(img => img.id === imageId)
  newImageTitle.value = imageData?.title || imageData?.prompt || ''
  showRenameModal.value = true
  await nextTick()
  renameInputRef.value?.focus()
  renameInputRef.value?.select()
}

const closeRenameModal = () => {
  showRenameModal.value = false
  newImageTitle.value = ''
  renamingImageId.value = null
}

const confirmRename = async () => {
  if (!newImageTitle.value.trim() || !renamingImageId.value) return

  try {
    const result = await renameImage(renamingImageId.value, newImageTitle.value.trim())
    if (result) {
      imageStore.upsertImage({
        id: renamingImageId.value,
        title: newImageTitle.value.trim(),
        prompt: newImageTitle.value.trim()
      })
    }
  } catch (err) {
    console.error('重命名失败:', err)
  }

  closeRenameModal()
}

const handleReusePrompt = (promptText) => {
  imageGeneratorRef.value?.setPrompt(promptText)
}

const handleBatchReference = (materials) => {
  imageGeneratorRef.value?.addReferenceImages(materials)
}

const handleSelectFolder = async (folderId) => {
  // 如果已经是当前文件夹且已加载过，跳过重复加载
  if (currentFolderId.value === folderId && folderImages.value !== null && folderId !== 'all') {
    return
  }
  currentFolderId.value = folderId
  folderImages.value = null
  if (folderId === 'all') {
    imageStore.fetchImages()
    return
  }
  try {
    const result = await getFolderImages(folderId)
    if (result?.success && result?.data) {
      folderImages.value = result.data.map((img) => ({
        ...img,
        url: img.url || img.local_url || '',
        thumbnail: img.thumbnail || img.preview_url || '',
        local_path: img.local_path || img.local_url || ''
      }))
    }
  } catch (e) {
    console.error('获取文件夹图片失败:', e)
    folderImages.value = []
  }
}

const handleEnterRecycleBin = () => {
  folderImages.value = null
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
      const platform = image.apiSource === 'fal' ? 'Fal' : image.apiSource === 'gptsapi' ? 'GPTsAPI' : 'T8'
      const copyText = image.prompt || ''
      const posterCopy = image.poster_copy || ''
      try {
        await api.post('/api/preparation/copy-from', {
          image_url: imageUrl,
          display_name: displayName,
          platform: platform,
          copy_text: copyText,
          poster_copy: posterCopy
        })
        openConfirmDialog({
          title: '添加成功',
          message: '已添加到预备目录',
          confirmText: '确定',
          cancelText: '',
          onConfirm: () => {}
        })
      } catch (e) {
        openConfirmDialog({
          title: '添加失败',
          message: '添加到预备目录失败：' + (e.message || '未知错误'),
          confirmText: '确定',
          cancelText: '',
          danger: true,
          onConfirm: () => {}
        })
      }
    }
  })
}

const handleRefresh = () => {
  currentFolderId.value = 'all'
  folderImages.value = null
  imageStore.fetchImages()
}

const handleImageRefresh = async (image) => {
  const imageId = image.id
  const taskId = getTaskId(image)
  if (!imageId) {
    return
  }

  const userInputUrl = prompt('请输入图片URL（留空则尝试重新查询任务）：')

  if (userInputUrl === null) {
    return
  }

  if (userInputUrl.trim()) {
    try {
      const refreshResult = await refreshImage(imageId, userInputUrl.trim())
      const updatedImage = refreshResult?.image || refreshResult
      if (updatedImage) {
        imageStore.upsertImage(updatedImage)
      }
    } catch (err) {
      console.error('刷新图片失败:', err)
      alert('刷新失败，请重试')
    }
    return
  }

  if (!taskId) {
    alert('该图片没有关联的任务，无法重新查询')
    return
  }

  try {
    const result = await queryTask(taskId)
    applyTaskResult(result, taskId)
  } catch (err) {
    console.error('查询任务失败:', err)
    alert('查询任务失败，请重试')
  }
}

const handleGptsapiRetry = async (image) => {
  const rawResult = image.gptsapiRawResult
  if (!rawResult) {
    openConfirmDialog({
      title: '无法重试',
      message: '缺少 GPTsAPI 原始响应数据，请重新生成',
      confirmText: '确定',
      cancelText: '',
      onConfirm: () => {}
    })
    return
  }

  try {
    const response = await gptsapiRetry({
      raw_result: rawResult,
      prompt: image.prompt || '',
      model: image.model || 'gptsapi/gpt-image-2',
      size: image.size || '',
      aspect_ratio: image.aspect_ratio || image.aspectRatio || '',
      image_type: image.imageType || image.image_type || 'generation'
    })

    const updatedImage = response?.image || response
    if (updatedImage) {
      imageStore.upsertImage({
        ...updatedImage,
        id: image.id,
        status: 'SUCCESS',
        generating: false,
        error: ''
      })
    }

    openConfirmDialog({
      title: '重试成功',
      message: '已成功获取图片',
      confirmText: '确定',
      cancelText: '',
      onConfirm: () => {}
    })
  } catch (err) {
    openConfirmDialog({
      title: '重试失败',
      message: err?.response?.data?.error || err.message || '重试失败，请稍后重试',
      confirmText: '确定',
      cancelText: '',
      danger: true,
      onConfirm: () => {}
    })
  }
}

// 根据初始状态决定加载文件夹图片或全部图片
onMounted(async () => {
  if (currentFolderId.value !== 'all') {
    isFolderLoading.value = true
    try {
      await handleSelectFolder(currentFolderId.value)
    } finally {
      isFolderLoading.value = false
    }
  } else {
    imageStore.fetchImages()
  }

  const cachedImages = imageStore.images
  for (const img of cachedImages) {
    const taskId = getTaskId(img)
    if (img.generating && taskId && !pollingIntervals.has(taskId)) {
      startPolling(taskId)
    }
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style lang="scss">
@import '@/styles/CreateView.scss';
</style>
