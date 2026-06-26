<template>
  <div class="preparation-view geo-view">
    <div class="preparation-view__header">
      <h1 class="preparation-view__title">GEO</h1>
      <button class="preparation-view__sync-btn" :disabled="syncing" @click="handleSync">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'animate-spin': syncing }">
          <polyline points="23 4 23 10 17 10"></polyline>
          <polyline points="1 20 1 14 7 14"></polyline>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
        </svg>
        {{ syncing ? '同步中...' : '同步刷新' }}
      </button>
    </div>

    <div class="filter-tabs">
      <button class="filter-tabs__btn" :class="{ 'filter-tabs__btn--active': filterMode === 'preparation' }" @click="filterMode = 'preparation'">
        预成品
        <span class="filter-tabs__count">{{ preparationCount }}</span>
      </button>
      <button class="filter-tabs__btn filter-tabs__btn--publishable" :class="{ 'filter-tabs__btn--active': filterMode === 'publishable' }" @click="filterMode = 'publishable'">
        可发布
        <span class="filter-tabs__count">{{ publishableCount }}</span>
      </button>
      <button v-if="filterMode === 'publishable'" class="filter-tabs__btn filter-tabs__btn--new-group" type="button" @click="openNewPublishGroupDialog">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        新建时间分组
      </button>
    </div>

    <div v-if="loading" class="u-flex u-justify-center u-p-xl">
      <span class="animate-pulse">加载中...</span>
    </div>

    <div v-else-if="error" class="u-flex u-justify-center u-p-xl">
      <span class="geo-view__error">加载失败：{{ error }}</span>
    </div>

    <div v-else-if="filteredImages.length === 0" class="u-flex u-justify-center u-p-xl">
      <span class="geo-view__empty">暂无 GEO 图片</span>
    </div>

    <div v-else class="geo-view__body">
      <aside class="publishable-sidebar geo-sidebar">
        <div v-if="sidebarGroups.length === 0" class="publishable-sidebar__empty">暂无分组</div>
        <div
          v-for="group in sidebarGroups"
          :key="'sb-' + group.date"
          class="publishable-sidebar__item"
          :class="{
            'publishable-sidebar__item--active': selectedPublishGroup === group.date,
            'publishable-sidebar__item--drag-over': filterMode === 'publishable' && dragOverDate === group.date
          }"
          @click="selectPublishGroup(group.date)"
          @dragover.prevent="filterMode === 'publishable' && handleDragOver(group.date)"
          @dragleave="filterMode === 'publishable' && handleDragLeave(group.date)"
          @drop.prevent="filterMode === 'publishable' && handleDrop(group.date)"
        >
          <span class="publishable-sidebar__date">{{ group.date }}</span>
          <span class="publishable-sidebar__count">{{ group.items.length }} 张</span>
        </div>
      </aside>

      <section class="geo-view__main">
        <div class="geo-view__groups">
          <section
            v-for="group in groupedImages"
            :key="group.date"
            :id="`geo-group-${group.date}`"
            :ref="el => setGroupRef(group.date, el)"
            class="time-group-section"
            :class="{ 'time-group-section--drag-over': filterMode === 'publishable' && dragOverDate === group.date }"
            @dragover.prevent="filterMode === 'publishable' && handleDragOver(group.date)"
            @dragleave="filterMode === 'publishable' && handleDragLeave(group.date)"
            @drop.prevent="filterMode === 'publishable' && handleDrop(group.date)"
          >
            <div class="time-group-section__header">
              <span class="time-group-section__date">{{ group.date }}</span>
              <span class="time-group-section__stats">{{ group.items.length }} 张</span>
            </div>

        <div class="geo-view__grid">
          <article
            v-for="item in group.items"
            :key="item.id"
            class="geo-card"
            :class="{
              'geo-card--dragging': filterMode === 'publishable' && draggingItemId === item.id,
              'geo-card--draggable': filterMode === 'publishable' && !isDeleted(item)
            }"
            :draggable="filterMode === 'publishable' && !isDeleted(item) ? 'true' : 'false'"
            @dragstart="filterMode === 'publishable' && handleDragStart(item, $event)"
            @dragend="filterMode === 'publishable' && handleDragEnd"
          >
            <button class="geo-card__image-btn" type="button" @click="previewImage = item">
              <img class="geo-card__image" :src="item.url" :alt="item.display_name || item.filename" loading="lazy" />
              <span class="geo-card__image-overlay">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="11" cy="11" r="8"></circle>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                预览
              </span>
            </button>

            <div class="geo-card__content">
              <div class="geo-card__field">
                <span class="geo-card__label">编号</span>
                <input class="geo-card__input" :value="item.publish_code" :disabled="isDeleted(item)" placeholder="输入编号" @blur="updateField(item, 'publish_code', $event.target.value)" @keyup.enter="$event.target.blur()" />
              </div>

              <div class="geo-card__field">
                <span class="geo-card__label">API平台</span>
                <input class="geo-card__input" :value="item.platform" :disabled="isDeleted(item)" placeholder="API平台" @blur="updateField(item, 'platform', $event.target.value)" @keyup.enter="$event.target.blur()" />
              </div>

              <div class="geo-card__field">
                <span class="geo-card__label">发布平台</span>
                <input class="geo-card__input" :value="item.publish_platform" :disabled="isDeleted(item)" placeholder="发布平台" @blur="updateField(item, 'publish_platform', $event.target.value)" @keyup.enter="$event.target.blur()" />
              </div>

              <div class="geo-card__field">
                <span class="geo-card__label">创作人</span>
                <input class="geo-card__input" :value="item.creator" :disabled="isDeleted(item)" placeholder="创作人" @blur="updateField(item, 'creator', $event.target.value)" @keyup.enter="$event.target.blur()" />
              </div>

              <div class="geo-card__field geo-card__field--prompt">
                <span class="geo-card__label">生图提示词</span>
                <textarea class="geo-card__textarea" :value="item.copy_text" :disabled="isDeleted(item)" rows="5" placeholder="生图提示词" @blur="updateField(item, 'copy_text', $event.target.value)"></textarea>
              </div>

              <div v-if="filterMode === 'publishable'" class="geo-card__status-row">
                <span class="geo-card__label">审核状态</span>
                <span v-if="isDeleted(item)" class="geo-card__status geo-card__status--deleted">已删除</span>
                <span v-else-if="isReviewed(item)" class="geo-card__status geo-card__status--reviewed">已审核</span>
                <span v-else class="geo-card__status geo-card__status--pending">未审核</span>
              </div>

              <div class="geo-card__actions">
                <button v-if="filterMode === 'preparation'" class="geo-card__btn geo-card__btn--primary" type="button" @click="markPublishable(item)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                  标记可发布
                </button>
                <button v-else-if="!isReviewed(item) && !isDeleted(item)" class="geo-card__btn geo-card__btn--warning" type="button" @click="cancelPublishable(item)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="15" y1="9" x2="9" y2="15"></line>
                    <line x1="9" y1="9" x2="15" y2="15"></line>
                  </svg>
                  取消发布
                </button>
                <button v-if="filterMode === 'publishable' && !item.audit_status" class="geo-card__btn geo-card__btn--success" type="button" @click="confirmAudit(item)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 11l3 3L22 4"></path>
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
                  </svg>
                  审核
                </button>
                <button v-if="filterMode === 'publishable' && isReviewed(item)" class="geo-card__btn geo-card__btn--danger-outline" type="button" @click="confirmDeletedStatus(item)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"></path>
                  </svg>
                  已删除
                </button>
                <button v-if="filterMode === 'preparation'" class="geo-card__btn geo-card__btn--danger" type="button" @click="deleteItem(item)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"></path>
                    <line x1="10" y1="11" x2="10" y2="17"></line>
                    <line x1="14" y1="11" x2="14" y2="17"></line>
                  </svg>
                  删除
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
        </div>
      </section>
    </div>

    <div v-if="showNewPublishGroupDialog" class="publish-date-dialog-overlay" @click.self="closeNewPublishGroupDialog">
      <div class="publish-date-dialog">
        <h3 class="publish-date-dialog__title">新建时间分组</h3>
        <input class="publish-date-dialog__input" type="date" v-model="newPublishDate" @keyup.enter="handleCreatePublishGroup" />
        <div class="publish-date-dialog__actions">
          <button class="batch-dialog__btn batch-dialog__btn--cancel" type="button" @click="closeNewPublishGroupDialog">取消</button>
          <button class="batch-dialog__btn batch-dialog__btn--confirm" type="button" @click="handleCreatePublishGroup" :disabled="creatingPublishGroup">
            {{ creatingPublishGroup ? '创建中...' : '确定' }}
          </button>
        </div>
      </div>
    </div>

    <ImagePreview
      :show="!!previewImage"
      :image="previewImage"
      :alt="previewImage?.display_name"
      @close="previewImage = null"
    />

    <ConfirmDialog
      v-model:visible="confirmDialog.visible"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :confirm-text="confirmDialog.confirmText"
      :cancel-text="confirmDialog.cancelText"
      :danger="confirmDialog.danger"
      @confirm="handleConfirmDialogConfirm"
      @cancel="closeConfirmDialog"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  getGeoList,
  updateGeoItem,
  syncGeo,
  deleteGeoItem,
  getGeoPublishGroups,
  createGeoPublishGroup,
  moveGeoPublishGroup
} from '@/services/api'
import ImagePreview from '@/components/ImagePreview.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'
import { setCustomDragImage } from '@/utils/dragImage'

const images = ref([])
const loading = ref(true)
const syncing = ref(false)
const error = ref(null)
const previewImage = ref(null)
const publishGroups = ref([])
const showNewPublishGroupDialog = ref(false)
const newPublishDate = ref('')
const creatingPublishGroup = ref(false)
const selectedPublishGroup = ref('')
const groupRefs = ref({})
// 拖拽相关状态：仅在「可发布」Tab 中使用，draggingItemId 记录当前正在拖拽的 item.id，
// dragOverDate 记录当前鼠标悬停的目标时间分组；这两个值变化时会驱动对应的 CSS class 切换。
const draggingItemId = ref('')
const dragOverDate = ref('')
const confirmDialog = ref({
  visible: false,
  title: '确认',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  onConfirm: null
})

const savedFilterMode = localStorage.getItem('geo_filter_mode')
const filterMode = ref(savedFilterMode && ['preparation', 'publishable'].includes(savedFilterMode) ? savedFilterMode : 'preparation')

watch(filterMode, (value) => {
  localStorage.setItem('geo_filter_mode', value)
})

function normalizeFolderPath(folderPath) {
  return (folderPath || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
}

function isPublishFolderItem(item) {
  return /^可发布\/\d{4}-\d{2}-\d{2}$/.test(normalizeFolderPath(item.folder_path))
}

function isPublishedItem(item) {
  return item.is_publishable === 1 || !!item.publish_date || isPublishFolderItem(item)
}

function isReviewed(item) {
  return item.audit_status === 'reviewed'
}

function isDeleted(item) {
  return item.audit_status === 'deleted'
}

const preparationImages = computed(() => {
  return images.value.filter(item => !isPublishedItem(item))
})

const publishableImages = computed(() => {
  return images.value.filter(item => isPublishedItem(item))
})

const preparationCount = computed(() => preparationImages.value.length)
const publishableCount = computed(() => publishableImages.value.length)

const filteredImages = computed(() => {
  return filterMode.value === 'publishable' ? publishableImages.value : preparationImages.value
})

const groupedImages = computed(() => {
  const groups = {}
  const usePublishDate = filterMode.value === 'publishable'
  for (const item of filteredImages.value) {
    const date = usePublishDate
      ? (validateDateKey(item.publish_date) || '未知日期')
      : ((item.created_at || '').slice(0, 10) || '未知日期')
    if (!groups[date]) groups[date] = []
    groups[date].push(item)
  }
  return Object.entries(groups)
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, items]) => ({ date, items }))
})

// 按当前 Tab 决定侧边栏展示的分组
// 「预成品」按 created_at；「可发布」按 publish_date；
// 「可发布」额外合并后端返回的 publishGroups，确保空日期文件夹也会出现在侧边栏
const sidebarGroups = computed(() => {
  const map = new Map()
  for (const group of groupedImages.value) {
    map.set(group.date, { date: group.date, items: group.items })
  }
  if (filterMode.value === 'publishable') {
    for (const date of publishGroups.value) {
      if (!map.has(date)) {
        map.set(date, { date, items: [] })
      }
    }
  }
  return Array.from(map.values()).sort((a, b) => b.date.localeCompare(a.date))
})

function validateDateKey(value) {
  if (!value) return null
  const trimmed = String(value).trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return null
  return trimmed
}

function setGroupRef(date, el) {
  if (el) {
    groupRefs.value[date] = el
  } else {
    delete groupRefs.value[date]
  }
}

function scrollToGroup(date) {
  const el = groupRefs.value[date]
  if (el && typeof el.scrollIntoView === 'function') {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function selectPublishGroup(date) {
  selectedPublishGroup.value = date
  scrollToGroup(date)
}

watch(filterMode, () => {
  // 切换 Tab 时清空选中态，让用户重新选择
  selectedPublishGroup.value = ''
  groupRefs.value = {}
  // 切换 Tab 时清空拖拽状态，避免跨 Tab 出现幽灵拖拽
  draggingItemId.value = ''
  dragOverDate.value = ''
})

async function loadImages() {
  loading.value = true
  error.value = null
  try {
    const response = await getGeoList()
    images.value = response.images || []
  } catch (err) {
    error.value = err.message || '未知错误'
  } finally {
    loading.value = false
  }
}

async function loadPublishGroups() {
  try {
    const response = await getGeoPublishGroups()
    publishGroups.value = response.groups || []
  } catch (err) {
    // 侧边栏加载失败不阻塞主流程，仅记录到 error
    error.value = err.message || '加载发布日期分组失败'
  }
}

function openNewPublishGroupDialog() {
  newPublishDate.value = new Date().toISOString().slice(0, 10)
  showNewPublishGroupDialog.value = true
}

function closeNewPublishGroupDialog() {
  if (creatingPublishGroup.value) return
  showNewPublishGroupDialog.value = false
}

async function handleCreatePublishGroup() {
  if (creatingPublishGroup.value) return
  const date = validateDateKey(newPublishDate.value)
  if (!date) {
    openConfirmDialog({
      title: '日期无效',
      message: '请选择有效的发布日期（YYYY-MM-DD）',
      confirmText: '我知道了',
      cancelText: '',
      onConfirm: () => {}
    })
    return
  }
  creatingPublishGroup.value = true
  try {
    const res = await createGeoPublishGroup(date)
    const createdDate = validateDateKey(res?.publish_date) || date
    if (!publishGroups.value.includes(createdDate)) {
      publishGroups.value.push(createdDate)
      publishGroups.value.sort((a, b) => b.localeCompare(a))
    }
    showNewPublishGroupDialog.value = false
    // 重新拉取图片列表，确保侧边栏能正确反映最新状态
    await loadImages()
    await nextTick()
    selectPublishGroup(createdDate)
  } catch (err) {
    openConfirmDialog({
      title: '创建失败',
      message: '创建时间分组失败：' + (err.message || '未知错误'),
      confirmText: '我知道了',
      cancelText: '',
      danger: false,
      onConfirm: () => {}
    })
  } finally {
    creatingPublishGroup.value = false
  }
}

async function handleSync() {
  syncing.value = true
  error.value = null
  try {
    const response = await syncGeo()
    images.value = response.images || []
  } catch (err) {
    error.value = err.message || '同步失败'
  } finally {
    syncing.value = false
  }
}

function replaceItem(updatedItem) {
  const index = images.value.findIndex(item => item.id === updatedItem.id)
  if (index !== -1) images.value.splice(index, 1, updatedItem)
}

async function updateField(item, field, value) {
  if (isDeleted(item)) return
  if ((item[field] || '') === value) return
  try {
    const response = await updateGeoItem(item.id, { [field]: value })
    if (response.item) replaceItem(response.item)
  } catch (err) {
    error.value = err.message || '保存失败'
  }
}

async function markPublishable(item) {
  try {
    const response = await updateGeoItem(item.id, { is_publishable: 1 })
    if (response.item) replaceItem(response.item)
    filterMode.value = 'publishable'
  } catch (err) {
    error.value = err.message || '标记可发布失败'
  }
}

async function cancelPublishable(item) {
  if (isReviewed(item) || isDeleted(item)) return
  try {
    const response = await updateGeoItem(item.id, { is_publishable: 0 })
    if (response.item) replaceItem(response.item)
  } catch (err) {
    error.value = err.message || '取消发布失败'
  }
}

async function deleteItem(item) {
  openConfirmDialog({
    title: '确认删除',
    message: `确定要删除 ${item.filename} 吗？`,
    confirmText: '删除',
    danger: true,
    onConfirm: async () => {
      try {
        await deleteGeoItem(item.id)
        images.value = images.value.filter(current => current.id !== item.id)
      } catch (err) {
        error.value = err.message || '删除失败'
      }
    }
  })
}

function openConfirmDialog(options) {
  confirmDialog.value = {
    visible: true,
    title: options.title || '确认',
    message: options.message || '',
    confirmText: options.confirmText || '确定',
    cancelText: options.cancelText || '取消',
    danger: !!options.danger,
    onConfirm: options.onConfirm || null
  }
}

function closeConfirmDialog() {
  confirmDialog.value.visible = false
}

function handleConfirmDialogConfirm() {
  const action = confirmDialog.value.onConfirm
  closeConfirmDialog()
  if (action) action()
}

function confirmAudit(item) {
  openConfirmDialog({
    title: '确认审核',
    message: '确认审核后，该图片不可取消发布。是否继续？',
    confirmText: '确认审核',
    onConfirm: async () => {
      try {
        const response = await updateGeoItem(item.id, { audit_status: 'reviewed' })
        if (response.item) replaceItem(response.item)
      } catch (err) {
        error.value = err.message || '审核失败'
      }
    }
  })
}

function confirmDeletedStatus(item) {
  openConfirmDialog({
    title: '确认标记已删除',
    message: '该操作只会更新状态，不会删除图片；确认后已删除状态不可修改。是否继续？',
    confirmText: '标记已删除',
    danger: true,
    onConfirm: async () => {
      try {
        const response = await updateGeoItem(item.id, { audit_status: 'deleted' })
        if (response.item) replaceItem(response.item)
      } catch (err) {
        error.value = err.message || '标记已删除失败'
      }
    }
  })
}

// 拖拽开始：记录当前正在拖拽的 item，并写入 dataTransfer 让浏览器显示原生拖拽幽灵
function handleDragStart(item, event) {
  if (filterMode.value !== 'publishable' || isDeleted(item)) {
    event.preventDefault()
    return
  }
  draggingItemId.value = item.id
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', item.id)
    // 自定义拖拽预览为缩小后的图片缩略图，避免默认整卡片预览遮挡光标
    // 必须传入卡内已加载完成的 img 元素（DOM 中可见的图），不能传 URL 后异步加载，
    // 否则 setDragImage 在异步 onload 中调用，浏览器已用默认拖拽图
    const card = event.currentTarget
    const img = card && card.querySelector ? card.querySelector('.geo-card__image') : null
    if (img) {
      setCustomDragImage(event.dataTransfer, img)
    }
  }
}

// 拖拽结束：清空所有拖拽状态，避免出现「卡片保持半透明」等视觉残留
function handleDragEnd() {
  draggingItemId.value = ''
  dragOverDate.value = ''
}

// 拖拽悬停：高亮当前目标时间分组（侧边栏 / 主区域共用同一逻辑）
function handleDragOver(date) {
  if (filterMode.value !== 'publishable') return
  if (!draggingItemId.value) return
  dragOverDate.value = date
}

// 拖拽离开：仅当鼠标真正离开当前分组时才取消高亮，避免子元素冒泡导致闪烁
function handleDragLeave(date) {
  if (dragOverDate.value === date) {
    dragOverDate.value = ''
  }
}

// 放下：调用后端 moveGeoPublishGroup，把 publish 文件移动到目标日期分组
// （图片原件保留在「可发布/_originals/」备份目录，不随时间组移动）
async function handleDrop(date) {
  const itemId = draggingItemId.value
  draggingItemId.value = ''
  dragOverDate.value = ''
  if (!itemId) return
  if (filterMode.value !== 'publishable') return
  if (!validateDateKey(date)) return
  const item = images.value.find(i => i.id === itemId)
  if (!item) return
  const currentDate = validateDateKey(item.publish_date) || ''
  if (currentDate === date) return
  const previous = { ...item }
  // 乐观更新：先在前端把目标分组标记出来，失败时回滚
  item.publish_date = date
  try {
    const response = await moveGeoPublishGroup(itemId, date)
    if (response?.item) {
      replaceItem(response.item)
    }
    // 把新日期加入侧边栏，确保新建的空日期分组也能立即显示
    if (!publishGroups.value.includes(date)) {
      publishGroups.value.push(date)
      publishGroups.value.sort((a, b) => b.localeCompare(a))
    }
    // 同步最新 publishGroups 列表，避免侧边栏与实际数据不一致
    await loadPublishGroups()
    // 滚动到目标分组，提升用户体验
    await nextTick()
    selectPublishGroup(date)
  } catch (err) {
    Object.assign(item, previous)
    openConfirmDialog({
      title: '移动失败',
      message: '移动到时间分组失败：' + (err.message || '未知错误'),
      confirmText: '我知道了',
      cancelText: '',
      danger: true,
      onConfirm: () => {}
    })
  }
}

onMounted(async () => {
  // 页面挂载时同时加载图片列表和发布日期分组（侧边栏）
  await Promise.all([loadImages(), loadPublishGroups()])
})
</script>

<style lang="scss" scoped>
// GEO页面样式：包含时间分组卡片、状态徽标、动作按钮等美化样式
@import '@/styles/PreparationView.scss';

.geo-view {
  &__error {
    color: $color-danger;
  }

  &__empty {
    color: $color-text-tertiary;
  }

  // 左右分栏布局壳：左侧侧边栏 + 右侧主内容（仅在有数据时渲染）
  &__body {
    display: flex;
    align-items: flex-start;
    gap: $spacing-lg;
    min-height: 60vh;
  }

  // 主内容区域：占据剩余空间并允许独立滚动
  &__main {
    flex: 1;
    min-width: 0;
  }

  &__groups {
    display: flex;
    flex-direction: column;
    gap: $spacing-xl;
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
    gap: $spacing-md;
  }
}

// 侧边栏专属修饰：复用 PreparationView 的 .publishable-sidebar 样式
.geo-sidebar {
  position: sticky;
  top: 88px;
  max-height: calc(100vh - 120px);
}

.publishable-sidebar__empty {
  padding: $spacing-md;
  text-align: center;
  color: $color-text-tertiary;
  font-size: $font-size-sm;
}

// 「+ 新建时间分组」按钮：与 filter-tabs 风格一致，强调色
.filter-tabs__btn--new-group {
  margin-left: auto;
  background: linear-gradient(135deg, rgba($color-primary, 0.1) 0%, rgba($color-primary-light, 0.05) 100%);
  border-color: rgba($color-primary, 0.3);
  color: $color-primary;

  svg {
    width: 14px;
    height: 14px;
  }

  &:hover {
    background: linear-gradient(135deg, rgba($color-primary, 0.18) 0%, rgba($color-primary-light, 0.1) 100%);
    border-color: $color-primary;
    color: $color-primary;
  }
}

// 新建时间分组弹窗遮罩（与 PreparationView 的弹窗风格保持一致）
.publish-date-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.geo-card {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  align-items: start;
  gap: $spacing-md;
  padding: $spacing-md;
  background: $color-bg-card;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  box-shadow: $shadow-sm;
  transition: all $transition-normal;
  overflow: hidden;

  &:hover {
    border-color: $color-primary-light;
    box-shadow: $shadow-md;
    transform: translateY(-2px);
  }

  // 可发布 Tab 中：未删除的卡片支持拖拽，鼠标显示抓手
  &--draggable {
    cursor: grab;

    &:active {
      cursor: grabbing;
    }
  }

  // 正在被拖拽的卡片：半透明 + 轻微缩放，提示用户当前操作状态
  &--dragging {
    opacity: 0.55;
    transform: scale(0.98);
    box-shadow: $shadow-lg;
  }

  &__image-btn {
    position: relative;
    width: 100%;
    max-height: 420px;
    padding: 0;
    overflow: hidden;
    background: $color-bg-tertiary;
    border: 0;
    border-radius: $radius-md;
    cursor: pointer;
    transition: all $transition-fast;

    &:hover .geo-card__image-overlay {
      opacity: 1;
    }
  }

  &__image {
    width: 100%;
    height: auto;
    max-height: 420px;
    object-fit: contain;
    display: block;
    transition: transform $transition-normal;
  }

  &__image-btn:hover &__image {
    transform: scale(1.05);
  }

  &__image-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: $spacing-xs;
    background: linear-gradient(180deg, rgba(15, 23, 42, 0) 0%, rgba(15, 23, 42, 0.7) 100%);
    color: $color-text-inverse;
    font-size: $font-size-sm;
    font-weight: $font-weight-medium;
    opacity: 0;
    transition: opacity $transition-fast;

    svg {
      width: 18px;
      height: 18px;
    }
  }

  &__content {
    min-width: 0;
    max-width: 320px;
    display: flex;
    flex-direction: column;
    gap: $spacing-md;
  }

  &__field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  &__field--prompt {
    flex: 1;
  }

  &__label {
    color: $color-text-tertiary;
    font-size: 11px;
    font-weight: $font-weight-semibold;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  &__input,
  &__textarea {
    width: 100%;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    background: $color-bg;
    color: $color-text-primary;
    font: inherit;
    transition: all $transition-fast;

    &::placeholder {
      color: $color-text-tertiary;
    }

    &:hover:not(:disabled) {
      border-color: $color-border-focus;
    }

    &:focus {
      outline: none;
      border-color: $color-primary;
      box-shadow: 0 0 0 3px rgba($color-primary, 0.12);
    }

    &:disabled {
      opacity: 0.55;
      cursor: not-allowed;
      background: $color-bg-secondary;
    }
  }

  &__input {
    height: 32px;
    padding: 0 $spacing-sm;
    font-size: $font-size-sm;
  }

  &__textarea {
    min-height: 110px;
    padding: $spacing-sm $spacing-md;
    resize: vertical;
    line-height: $line-height-relaxed;
    font-size: $font-size-sm;
  }

  &__status-row {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    padding: $spacing-xs 0;
  }

  &__status {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px $spacing-sm;
    border-radius: $radius-full;
    background: $color-bg-secondary;
    color: $color-text-secondary;
    font-size: $font-size-xs;
    font-weight: $font-weight-semibold;

    &::before {
      content: '';
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
    }
  }

  &__status--reviewed {
    background: rgba($color-success, 0.1);
    color: $color-success;
  }

  &__status--deleted {
    background: rgba($color-danger, 0.1);
    color: $color-danger;
  }

  &__status--pending {
    background: rgba($color-warning, 0.1);
    color: $color-warning;
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: $spacing-xs;
    padding-top: $spacing-sm;
    border-top: 1px dashed $color-border;
  }

  &__btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 32px;
    padding: 0 $spacing-md;
    border-radius: $radius-md;
    font-size: $font-size-xs;
    font-weight: $font-weight-semibold;
    cursor: pointer;
    transition: all $transition-fast;
    white-space: nowrap;
    border: 1px solid transparent;

    svg {
      width: 14px;
      height: 14px;
      flex-shrink: 0;
    }

    &--primary {
      background: linear-gradient(135deg, $color-primary 0%, $color-primary-light 100%);
      color: $color-text-inverse;
      border-color: transparent;
      box-shadow: 0 2px 4px rgba($color-primary, 0.25);

      &:hover {
        box-shadow: 0 4px 10px rgba($color-primary, 0.4);
        transform: translateY(-1px);
      }
    }

    &--warning {
      background: rgba($color-warning, 0.12);
      color: $color-warning;
      border-color: rgba($color-warning, 0.3);

      &:hover {
        background: rgba($color-warning, 0.18);
        border-color: $color-warning;
      }
    }

    &--success {
      background: rgba($color-success, 0.12);
      color: $color-success;
      border-color: rgba($color-success, 0.3);

      &:hover {
        background: rgba($color-success, 0.18);
        border-color: $color-success;
      }
    }

    &--danger {
      background: rgba($color-danger, 0.1);
      color: $color-danger;
      border-color: rgba($color-danger, 0.25);

      &:hover {
        background: $color-danger;
        color: $color-text-inverse;
        border-color: $color-danger;
      }
    }

    &--danger-outline {
      background: transparent;
      color: $color-danger;
      border-color: rgba($color-danger, 0.3);

      &:hover {
        background: rgba($color-danger, 0.1);
        border-color: $color-danger;
      }
    }
  }
}

// 时间分组区域在拖拽悬停时显示高亮（覆盖 PreparationView 的默认样式）
.time-group-section--drag-over {
  border-radius: $radius-lg;
  background: rgba($color-warning, 0.06);
  outline: 2px dashed rgba($color-warning, 0.6);
  outline-offset: 4px;
  transition: background $transition-fast, outline-color $transition-fast;
}

@media (max-width: 760px) {
  .geo-view__grid {
    grid-template-columns: 1fr;
  }

  .geo-card {
    grid-template-columns: 1fr;
  }

  // 移动端：侧边栏转为顶部横排，主内容在下方
  .geo-view__body {
    flex-direction: column;
  }

  .geo-sidebar {
    position: static;
    width: 100% !important;
    max-height: none;
    display: flex;
    gap: $spacing-xs;
    overflow-x: auto;
    border-right: none;
    border-bottom: 1px solid $color-border;
    padding: $spacing-xs;

    // 侧边栏空态占满整行
    .publishable-sidebar__empty {
      width: 100%;
    }
  }

  .filter-tabs__btn--new-group {
    margin-left: $spacing-xs;
  }
}
</style>
