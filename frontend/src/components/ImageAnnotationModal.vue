<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="image-annotation-modal-overlay"
      @click="handleClose"
    >
      <div
        class="image-annotation-modal"
        @click.stop
      >
        <div class="image-annotation-modal__header">
          <div>
            <h2 class="image-annotation-modal__title">图片标注与遮罩</h2>
            <p class="image-annotation-modal__subtitle">放大查看后可使用标注或遮罩标出需要修改的位置</p>
          </div>
          <button
            class="image-annotation-modal__close-btn"
            type="button"
            @click="handleClose"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="image-annotation-modal__content">
          <div class="image-annotation-modal__canvas-panel">
            <div class="image-annotation-modal__canvas-shell">
              <img
                v-if="currentImage && !imageLoadError"
                ref="imageRef"
                :src="currentImage"
                class="image-annotation-modal__image"
                alt="待标注图片"
                crossorigin="anonymous"
                @load="handleImageLoad"
                @error="handleImageError"
              />
              <div
                v-else
                class="image-annotation-modal__image-error"
              >
                {{ currentImage ? '图片加载失败，请重新选择后再试' : '当前没有可标注的图片' }}
              </div>

              <canvas
                v-show="currentImage && !imageLoadError"
                ref="canvasRef"
                class="image-annotation-modal__canvas"
                @mousedown="startDrawing"
                @mousemove="draw"
                @mouseup="stopDrawing"
                @mouseleave="stopDrawing"
                @touchstart.prevent="startDrawing"
                @touchmove.prevent="draw"
                @touchend="stopDrawing"
              ></canvas>

              <canvas
                v-show="currentImage && !imageLoadError"
                ref="maskCanvasRef"
                class="image-annotation-modal__mask-canvas"
                @mousedown="startDrawing"
                @mousemove="draw"
                @mouseup="stopDrawing"
                @mouseleave="stopDrawing"
                @touchstart.prevent="startDrawing"
                @touchmove.prevent="draw"
                @touchend="stopDrawing"
              ></canvas>
            </div>
          </div>

          <aside class="image-annotation-modal__tools">
            <section class="image-annotation-modal__tool-group">
              <div class="image-annotation-modal__mode-tabs">
                <button
                  class="image-annotation-modal__mode-tab"
                  :class="{ 'image-annotation-modal__mode-tab--active': mode === 'annotation' }"
                  type="button"
                  :disabled="loading"
                  @click="mode = 'annotation'"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path>
                  </svg>
                  <span>标注</span>
                </button>
                <button
                  class="image-annotation-modal__mode-tab"
                  :class="{ 'image-annotation-modal__mode-tab--active': mode === 'mask' }"
                  type="button"
                  :disabled="loading"
                  @click="mode = 'mask'"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="3" width="18" height="18" rx="3"></rect>
                    <circle cx="12" cy="12" r="4" fill="currentColor"></circle>
                  </svg>
                  <span>遮罩</span>
                </button>
              </div>
            </section>

            <template v-if="mode === 'annotation'">
              <section class="image-annotation-modal__tool-group">
                <h3 class="image-annotation-modal__tool-title">标注颜色</h3>
                <div class="image-annotation-modal__color-row">
                  <input
                    v-model="brushColor"
                    class="image-annotation-modal__color-input"
                    type="color"
                    :disabled="loading"
                  />
                  <span class="image-annotation-modal__color-value">{{ brushColor.toUpperCase() }}</span>
                </div>
              </section>

              <section class="image-annotation-modal__tool-group">
                <h3 class="image-annotation-modal__tool-title">画笔粗细: {{ brushSize }}px</h3>
                <input
                  v-model.number="brushSize"
                  class="image-annotation-modal__slider"
                  type="range"
                  min="4"
                  max="48"
                  :disabled="loading"
                />
              </section>

              <section class="image-annotation-modal__tool-group">
                <h3 class="image-annotation-modal__tool-title">使用提示</h3>
                <p class="image-annotation-modal__hint">
                  推荐直接圈出需要改动的位置，再配合文字描述一起提交。
                </p>
              </section>
            </template>

            <template v-else>
              <section class="image-annotation-modal__tool-group">
                <h3 class="image-annotation-modal__tool-title">画笔工具</h3>
                <div class="image-annotation-modal__tool-buttons">
                  <button
                    class="image-annotation-modal__tool-btn"
                    :class="{ 'image-annotation-modal__tool-btn--active': tool === 'brush' }"
                    type="button"
                    :disabled="loading"
                    @click="tool = 'brush'"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path>
                    </svg>
                    <span>画笔</span>
                  </button>
                  <button
                    class="image-annotation-modal__tool-btn"
                    :class="{ 'image-annotation-modal__tool-btn--active': tool === 'eraser' }"
                    type="button"
                    :disabled="loading"
                    @click="tool = 'eraser'"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M20 20H7L3 16C2.5 15.5 2.5 14.5 3 14L11 6C11.5 5.5 12.5 5.5 13 6L21 14C21.5 14.5 21.5 15.5 21 16L20 17H7"></path>
                    </svg>
                    <span>橡皮擦</span>
                  </button>
                </div>
              </section>

              <section class="image-annotation-modal__tool-group">
                <h3 class="image-annotation-modal__tool-title">画笔类型</h3>
                <div class="image-annotation-modal__tool-buttons">
                  <button
                    class="image-annotation-modal__tool-btn"
                    :class="{ 'image-annotation-modal__tool-btn--active': brushShape === 'circle' }"
                    type="button"
                    :disabled="loading"
                    @click="brushShape = 'circle'"
                  >
                    <svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="5"></circle>
                    </svg>
                    <span>圆形</span>
                  </button>
                  <button
                    class="image-annotation-modal__tool-btn"
                    :class="{ 'image-annotation-modal__tool-btn--active': brushShape === 'square' }"
                    type="button"
                    :disabled="loading"
                    @click="brushShape = 'square'"
                  >
                    <svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2">
                      <rect x="7" y="7" width="10" height="10"></rect>
                    </svg>
                    <span>方形</span>
                  </button>
                </div>
              </section>

              <section class="image-annotation-modal__tool-group">
                <h3 class="image-annotation-modal__tool-title">画笔大小: {{ brushSize }}px</h3>
                <input
                  v-model.number="brushSize"
                  class="image-annotation-modal__slider"
                  type="range"
                  min="4"
                  max="48"
                  :disabled="loading"
                />
              </section>

              <section v-if="tool === 'eraser'" class="image-annotation-modal__tool-group">
                <h3 class="image-annotation-modal__tool-title">橡皮擦大小: {{ eraserSize }}px</h3>
                <input
                  v-model.number="eraserSize"
                  class="image-annotation-modal__slider"
                  type="range"
                  min="4"
                  max="48"
                  :disabled="loading"
                />
              </section>

              <section class="image-annotation-modal__tool-group">
                <div class="image-annotation-modal__action-buttons">
                  <button
                    class="image-annotation-modal__action-btn image-annotation-modal__action-btn--secondary"
                    type="button"
                    :disabled="loading || maskHistoryStack.length <= 1"
                    @click="handleMaskUndo"
                  >
                    撤销
                  </button>
                  <button
                    class="image-annotation-modal__action-btn image-annotation-modal__action-btn--secondary"
                    type="button"
                    :disabled="loading"
                    @click="handleInvertMask"
                  >
                    反转
                  </button>
                  <button
                    class="image-annotation-modal__action-btn image-annotation-modal__action-btn--danger"
                    type="button"
                    :disabled="loading"
                    @click="handleMaskClear"
                  >
                    清空
                  </button>
                </div>
              </section>

              <section class="image-annotation-modal__tool-group">
                <h3 class="image-annotation-modal__tool-title">使用提示</h3>
                <p class="image-annotation-modal__hint">
                  用白色画笔涂抹需要修改的区域，黑色（透明）部分保持不变。点击「反转」可快速互换编辑区与非编辑区。
                </p>
              </section>
            </template>

            <section class="image-annotation-modal__tool-group">
              <div class="image-annotation-modal__action-buttons">
                <button
                  class="image-annotation-modal__action-btn image-annotation-modal__action-btn--secondary"
                  type="button"
                  :disabled="loading || annotationHistoryStack.length <= 1"
                  @click="handleAnnotationUndo"
                >
                  撤销标注
                </button>
                <button
                  class="image-annotation-modal__action-btn image-annotation-modal__action-btn--danger"
                  type="button"
                  :disabled="loading"
                  @click="handleAnnotationClear"
                >
                  清空标注
                </button>
              </div>
            </section>
          </aside>
        </div>

        <div class="image-annotation-modal__footer">
          <button
            class="image-annotation-modal__btn image-annotation-modal__btn--secondary"
            type="button"
            :disabled="loading"
            @click="handleClose"
          >
            取消
          </button>
          <button
            v-if="mode === 'annotation'"
            class="image-annotation-modal__btn image-annotation-modal__btn--primary"
            type="button"
            :disabled="loading || saving || imageLoadError || !currentImage || annotationHistoryStack.length <= 1"
            @click="handleSaveAnnotation"
          >
            {{ loading ? '保存中...' : '保存标注' }}
          </button>
          <button
            v-if="mode === 'mask'"
            class="image-annotation-modal__btn image-annotation-modal__btn--primary"
            type="button"
            :disabled="loading || saving || imageLoadError || !currentImage"
            @click="handleSaveMask"
          >
            {{ loading ? '保存中...' : '保存遮罩' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch, computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  imageUrl: {
    type: String,
    default: ''
  },
  saving: {
    type: Boolean,
    default: false
  },
  maskImage: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close', 'save'])

const imageRef = ref(null)
const canvasRef = ref(null)
const maskCanvasRef = ref(null)
const currentImage = ref('')
const imageLoadError = ref(false)
const isDrawing = ref(false)
const mode = ref('annotation')
const brushColor = ref('#ff3b30')
const brushSize = ref(10)
const tool = ref('brush')
const brushShape = ref('circle')
const eraserSize = ref(15)
const annotationHistoryStack = ref([])
const maskHistoryStack = ref([])
const loading = ref(false)
const isMaskDirty = ref(false)

const MAX_HISTORY = 20

const activeCanvasRef = () => {
  return mode.value === 'mask' ? maskCanvasRef.value : canvasRef.value
}

const activeHistoryStack = () => {
  return mode.value === 'mask' ? maskHistoryStack : annotationHistoryStack
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      currentImage.value = props.imageUrl
      imageLoadError.value = false
      annotationHistoryStack.value = []
      maskHistoryStack.value = []
      isMaskDirty.value = false
      mode.value = 'annotation'
      nextTick(() => {
        initBothCanvases()
        if (props.maskImage) {
          nextTick(() => restoreMaskFromBase64(props.maskImage))
        }
      })
      return
    }

    imageLoadError.value = false
    annotationHistoryStack.value = []
    maskHistoryStack.value = []
    isMaskDirty.value = false
    loading.value = false
    clearBothCanvases()
  }
)

watch(
  () => props.imageUrl,
  (imageUrl) => {
    if (!props.visible) {
      return
    }

    currentImage.value = imageUrl
    imageLoadError.value = false
    annotationHistoryStack.value = []
    maskHistoryStack.value = []
    isMaskDirty.value = false
    mode.value = 'annotation'
    nextTick(() => {
      initBothCanvases()
      if (props.maskImage) {
        nextTick(() => restoreMaskFromBase64(props.maskImage))
      }
    })
  }
)

const syncCanvasDisplay = () => {
  if (!canvasRef.value || !imageRef.value) {
    return
  }

  const canvas = canvasRef.value
  const image = imageRef.value
  const container = image.parentElement

  if (!container) {
    return
  }

  const imageRect = image.getBoundingClientRect()
  const containerRect = container.getBoundingClientRect()

  if (imageRect.width <= 0 || imageRect.height <= 0) {
    return
  }

  const w = `${imageRect.width}px`
  const h = `${imageRect.height}px`
  const left = `${imageRect.left - containerRect.left}px`
  const top = `${imageRect.top - containerRect.top}px`

  canvas.style.width = w
  canvas.style.height = h
  canvas.style.left = left
  canvas.style.top = top

  if (maskCanvasRef.value) {
    maskCanvasRef.value.style.width = w
    maskCanvasRef.value.style.height = h
    maskCanvasRef.value.style.left = left
    maskCanvasRef.value.style.top = top
  }
}

const initMaskCanvas = () => {
  if (!maskCanvasRef.value || !imageRef.value) {
    return
  }

  const image = imageRef.value
  const canvas = maskCanvasRef.value

  if (!image.naturalWidth || !image.naturalHeight) {
    return
  }

  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight

  const context = canvas.getContext('2d')
  context.clearRect(0, 0, canvas.width, canvas.height)
  saveMaskHistory()
}

const initAnnotationCanvas = () => {
  if (!canvasRef.value || !imageRef.value) {
    return
  }

  const image = imageRef.value
  const canvas = canvasRef.value

  if (!image.naturalWidth || !image.naturalHeight) {
    return
  }

  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight

  const context = canvas.getContext('2d')
  context.clearRect(0, 0, canvas.width, canvas.height)
  saveAnnotationHistory()
}

const initBothCanvases = () => {
  syncCanvasDisplay()
  initAnnotationCanvas()
  initMaskCanvas()
}

const clearCanvas = (canvas) => {
  if (!canvas) {
    return
  }

  const context = canvas.getContext('2d')
  context.clearRect(0, 0, canvas.width, canvas.height)
}

const clearBothCanvases = () => {
  clearCanvas(canvasRef.value)
  clearCanvas(maskCanvasRef.value)
}

// 从 base64 data URL 恢复遮罩到 maskCanvas 上
const restoreMaskFromBase64 = (dataUrl) => {
  if (!dataUrl || !maskCanvasRef.value) {
    return
  }

  const img = new Image()
  img.onload = () => {
    const canvas = maskCanvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    maskHistoryStack.value.push(canvas.toDataURL('image/png'))
    isMaskDirty.value = true
  }
  img.onerror = () => {
    console.warn('恢复遮罩失败: 图片加载错误')
  }
  img.src = dataUrl
}

const saveAnnotationHistory = () => {
  if (!canvasRef.value) {
    return
  }

  annotationHistoryStack.value.push(canvasRef.value.toDataURL('image/png'))

  if (annotationHistoryStack.value.length > MAX_HISTORY) {
    annotationHistoryStack.value.shift()
  }
}

const saveMaskHistory = () => {
  if (!maskCanvasRef.value) {
    return
  }

  maskHistoryStack.value.push(maskCanvasRef.value.toDataURL('image/png'))

  if (maskHistoryStack.value.length > MAX_HISTORY) {
    maskHistoryStack.value.shift()
  }
}

const restoreCanvasState = (dataUrl, canvas) => {
  if (!canvas) {
    return
  }

  const context = canvas.getContext('2d')
  const image = new Image()

  image.onload = () => {
    context.clearRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
  }

  image.src = dataUrl
}

const handleAnnotationUndo = () => {
  if (annotationHistoryStack.value.length <= 1) {
    return
  }

  annotationHistoryStack.value.pop()
  restoreCanvasState(annotationHistoryStack.value[annotationHistoryStack.value.length - 1], canvasRef.value)
}

const handleMaskUndo = () => {
  if (maskHistoryStack.value.length <= 1) {
    return
  }

  maskHistoryStack.value.pop()
  restoreCanvasState(maskHistoryStack.value[maskHistoryStack.value.length - 1], maskCanvasRef.value)
  isMaskDirty.value = maskHistoryStack.value.length > 1
}

const handleAnnotationClear = () => {
  saveAnnotationHistory()
  clearCanvas(canvasRef.value)
}

const handleMaskClear = () => {
  saveMaskHistory()
  clearCanvas(maskCanvasRef.value)
  isMaskDirty.value = maskHistoryStack.value.length > 1
}

const getCanvasCoordinates = (event, canvas) => {
  if (!canvas) {
    return null
  }

  const rect = canvas.getBoundingClientRect()
  let clientX = event.clientX
  let clientY = event.clientY

  if (event.touches?.length) {
    clientX = event.touches[0].clientX
    clientY = event.touches[0].clientY
  }

  if (
    clientX < rect.left ||
    clientX > rect.right ||
    clientY < rect.top ||
    clientY > rect.bottom ||
    rect.width <= 0 ||
    rect.height <= 0
  ) {
    return null
  }

  return {
    x: ((clientX - rect.left) * canvas.width) / rect.width,
    y: ((clientY - rect.top) * canvas.height) / rect.height
  }
}

const annotationLastPoint = ref(null)
const maskLastPoint = ref(null)

const getLastPoint = () => {
  return mode.value === 'mask' ? maskLastPoint : annotationLastPoint
}

const startDrawing = (event) => {
  if (loading.value) {
    return
  }

  const canvas = activeCanvasRef()
  const point = getCanvasCoordinates(event, canvas)
  if (!point) {
    return
  }

  if (mode.value === 'annotation') {
    saveAnnotationHistory()
  } else {
    saveMaskHistory()
    isMaskDirty.value = true
  }

  getLastPoint().value = point
  isDrawing.value = true
  drawDot(point.x, point.y)
}

const draw = (event) => {
  if (!isDrawing.value || loading.value) {
    return
  }

  const canvas = activeCanvasRef()
  const point = getCanvasCoordinates(event, canvas)
  const lastPoint = getLastPoint().value
  if (!point || !lastPoint) {
    return
  }

  drawLine(lastPoint.x, lastPoint.y, point.x, point.y)
  getLastPoint().value = point
}

const stopDrawing = () => {
  isDrawing.value = false
  annotationLastPoint.value = null
  maskLastPoint.value = null
}

const drawDot = (x, y) => {
  const canvas = activeCanvasRef()
  if (!canvas) {
    return
  }

  const context = canvas.getContext('2d')

  if (mode.value === 'annotation') {
    context.beginPath()
    context.fillStyle = brushColor.value
    context.arc(x, y, brushSize.value, 0, Math.PI * 2)
    context.fill()
    return
  }

  const size = tool.value === 'brush' ? brushSize.value : eraserSize.value

  context.beginPath()

  if (brushShape.value === 'circle') {
    context.arc(x, y, size, 0, Math.PI * 2)
  } else {
    context.rect(x - size, y - size, size * 2, size * 2)
  }

  if (tool.value === 'brush') {
    context.fillStyle = 'rgba(255, 255, 255, 1)'
  } else {
    context.fillStyle = 'rgba(0, 0, 0, 1)'
    context.globalCompositeOperation = 'destination-out'
  }

  context.fill()
  context.globalCompositeOperation = 'source-over'
}

const drawLine = (fromX, fromY, toX, toY) => {
  const canvas = activeCanvasRef()
  if (!canvas) {
    return
  }

  const context = canvas.getContext('2d')

  if (mode.value === 'annotation') {
    context.strokeStyle = brushColor.value
    context.lineWidth = brushSize.value * 2
    context.lineCap = 'round'
    context.lineJoin = 'round'
    context.beginPath()
    context.moveTo(fromX, fromY)
    context.lineTo(toX, toY)
    context.stroke()
    return
  }

  const size = tool.value === 'brush' ? brushSize.value : eraserSize.value

  context.lineWidth = size * 2
  context.lineCap = 'round'
  context.lineJoin = 'round'
  context.beginPath()
  context.moveTo(fromX, fromY)
  context.lineTo(toX, toY)

  if (tool.value === 'brush') {
    context.strokeStyle = 'rgba(255, 255, 255, 1)'
  } else {
    context.strokeStyle = 'rgba(0, 0, 0, 1)'
    context.globalCompositeOperation = 'destination-out'
  }

  context.stroke()
  context.globalCompositeOperation = 'source-over'
}

const handleInvertMask = () => {
  const canvas = maskCanvasRef.value
  if (!canvas) {
    return
  }

  saveMaskHistory()
  isMaskDirty.value = true

  const context = canvas.getContext('2d')
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height)
  const data = imageData.data

  for (let i = 0; i < data.length; i += 4) {
    const alpha = data[i + 3]
    if (alpha > 128) {
      data[i + 3] = 0
      data[i] = 0
      data[i + 1] = 0
      data[i + 2] = 0
    } else {
      data[i + 3] = 255
      data[i] = 255
      data[i + 1] = 255
      data[i + 2] = 255
    }
  }

  context.putImageData(imageData, 0, 0)
}

const handleImageLoad = () => {
  imageLoadError.value = false
  initBothCanvases()
  if (props.maskImage) {
    nextTick(() => restoreMaskFromBase64(props.maskImage))
  }
}

const handleImageError = () => {
  imageLoadError.value = true
  clearBothCanvases()
}

const handleWindowResize = () => {
  if (!props.visible) {
    return
  }

  nextTick(() => {
    syncCanvasDisplay()
  })
}

const handleClose = () => {
  stopDrawing()
  emit('close')
}

const createMergedImage = () => {
  if (!imageRef.value || !canvasRef.value) {
    return ''
  }

  const exportCanvas = document.createElement('canvas')
  const exportContext = exportCanvas.getContext('2d')

  exportCanvas.width = imageRef.value.naturalWidth
  exportCanvas.height = imageRef.value.naturalHeight
  exportContext.drawImage(imageRef.value, 0, 0, exportCanvas.width, exportCanvas.height)
  exportContext.drawImage(canvasRef.value, 0, 0, exportCanvas.width, exportCanvas.height)

  return exportCanvas.toDataURL('image/png')
}

const getMaskImageData = () => {
  if (!maskCanvasRef.value) {
    return null
  }

  const canvas = maskCanvasRef.value
  const context = canvas.getContext('2d')
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height)
  const data = imageData.data
  let hasContent = false

  for (let i = 3; i < data.length; i += 4) {
    if (data[i] > 0) {
      hasContent = true
      break
    }
  }

  if (!hasContent) {
    return null
  }

  return canvas.toDataURL('image/png')
}

// 仅保存标注图
const handleSaveAnnotation = () => {
  if (annotationHistoryStack.value.length <= 1) {
    return
  }

  loading.value = true

  try {
    const annotatedImage = createMergedImage()

    emit('save', {
      imageUrl: props.imageUrl,
      annotatedImage
    })
    loading.value = false
  } catch (e) {
    console.error('保存标注失败:', e)
    loading.value = false
  }
}

// 仅保存遮罩图
const handleSaveMask = () => {
  const maskData = getMaskImageData()
  if (!maskData) {
    return
  }

  loading.value = true

  try {
    emit('save', {
      imageUrl: props.imageUrl,
      maskImage: maskData
    })
    loading.value = false
  } catch (e) {
    console.error('保存遮罩失败:', e)
    loading.value = false
  }
}

const handleKeydown = (event) => {
  if (event.key === 'Escape' && props.visible) {
    handleClose()
  }
}

onMounted(() => {
  window.addEventListener('resize', handleWindowResize)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleWindowResize)
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables' as *;
@use '@/styles/mixins' as *;

.image-annotation-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $spacing-lg;
  background:
    radial-gradient(circle at top, rgba($color-primary, 0.14), transparent 38%),
    rgba(11, 16, 27, 0.78);
  backdrop-filter: blur(14px);
}

.image-annotation-modal {
  width: min(1180px, 100%);
  max-height: min(860px, calc(100vh - 32px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(19, 25, 39, 0.98), rgba(11, 16, 27, 0.98));
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.image-annotation-modal__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: $spacing-lg;
  padding: $spacing-lg $spacing-xl;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.image-annotation-modal__title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #f6f8ff;
  letter-spacing: -0.03em;
}

.image-annotation-modal__subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: rgba(232, 237, 255, 0.72);
}

.image-annotation-modal__close-btn {
  @include flex-center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.78);
  cursor: pointer;
  transition: transform $transition-fast, background $transition-fast, border-color $transition-fast;

  &:hover {
    transform: translateY(-1px);
    border-color: rgba(255, 255, 255, 0.16);
    background: rgba(255, 255, 255, 0.08);
  }

  svg {
    width: 18px;
    height: 18px;
  }
}

.image-annotation-modal__content {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: $spacing-lg;
  min-height: 0;
  padding: $spacing-lg;
}

.image-annotation-modal__canvas-panel {
  min-width: 0;
  min-height: 0;
}

.image-annotation-modal__canvas-shell {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 520px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.02)),
    linear-gradient(45deg, rgba(255, 255, 255, 0.015) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.015) 75%),
    linear-gradient(45deg, rgba(255, 255, 255, 0.015) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.015) 75%);
  background-size: auto, 28px 28px, 28px 28px;
  background-position: 0 0, 0 0, 14px 14px;
}

.image-annotation-modal__image {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
}

.image-annotation-modal__canvas {
  position: absolute;
  top: 0;
  left: 0;
  cursor: crosshair;
}

.image-annotation-modal__mask-canvas {
  position: absolute;
  top: 0;
  left: 0;
  cursor: crosshair;
  opacity: 0.6;
}

.image-annotation-modal__image-error {
  max-width: 480px;
  padding: $spacing-xl;
  font-size: 14px;
  line-height: 1.7;
  text-align: center;
  color: rgba(232, 237, 255, 0.72);
}

.image-annotation-modal__tools {
  display: flex;
  flex-direction: column;
  gap: $spacing-md;
  overflow-y: auto;
}

.image-annotation-modal__tool-group {
  padding: $spacing-md;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.03));
}

.image-annotation-modal__mode-tabs {
  display: flex;
  gap: $spacing-sm;
}

.image-annotation-modal__mode-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: $spacing-xs;
  padding: $spacing-sm;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: all $transition-fast;
  font-size: 13px;
  font-weight: 600;

  svg {
    width: 16px;
    height: 16px;
  }

  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.9);
  }

  &--active {
    background: linear-gradient(135deg, #ff4b45 0%, #ff7d4d 100%);
    border-color: transparent;
    color: #ffffff;

    &:hover:not(:disabled) {
      background: linear-gradient(135deg, #ff4b45 0%, #ff7d4d 100%);
      color: #ffffff;
    }
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.image-annotation-modal__tool-title {
  margin: 0 0 $spacing-sm;
  font-size: 12px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.92);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.image-annotation-modal__color-row {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.image-annotation-modal__color-input {
  width: 56px;
  height: 40px;
  padding: 0;
  border: none;
  border-radius: 12px;
  background: transparent;
  cursor: pointer;
}

.image-annotation-modal__color-value {
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.image-annotation-modal__slider {
  width: 100%;
  cursor: pointer;
}

.image-annotation-modal__hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(232, 237, 255, 0.72);
}

.image-annotation-modal__tool-buttons {
  display: flex;
  gap: $spacing-sm;
}

.image-annotation-modal__tool-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: $spacing-sm;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all $transition-fast;

  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.9);
  }

  &--active {
    background: linear-gradient(135deg, #ff4b45 0%, #ff7d4d 100%);
    border-color: transparent;
    color: #ffffff;

    &:hover:not(:disabled) {
      background: linear-gradient(135deg, #ff4b45 0%, #ff7d4d 100%);
      color: #ffffff;
    }
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  svg {
    width: 18px;
    height: 18px;
  }

  span {
    font-size: 11px;
    font-weight: 600;
  }
}

.image-annotation-modal__action-buttons {
  display: flex;
  gap: $spacing-sm;
}

.image-annotation-modal__action-btn,
.image-annotation-modal__btn {
  min-height: 44px;
  padding: 0 18px;
  border: none;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform $transition-fast, box-shadow $transition-fast, opacity $transition-fast, background $transition-fast;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.image-annotation-modal__action-btn {
  flex: 1;
}

.image-annotation-modal__action-btn--secondary,
.image-annotation-modal__btn--secondary {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.88);

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    background: rgba(255, 255, 255, 0.08);
  }
}

.image-annotation-modal__action-btn--danger {
  background: rgba(255, 89, 89, 0.14);
  color: #ff9b9b;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    background: rgba(255, 89, 89, 0.22);
  }
}

.image-annotation-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: $spacing-sm;
  padding: $spacing-lg $spacing-xl;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.image-annotation-modal__btn--primary {
  color: #ffffff;
  background: linear-gradient(135deg, #ff4b45 0%, #ff7d4d 100%);
  box-shadow: 0 14px 32px rgba(255, 97, 70, 0.28);

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 18px 36px rgba(255, 97, 70, 0.34);
  }
}

@media (max-width: 1024px) {
  .image-annotation-modal__content {
    grid-template-columns: 1fr;
  }

  .image-annotation-modal__canvas-shell {
    min-height: 420px;
  }
}

@media (max-width: 640px) {
  .image-annotation-modal-overlay {
    padding: 12px;
  }

  .image-annotation-modal {
    max-height: calc(100vh - 24px);
  }

  .image-annotation-modal__header,
  .image-annotation-modal__footer {
    padding: $spacing-md;
  }

  .image-annotation-modal__content {
    padding: $spacing-md;
  }

  .image-annotation-modal__canvas-shell {
    min-height: 280px;
  }

  .image-annotation-modal__footer {
    flex-direction: column-reverse;
  }

  .image-annotation-modal__btn {
    width: 100%;
  }
}
</style>
