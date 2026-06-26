<template>
  <div v-if="show" class="prompt-template-dialog" @click.self="emitClose">
    <div class="prompt-template-dialog__panel">
      <header class="prompt-template-dialog__header">
        <div>
          <h3>模版</h3>
          <span>{{ activeCategoryName }} · {{ filteredTemplates.length }} 个</span>
        </div>
        <button type="button" class="prompt-template-dialog__icon-btn" @click="emitClose">×</button>
      </header>

      <div class="prompt-template-dialog__body">
        <aside class="prompt-template-dialog__sidebar">
          <button
            v-for="category in categories"
            :key="category.id"
            type="button"
            class="prompt-template-dialog__category"
            :class="{
              'prompt-template-dialog__category--active': activeCategoryId === category.id,
              'prompt-template-dialog__category--drop': draggingTemplateId && draggingOverCategoryId === category.id
            }"
            @click="activeCategoryId = category.id"
            @dragenter.prevent="handleCategoryDragEnter(category.id)"
            @dragover.prevent="handleCategoryDragOver(category.id)"
            @dragleave="handleCategoryDragLeave(category.id)"
            @drop.prevent="handleTemplateDrop(category.id)"
          >
            <span>{{ category.name }}</span>
            <small>{{ templateCountByCategory(category.id) }}</small>
          </button>
          <div class="prompt-template-dialog__category-actions">
            <button type="button" @click="createCategory">新建分类</button>
            <button type="button" :disabled="!activeCategoryId" @click="renameCategory">改名</button>
            <button type="button" :disabled="!canDeleteCategory" @click="removeCategory">删除</button>
          </div>
        </aside>

        <main class="prompt-template-dialog__content">
          <div class="prompt-template-dialog__toolbar">
            <div class="prompt-template-dialog__toolbar-title">
              <strong>模版管理</strong>
              <span>添加、编辑、删除当前分类下的模版</span>
            </div>
            <button type="button" class="prompt-template-dialog__primary prompt-template-dialog__add-template" @click="startCreateTemplate">
              添加模版
            </button>
            <span v-if="error" class="prompt-template-dialog__error">{{ error }}</span>
          </div>

          <div v-if="loading" class="prompt-template-dialog__empty">加载中...</div>
          <div v-else-if="filteredTemplates.length === 0" class="prompt-template-dialog__empty">
            <span>当前分类没有模版</span>
            <button type="button" class="prompt-template-dialog__primary prompt-template-dialog__empty-add" @click="startCreateTemplate">
              添加第一个模版
            </button>
          </div>
          <div v-else class="prompt-template-dialog__grid">
            <article
              v-for="template in filteredTemplates"
              :key="template.id || template.createdAt || template.name"
              class="prompt-template-dialog__card"
              :class="{ 'prompt-template-dialog__card--dragging': draggingTemplateId === template.id }"
              draggable="true"
              @dragstart="handleTemplateDragStart($event, template)"
              @dragend="handleTemplateDragEnd"
            >
              <div class="prompt-template-dialog__thumb">
                <img v-if="template.exampleThumbnail" :src="template.exampleThumbnail" :alt="template.name" />
                <span v-else>无示例图</span>
              </div>
              <div class="prompt-template-dialog__card-body">
                <strong>{{ template.name }}</strong>
                <p>{{ template.prompt || '未填写提示词' }}</p>
                <small>{{ template.apiProvider || '当前API' }} · {{ template.aspectRatio || '当前比例' }} · {{ template.resolution || '当前res' }}</small>
              </div>
              <div v-if="template.exampleThumbnail" class="prompt-template-dialog__hover">
                <img :src="template.exampleThumbnail" :alt="template.name" />
              </div>
              <footer class="prompt-template-dialog__card-actions">
                <button type="button" @click="emitApply(template)">启用</button>
                <button type="button" @click="startEditTemplate(template)">编辑</button>
                <button type="button" class="prompt-template-dialog__danger" @click="removeTemplate(template)">删除</button>
                <button type="button" :disabled="generatingId === template.id" @click="generateExample(template)">
                  {{ generatingId === template.id ? '生成中...' : '生成示例图' }}
                </button>
              </footer>
            </article>
          </div>
        </main>
      </div>

      <Transition name="confirm-dialog">
        <div v-if="editing" class="prompt-template-dialog__editor" @click.self="editing = null">
          <div class="prompt-template-dialog__editor-panel" @click.stop>
          <header>
            <h4>{{ editing.id ? '编辑模版' : '新建模版' }}</h4>
            <button type="button" class="prompt-template-dialog__icon-btn" @click="editing = null">×</button>
          </header>
          <div class="prompt-template-dialog__form">
            <label>
              名称
              <input v-model="editing.name" type="text" />
            </label>
            <label>
              分类
              <select v-model="editing.categoryId">
                <option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option>
              </select>
            </label>
            <label class="prompt-template-dialog__form-full">
              提示词
              <textarea v-model="editing.prompt" rows="5"></textarea>
            </label>
            <label>
              API
              <select v-model="editing.apiProvider">
                <option value="">当前API</option>
                <option value="openai">OpenAI 兼容</option>
                <option value="fal">Fal API</option>
                <option value="gptsapi">GPTsAPI</option>
                <option value="apiyi">APIYI</option>
              </select>
            </label>
            <label>
              模型
              <select v-model="editing.model">
                <option value="">当前模型</option>
                <option v-for="model in editingModelOptions" :key="model" :value="model">{{ model }}</option>
              </select>
            </label>
            <label>
              比例
              <select v-model="editing.aspectRatio">
                <option value="">当前比例</option>
                <option v-for="ratio in aspectRatioOptions" :key="ratio.value" :value="ratio.value">{{ ratio.label }}</option>
              </select>
            </label>
            <label>
              res
              <select v-model="editing.resolution">
                <option value="">当前res</option>
                <option value="1K">1K</option>
                <option value="2K">2K</option>
                <option value="4K">4K</option>
              </select>
            </label>
            <label>
              质量
              <select v-model="editing.quality">
                <option value="">当前质量</option>
                <option value="auto">Auto</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </label>
            <label>
              输出
              <select v-model="editing.outputFormat">
                <option value="">当前输出</option>
                <option value="png">PNG</option>
                <option value="jpeg">JPEG</option>
                <option value="webp">WebP</option>
              </select>
            </label>
            <label>
              压缩率
              <input v-model.number="editing.outputCompression" type="number" min="0" max="100" />
            </label>
            <label>
              背景
              <select v-model="editing.background">
                <option value="">当前背景</option>
                <option value="auto">Auto</option>
                <option value="opaque">Opaque</option>
                <option value="transparent">Transparent</option>
              </select>
            </label>
            <label>
              Moderation
              <select v-model="editing.moderation">
                <option value="">当前Moderation</option>
                <option value="auto">Auto</option>
                <option value="low">Low</option>
              </select>
            </label>

            <section class="prompt-template-dialog__form-full prompt-template-dialog__assets">
              <div>
                <span>示例图</span>
                <button type="button" @click="exampleInput?.click()">上传示例图</button>
                <input ref="exampleInput" type="file" accept="image/jpeg,image/png,image/webp" @change="handleExampleSelect" />
              </div>
              <img v-if="editing.exampleThumbnail || pendingExamplePreview" :src="pendingExamplePreview || editing.exampleThumbnail" alt="示例图" />
            </section>

            <section class="prompt-template-dialog__form-full prompt-template-dialog__assets">
              <div>
                <span>参考图</span>
                <button type="button" @click="referenceInput?.click()">上传参考图</button>
                <input ref="referenceInput" type="file" accept="image/jpeg,image/png,image/webp" multiple @change="handleReferenceSelect" />
              </div>
              <div class="prompt-template-dialog__ref-list">
                <figure v-for="ref in editing.referenceImages" :key="ref.id">
                  <img :src="ref.thumbnail || ref.url" :alt="ref.name" />
                  <button type="button" @click="removeReference(ref.id)">×</button>
                </figure>
              </div>
            </section>
          </div>
          <footer class="prompt-template-dialog__editor-actions">
            <button type="button" class="prompt-template-dialog__dialog-btn prompt-template-dialog__dialog-btn--cancel" @click="editing = null">取消</button>
            <button type="button" class="prompt-template-dialog__primary" :disabled="saving" @click="saveTemplate">
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </footer>
          </div>
        </div>
      </Transition>

      <Transition name="confirm-dialog">
        <div v-if="categoryDialog.visible" class="prompt-template-dialog__editor" @click.self="closeCategoryDialog">
          <div class="prompt-template-dialog__category-dialog" @click.stop>
            <div class="prompt-template-dialog__category-dialog-header">
              <h4>{{ categoryDialog.mode === 'create' ? '新建分类' : '更改分类名称' }}</h4>
            </div>
            <div class="prompt-template-dialog__category-dialog-content">
              <input
                ref="categoryInputRef"
                v-model="categoryDialog.name"
                class="prompt-template-dialog__category-input"
                type="text"
                placeholder="输入分类名称"
                @keyup.enter="confirmCategoryDialog"
              />
            </div>
            <div class="prompt-template-dialog__category-dialog-actions">
              <button type="button" class="prompt-template-dialog__dialog-btn prompt-template-dialog__dialog-btn--cancel" @click="closeCategoryDialog">取消</button>
              <button type="button" class="prompt-template-dialog__dialog-btn prompt-template-dialog__dialog-btn--confirm" @click="confirmCategoryDialog">确定</button>
            </div>
          </div>
        </div>
      </Transition>

      <ConfirmDialog
        :visible="confirmDialog.visible"
        :title="confirmDialog.title"
        :message="confirmDialog.message"
        confirm-text="删除"
        cancel-text="取消"
        danger
        @update:visible="confirmDialog.visible = $event"
        @confirm="confirmDeleteAction"
        @cancel="clearConfirmDialog"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useConfigStore } from '@/stores/configStore'
import {
  createPromptTemplate,
  createPromptTemplateCategory,
  deletePromptTemplate,
  deletePromptTemplateCategory,
  generatePromptTemplateExample,
  getPromptTemplates,
  updatePromptTemplate,
  updatePromptTemplateCategory,
  uploadPromptTemplateExample
} from '@/services/api'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  aspectRatioOptions: {
    type: Array,
    default: () => []
  },
  currentSettings: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['close', 'apply'])
const configStore = useConfigStore()

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const categories = ref([])
const templates = ref([])
const activeCategoryId = ref('')
const editing = ref(null)
const exampleInput = ref(null)
const referenceInput = ref(null)
const pendingExampleData = ref('')
const pendingExamplePreview = ref('')
const generatingId = ref('')
const draggingTemplateId = ref('')
const draggingOverCategoryId = ref('')
const categoryInputRef = ref(null)
const categoryDialog = ref({
  visible: false,
  mode: 'create',
  id: '',
  name: ''
})
const confirmDialog = ref({
  visible: false,
  type: '',
  target: null,
  title: '',
  message: ''
})

const activeCategoryName = computed(() => categories.value.find(item => item.id === activeCategoryId.value)?.name || '未选择分类')
const filteredTemplates = computed(() => templates.value.filter(item => item.categoryId === activeCategoryId.value))
const canDeleteCategory = computed(() => categories.value.length > 1 && activeCategoryId.value && templateCountByCategory(activeCategoryId.value) === 0)
const editingModelOptions = computed(() => {
  const provider = editing.value?.apiProvider || props.currentSettings?.apiProvider || 'openai'
  return getModelsByProvider(provider)
})

watch(() => props.show, (show) => {
  if (show) loadTemplates()
})

watch(() => editing.value?.apiProvider, () => {
  if (!editing.value) return
  if (editing.value.model && !editingModelOptions.value.includes(editing.value.model)) {
    editing.value.model = ''
  }
})

onMounted(() => {
  if (props.show) loadTemplates()
})

function emitClose() {
  emit('close')
}

async function loadTemplates() {
  loading.value = true
  error.value = ''
  try {
    const res = await getPromptTemplates()
    categories.value = Array.isArray(res.categories) ? res.categories : []
    templates.value = Array.isArray(res.templates) ? res.templates : []
    if (!activeCategoryId.value || !categories.value.some(item => item.id === activeCategoryId.value)) {
      activeCategoryId.value = categories.value[0]?.id || ''
    }
  } catch (err) {
    error.value = err.message || '模版加载失败'
  } finally {
    loading.value = false
  }
}

function templateCountByCategory(categoryId) {
  return templates.value.filter(item => item.categoryId === categoryId).length
}

function createDragPreview(template) {
  const preview = document.createElement('div')
  preview.className = 'prompt-template-dialog__drag-preview'
  const image = document.createElement('img')
  image.alt = ''
  if (template.exampleThumbnail) {
    image.src = template.exampleThumbnail
  }
  const label = document.createElement('span')
  label.textContent = template.name || '模版'
  preview.appendChild(image)
  preview.appendChild(label)
  document.body.appendChild(preview)
  return preview
}

function handleTemplateDragStart(event, template) {
  if (!template?.id) {
    event.preventDefault()
    error.value = '模版ID缺失，请刷新后重试'
    return
  }
  if (event.target?.closest?.('button, input, textarea, select')) {
    event.preventDefault()
    return
  }
  draggingTemplateId.value = template.id
  draggingOverCategoryId.value = ''
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', template.id)

  const preview = createDragPreview(template)
  event.dataTransfer.setDragImage(preview, 24, 24)
  window.setTimeout(() => preview.remove(), 0)
}

function handleTemplateDragEnd() {
  draggingTemplateId.value = ''
  draggingOverCategoryId.value = ''
}

function handleCategoryDragEnter(categoryId) {
  if (!draggingTemplateId.value) return
  draggingOverCategoryId.value = categoryId
}

function handleCategoryDragOver(categoryId) {
  if (!draggingTemplateId.value) return
  draggingOverCategoryId.value = categoryId
}

function handleCategoryDragLeave(categoryId) {
  if (draggingOverCategoryId.value === categoryId) {
    draggingOverCategoryId.value = ''
  }
}

async function handleTemplateDrop(categoryId) {
  const templateId = draggingTemplateId.value
  draggingTemplateId.value = ''
  draggingOverCategoryId.value = ''
  if (!templateId || !categoryId) return

  const index = templates.value.findIndex(item => item.id === templateId)
  if (index < 0) return
  const template = templates.value[index]
  if (template.categoryId === categoryId) {
    activeCategoryId.value = categoryId
    return
  }

  const previousCategoryId = template.categoryId
  const nextTemplate = { ...template, categoryId }
  templates.value.splice(index, 1, nextTemplate)
  activeCategoryId.value = categoryId
  error.value = ''

  try {
    const res = await updatePromptTemplate(templateId, nextTemplate)
    const saved = res.template
    const savedIndex = templates.value.findIndex(item => item.id === templateId)
    if (savedIndex >= 0) {
      templates.value.splice(savedIndex, 1, saved)
    }
  } catch (err) {
    const currentIndex = templates.value.findIndex(item => item.id === templateId)
    if (currentIndex >= 0) {
      templates.value.splice(currentIndex, 1, { ...template, categoryId: previousCategoryId })
    }
    activeCategoryId.value = previousCategoryId
    error.value = err.message || '移动模版失败'
  }
}

function getModelsByProvider(provider) {
  if (provider === 'fal') {
    return Array.isArray(configStore.falApi?.falModels) && configStore.falApi.falModels.length > 0
      ? configStore.falApi.falModels
      : ['openai/gpt-image-2']
  }
  if (provider === 'gptsapi') {
    return ['gptsapi/gpt-image-2']
  }
  if (provider === 'apiyi') {
    const configuredModels = Array.isArray(configStore.apiyiApi?.imageModels) && configStore.apiyiApi.imageModels.length > 0
      ? configStore.apiyiApi.imageModels
      : ['gpt-image-2-vip', 'gpt-image-2']
    const mergedModels = Array.from(new Set([...configuredModels, 'gpt-image-2']))
    return mergedModels.map(model => model.startsWith('apiyi/') ? model : `apiyi/${model}`)
  }
  return Array.isArray(configStore.imageApi?.imageModels) && configStore.imageApi.imageModels.length > 0
    ? configStore.imageApi.imageModels
    : ['gpt-image-2']
}

function createCategory() {
  openCategoryDialog('create')
}

function renameCategory() {
  const current = categories.value.find(item => item.id === activeCategoryId.value)
  if (!current) return
  openCategoryDialog('rename', current)
}

function openCategoryDialog(mode, category = null) {
  categoryDialog.value = {
    visible: true,
    mode,
    id: category?.id || '',
    name: category?.name || ''
  }
  nextTick(() => {
    categoryInputRef.value?.focus()
    categoryInputRef.value?.select()
  })
}

function closeCategoryDialog() {
  categoryDialog.value.visible = false
}

async function confirmCategoryDialog() {
  const name = categoryDialog.value.name.trim()
  if (!name) return
  try {
    if (categoryDialog.value.mode === 'create') {
      const res = await createPromptTemplateCategory({ name })
      categories.value.push(res.category)
      activeCategoryId.value = res.category.id
    } else {
      const current = categories.value.find(item => item.id === categoryDialog.value.id)
      if (!current) return
      const res = await updatePromptTemplateCategory(current.id, { name })
      Object.assign(current, res.category)
    }
    closeCategoryDialog()
  } catch (err) {
    error.value = err.message || '分类保存失败'
  }
}

async function removeCategory() {
  if (!canDeleteCategory.value) return
  const current = categories.value.find(item => item.id === activeCategoryId.value)
  confirmDialog.value = {
    visible: true,
    type: 'category',
    target: current,
    title: '删除分类',
    message: `确定删除分类「${current?.name || ''}」吗？`
  }
}

function blankTemplate() {
  const settings = props.currentSettings || {}
  return {
    id: '',
    categoryId: activeCategoryId.value || categories.value[0]?.id || '',
    name: '',
    prompt: '',
    apiProvider: settings.apiProvider || '',
    model: settings.model || '',
    aspectRatio: settings.aspectRatio || '',
    resolution: settings.resolution || '',
    quality: settings.quality || '',
    outputFormat: settings.outputFormat || '',
    outputCompression: settings.outputCompression ?? 100,
    background: settings.background || '',
    moderation: settings.moderation || '',
    referenceImages: [],
    exampleImage: '',
    exampleThumbnail: ''
  }
}

function startCreateTemplate() {
  pendingExampleData.value = ''
  pendingExamplePreview.value = ''
  editing.value = blankTemplate()
}

function startEditTemplate(template) {
  if (!template?.id) {
    error.value = '模版ID缺失，已重新加载模版列表，请再编辑一次'
    loadTemplates()
    return
  }
  pendingExampleData.value = ''
  pendingExamplePreview.value = ''
  editing.value = JSON.parse(JSON.stringify(template))
}

async function saveTemplate() {
  if (!editing.value?.name?.trim()) {
    error.value = '模版名称不能为空'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const payload = { ...editing.value, name: editing.value.name.trim() }
    if (!payload.id && payload.createdAt) {
      error.value = '模版ID缺失，已重新加载模版列表，请再编辑一次'
      editing.value = null
      await loadTemplates()
      return
    }
    const res = payload.id
      ? await updatePromptTemplate(payload.id, payload)
      : await createPromptTemplate(payload)
    let saved = res.template
    if (pendingExampleData.value) {
      const exampleRes = await uploadPromptTemplateExample(saved.id, pendingExampleData.value)
      saved = exampleRes.template
    }
    const index = templates.value.findIndex(item => item.id === saved.id)
    if (index >= 0) {
      templates.value.splice(index, 1, saved)
    } else {
      templates.value.unshift(saved)
    }
    activeCategoryId.value = saved.categoryId
    editing.value = null
    pendingExampleData.value = ''
    pendingExamplePreview.value = ''
  } catch (err) {
    error.value = err.message || '模版保存失败'
  } finally {
    saving.value = false
  }
}

async function removeTemplate(template) {
  if (!template?.id) {
    error.value = '模版ID缺失，请刷新后重试'
    return
  }
  confirmDialog.value = {
    visible: true,
    type: 'template',
    target: template,
    title: '删除模版',
    message: `确定删除模版「${template.name || '未命名模版'}」吗？`
  }
}

function clearConfirmDialog() {
  confirmDialog.value = {
    visible: false,
    type: '',
    target: null,
    title: '',
    message: ''
  }
}

async function confirmDeleteAction() {
  const { type, target } = confirmDialog.value
  try {
    if (type === 'category' && target?.id) {
      await deletePromptTemplateCategory(target.id)
      categories.value = categories.value.filter(item => item.id !== target.id)
      activeCategoryId.value = categories.value[0]?.id || ''
    }
    if (type === 'template') {
      if (!target?.id) {
        error.value = '模版ID缺失，请刷新后重试'
        return
      }
      await deletePromptTemplate(target.id)
      templates.value = templates.value.filter(item => item.id !== target.id)
      await loadTemplates()
    }
  } catch (err) {
    error.value = err.message || '删除失败'
  } finally {
    clearConfirmDialog()
  }
}

function withTimeout(promise, timeoutMs, message) {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error(message)), timeoutMs)
    })
  ])
}

async function generateExample(template) {
  if (generatingId.value) return
  if (!template?.id) {
    error.value = '模版ID缺失，请刷新后重试'
    return
  }
  generatingId.value = template.id
  error.value = ''
  try {
    const res = await withTimeout(
      generatePromptTemplateExample(template.id, props.currentSettings || {}),
      90000,
      '示例图生成超时，请查看后台请求日志或手动上传示例图'
    )
    const index = templates.value.findIndex(item => item.id === template.id)
    if (index >= 0) templates.value.splice(index, 1, res.template)
  } catch (err) {
    error.value = err.message || '示例图生成失败'
  } finally {
    generatingId.value = ''
  }
}

function emitApply(template) {
  emit('apply', template)
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

async function handleExampleSelect(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  pendingExampleData.value = await fileToDataUrl(file)
  pendingExamplePreview.value = pendingExampleData.value
}

async function handleReferenceSelect(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!editing.value) return
  for (const file of files) {
    const dataUrl = await fileToDataUrl(file)
    editing.value.referenceImages.push({
      id: `${Date.now()}_${Math.random()}`,
      url: dataUrl,
      thumbnail: dataUrl,
      name: file.name,
      size: file.size,
      type: file.type || 'image/png'
    })
  }
}

function removeReference(refId) {
  if (!editing.value) return
  editing.value.referenceImages = editing.value.referenceImages.filter(item => item.id !== refId)
}
</script>

<style scoped>
.prompt-template-dialog {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  background: rgba(15, 23, 42, 0.45);
}

.prompt-template-dialog__panel {
  width: min(980px, 100%);
  height: min(760px, 94vh);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #dbe3f1;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.22);
}

.prompt-template-dialog__header,
.prompt-template-dialog__editor-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #e5eaf3;
}

.prompt-template-dialog__header h3,
.prompt-template-dialog__editor-panel h4 {
  margin: 0;
  color: #111827;
  font-size: 16px;
}

.prompt-template-dialog__header span {
  color: #64748b;
  font-size: 12px;
}

.prompt-template-dialog__icon-btn {
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  cursor: pointer;
}

.prompt-template-dialog__body {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  min-height: 0;
  flex: 1;
}

.prompt-template-dialog__sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-right: 1px solid #e5eaf3;
  background: #f8fafc;
}

.prompt-template-dialog__category {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #334155;
  cursor: pointer;
  text-align: left;
}

.prompt-template-dialog__category--active {
  border-color: #8b7cf6;
  background: #eef2ff;
  color: #6153e6;
}

.prompt-template-dialog__category--drop {
  border-color: #7c6cf2;
  background: #e0e7ff;
  box-shadow: inset 0 0 0 1px rgba(124, 108, 242, 0.28);
}

.prompt-template-dialog__category-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-top: auto;
}

.prompt-template-dialog__category-actions button,
.prompt-template-dialog__card-actions button,
.prompt-template-dialog__editor-actions button,
.prompt-template-dialog__assets button {
  min-height: 30px;
  border: 1px solid #dbe3f1;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  cursor: pointer;
}

.prompt-template-dialog__content {
  min-width: 0;
  overflow: auto;
  padding: 12px;
}

.prompt-template-dialog__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.prompt-template-dialog__toolbar-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.prompt-template-dialog__toolbar-title strong {
  color: #111827;
  font-size: 14px;
}

.prompt-template-dialog__toolbar-title span {
  color: #64748b;
  font-size: 12px;
}

.prompt-template-dialog__primary {
  border-color: #7c6cf2 !important;
  background: #7c6cf2 !important;
  color: #ffffff !important;
}

.prompt-template-dialog__add-template {
  min-width: 96px;
  min-height: 34px;
  font-weight: 600;
}

.prompt-template-dialog__error {
  color: #dc2626;
  font-size: 12px;
}

.prompt-template-dialog__empty {
  display: flex;
  min-height: 180px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 36px;
  color: #64748b;
  text-align: center;
}

.prompt-template-dialog__empty-add {
  min-width: 128px;
  min-height: 36px;
  font-weight: 600;
}

.prompt-template-dialog__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 320px));
  gap: 12px;
  justify-content: start;
}

.prompt-template-dialog__card {
  position: relative;
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) auto;
  width: 100%;
  max-width: 320px;
  overflow: visible;
  border: 1px solid #e5eaf3;
  border-radius: 8px;
  background: #ffffff;
  cursor: grab;
}

.prompt-template-dialog__card:active {
  cursor: grabbing;
}

.prompt-template-dialog__card--dragging {
  opacity: 0.42;
  outline: 1px dashed #7c6cf2;
  outline-offset: 2px;
}

.prompt-template-dialog__thumb {
  grid-row: 1 / 3;
  width: 104px;
  min-height: 172px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-right: 1px solid #eef2f7;
  border-radius: 8px 0 0 8px;
  background: #edf2f7;
  color: #94a3b8;
  font-size: 12px;
}

.prompt-template-dialog__thumb img,
.prompt-template-dialog__hover img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #f8fafc;
}

.prompt-template-dialog__card-body {
  min-width: 0;
  padding: 10px 10px 6px;
}

.prompt-template-dialog__card-body strong {
  display: block;
  overflow: hidden;
  color: #111827;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-template-dialog__card-body p {
  height: 36px;
  margin: 6px 0;
  overflow: hidden;
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
}

.prompt-template-dialog__card-body small,
.prompt-template-dialog__hover span {
  color: #64748b;
  font-size: 11px;
}

.prompt-template-dialog__hover {
  position: absolute;
  left: 50%;
  top: 10px;
  z-index: 2;
  display: none;
  pointer-events: none;
  width: max-content;
  max-width: calc(100vw - 48px);
  padding: 8px;
  transform: translateX(-50%);
  border: 1px solid #c7d2fe;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.18);
}

.prompt-template-dialog__hover img {
  display: block;
  width: auto;
  height: auto;
  max-width: min(560px, calc(100vw - 64px));
  max-height: 72vh;
  border-radius: 6px;
  background: #f8fafc;
}

.prompt-template-dialog__thumb:hover ~ .prompt-template-dialog__hover {
  display: block;
}

.prompt-template-dialog__card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  align-self: end;
  padding: 6px 10px 10px;
  border-top: 1px solid #eef2f7;
}

.prompt-template-dialog__danger {
  color: #dc2626 !important;
}

:global(.prompt-template-dialog__drag-preview) {
  position: fixed;
  top: -1000px;
  left: -1000px;
  z-index: -1;
  width: 64px;
  height: 64px;
  display: grid;
  grid-template-rows: 44px 1fr;
  overflow: hidden;
  border: 1px solid rgba(124, 108, 242, 0.35);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.18);
}

:global(.prompt-template-dialog__drag-preview img) {
  width: 100%;
  height: 44px;
  object-fit: contain;
  background: #f8fafc;
}

:global(.prompt-template-dialog__drag-preview span) {
  overflow: hidden;
  padding: 1px 4px;
  color: #334155;
  font-size: 10px;
  line-height: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-template-dialog__editor {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
}

.prompt-template-dialog__editor-panel {
  width: min(720px, 100%);
  max-height: 90vh;
  overflow: auto;
  border-radius: 12px;
  background: #2a2a2a;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.prompt-template-dialog__editor-panel header {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.prompt-template-dialog__editor-panel h4 {
  color: #ffffff;
  font-size: 18px;
}

.prompt-template-dialog__editor-panel .prompt-template-dialog__icon-btn {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
}

.prompt-template-dialog__form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 14px;
}

.prompt-template-dialog__form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: rgba(255, 255, 255, 0.78);
  font-size: 12px;
  font-weight: 600;
}

.prompt-template-dialog__form input,
.prompt-template-dialog__form select,
.prompt-template-dialog__form textarea {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  padding: 8px 10px;
  color: #ffffff;
  font-size: 13px;
}

.prompt-template-dialog__form select option {
  color: #111827;
}

.prompt-template-dialog__form-full {
  grid-column: 1 / -1;
}

.prompt-template-dialog__assets {
  padding: 10px;
  border: 1px dashed rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}

.prompt-template-dialog__assets > div:first-child {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.prompt-template-dialog__assets input {
  display: none;
}

.prompt-template-dialog__assets > img {
  width: 120px;
  height: 90px;
  margin-top: 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  object-fit: contain;
}

.prompt-template-dialog__ref-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.prompt-template-dialog__ref-list figure {
  position: relative;
  width: 70px;
  height: 70px;
  margin: 0;
}

.prompt-template-dialog__ref-list img {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  object-fit: cover;
}

.prompt-template-dialog__ref-list button {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 22px;
  height: 22px;
  min-height: 0;
  padding: 0;
}

.prompt-template-dialog__editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.prompt-template-dialog__editor-actions button {
  min-width: 112px;
  min-height: 40px;
  padding: 0 18px;
  white-space: nowrap;
}

.prompt-template-dialog__dialog-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.prompt-template-dialog__dialog-btn--cancel {
  background: rgba(255, 255, 255, 0.1) !important;
  color: rgba(255, 255, 255, 0.8) !important;
}

.prompt-template-dialog__dialog-btn--cancel:hover {
  background: rgba(255, 255, 255, 0.15) !important;
}

.prompt-template-dialog__dialog-btn--confirm {
  background: #4a9eff;
  color: #ffffff;
}

.prompt-template-dialog__dialog-btn--confirm:hover {
  background: #3a8eef;
}

.prompt-template-dialog__category-dialog {
  width: 360px;
  min-width: 320px;
  max-width: 90vw;
  overflow: hidden;
  border-radius: 12px;
  background: #2a2a2a;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.prompt-template-dialog__category-dialog-header {
  padding: 20px 24px 8px;
}

.prompt-template-dialog__category-dialog-header h4 {
  margin: 0;
  color: #ffffff;
  font-size: 18px;
  font-weight: 600;
}

.prompt-template-dialog__category-dialog-content {
  padding: 12px 24px 4px;
}

.prompt-template-dialog__category-input {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  padding: 10px 12px;
  color: #ffffff;
  font-size: 14px;
  outline: none;
}

.prompt-template-dialog__category-input:focus {
  border-color: rgba(74, 158, 255, 0.55);
  box-shadow: 0 0 0 3px rgba(74, 158, 255, 0.12);
}

.prompt-template-dialog__category-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
}

.confirm-dialog-enter-active,
.confirm-dialog-leave-active {
  transition: opacity 0.2s ease;
}

.confirm-dialog-enter-active .prompt-template-dialog__editor-panel,
.confirm-dialog-leave-active .prompt-template-dialog__editor-panel,
.confirm-dialog-enter-active .prompt-template-dialog__category-dialog,
.confirm-dialog-leave-active .prompt-template-dialog__category-dialog {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.confirm-dialog-enter-from,
.confirm-dialog-leave-to {
  opacity: 0;
}

.confirm-dialog-enter-from .prompt-template-dialog__editor-panel,
.confirm-dialog-leave-to .prompt-template-dialog__editor-panel,
.confirm-dialog-enter-from .prompt-template-dialog__category-dialog,
.confirm-dialog-leave-to .prompt-template-dialog__category-dialog {
  transform: scale(0.95);
  opacity: 0;
}

@media (max-width: 720px) {
  .prompt-template-dialog__body {
    grid-template-columns: 1fr;
  }

  .prompt-template-dialog__sidebar {
    max-height: 160px;
    border-right: 0;
    border-bottom: 1px solid #e5eaf3;
  }

  .prompt-template-dialog__form {
    grid-template-columns: 1fr;
  }

  .prompt-template-dialog__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .prompt-template-dialog__card {
    grid-template-columns: 112px minmax(0, 1fr);
  }

  .prompt-template-dialog__thumb {
    width: 112px;
  }

  .prompt-template-dialog__hover img {
    max-width: calc(100vw - 64px);
    max-height: 62vh;
  }
}
</style>
