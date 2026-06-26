<template>
  <div class="edit-board" :class="{ 'edit-board--selection-mode': selectionMode }">
    <div class="edit-board__toolbar">
      <button
        class="edit-board__toolbar-btn"
        :class="{ 'edit-board__toolbar-btn--active': selectionMode }"
        @click="toggleSelectionMode"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="7" height="7"></rect>
          <rect x="14" y="3" width="7" height="7"></rect>
          <rect x="14" y="14" width="7" height="7"></rect>
          <rect x="3" y="14" width="7" height="7"></rect>
        </svg>
        <span>{{ selectionMode ? '取消多选' : '多选' }}</span>
      </button>
      <button v-if="selectionMode" class="edit-board__toolbar-btn" @click="handleSelectAll">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <polyline points="9 12 12 15 21 6"></polyline>
        </svg>
        <span>全选</span>
      </button>
      <!-- 制作人筛选：仅作为展示与编辑入口，状态由父组件管理，本组件通过 props/emit 通信 -->
      <div class="edit-board__toolbar-creator">
        <span class="edit-board__toolbar-creator-label">制作人</span>
        <Select
          :model-value="creator"
          :options="creatorOptions"
          :placeholder="creatorOptions.length > 0 ? '选择制作人' : '请先在设置中配置制作人'"
          :disabled="creatorOptions.length === 0"
          wrapper-class="edit-board__toolbar-creator-select"
          @update:model-value="(val) => emit('update:creator', val)"
        />
      </div>
    </div>

    <div v-if="selectionMode && selectedImages.length > 0" class="edit-board__batch-bar">
      <span class="edit-board__batch-count">已选择 {{ selectedImages.length }} 张图片</span>
      <div class="edit-board__batch-actions">
        <button class="edit-board__batch-btn" @click="handleBatchSave">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
            <polyline points="17 21 17 13 7 13 7 21"></polyline>
            <polyline points="7 3 7 8 15 8"></polyline>
          </svg>
          批量保存
        </button>
        <button class="edit-board__batch-btn edit-board__batch-btn--danger" @click="handleBatchDelete">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          批量删除
        </button>
      </div>
    </div>

    <div v-if="!images || images.length === 0" class="edit-board__empty">
    </div>
    <div v-else class="edit-board__grid">
      <div
        v-for="image in images"
        :key="image.id"
        class="edit-board__card"
        :class="{
          'edit-board__card--selected': selectedId === image.id,
          'edit-board__card--checked': selectionMode && isSelected(image),
          'edit-board__card--generating': image.generating,
          'edit-board__card--error': image.error
        }"
        :style="getCardStyle(image)"
        @click="handleCardClick(image)"
      >
        <div class="edit-board__image-wrapper" :style="getImageWrapperStyle(image)">
          <img
            v-if="image.url || image.thumbnail"
            :src="image.thumbnail || image.url"
            :alt="image.prompt || '编辑图片'"
            class="edit-board__image"
          />
          <div v-else class="edit-board__placeholder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <circle cx="8.5" cy="8.5" r="1.5"></circle>
              <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
          </div>
          <div v-if="image.generating" class="edit-board__generating-overlay">
            <div class="edit-board__spinner"></div>
            <span class="edit-board__generating-text">生成中...</span>
          </div>
          <div v-if="image.error" class="edit-board__error-overlay">
            <svg class="edit-board__error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span class="edit-board__error-text">{{ image.error }}</span>
            <button
              v-if="image.taskId && image.apiSource === 'apiyi'"
              class="edit-board__retry-btn"
              @click.stop="emit('retry', image)"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 4 23 10 17 10"></polyline>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
              </svg>
              <span>重试</span>
            </button>
          </div>
          <div v-if="!selectionMode && !image.generating && !image.error" class="edit-board__overlay">
            <div class="edit-board__actions">
              <button class="edit-board__action-btn" title="编辑" @click.stop="handleEdit(image)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                <span>编辑</span>
              </button>
              <button class="edit-board__action-btn" title="删除" @click.stop="handleDelete(image)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                <span>删除</span>
              </button>
              <button class="edit-board__action-btn" title="保存" @click.stop="handleSave(image)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                  <polyline points="17 21 17 13 7 13 7 21"></polyline>
                  <polyline points="7 3 7 8 15 8"></polyline>
                </svg>
                <span>保存</span>
              </button>
              <button class="edit-board__action-btn" title="下载到本地" @click.stop="handleDownload(image)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                <span>下载</span>
              </button>
              <button class="edit-board__action-btn" title="添加到预备" @click.stop="emit('add-to-preparation', image)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <span>预备</span>
              </button>
              <button class="edit-board__action-btn" title="添加到GEO" @click.stop="emit('add-to-geo', image)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="2" y1="12" x2="22" y2="12"/>
                  <path d="M12 2a15.3 15.3 0 0 1 0 20"/>
                  <path d="M12 2a15.3 15.3 0 0 0 0 20"/>
                </svg>
                <span>GEO</span>
              </button>
            </div>
          </div>
          <div v-if="selectionMode && isSelected(image)" class="edit-board__selected-mark">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
        </div>
        <div class="edit-board__info">
          <div class="edit-board__meta">
            <span class="edit-board__meta-item">{{ formatApiSourceLabel(image.apiSource) }}</span>
            <span class="edit-board__meta-item">{{ image.size || '1024x1024' }}</span>
            <span class="edit-board__meta-item">{{ formatImageFormatLabel(image) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { formatApiSourceLabel, formatImageFormatLabel } from '@/utils/platformDisplay'
import Select from '@/components/common/Select/Select.vue'

const props = defineProps({
  images: {
    type: Array,
    default: () => []
  },
  selectedId: {
    type: String,
    default: null
  },
  // 当前制作人筛选值（v-model），由父组件管理
  creator: {
    type: String,
    default: ''
  },
  // 制作人下拉选项（来自父组件 configStore.creatorOptions.options 派生）
  creatorOptions: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['select', 'edit', 'delete', 'save', 'download', 'batchDelete', 'batchSave', 'add-to-preparation', 'add-to-geo', 'retry', 'update:creator'])

const selectionMode = ref(false)
const selectedImages = ref([])

// 根据图片宽高比获取比例值
const getAspectRatioValue = (image) => {
  if (image.aspect_ratio && typeof image.aspect_ratio === 'number' && image.aspect_ratio > 0) {
    return image.aspect_ratio
  }

  if (image.size && typeof image.size === 'string' && image.size.includes('x')) {
    const parts = image.size.split('x')
    if (parts.length === 2) {
      const width = parseFloat(parts[0])
      const height = parseFloat(parts[1])
      if (width > 0 && height > 0) {
        return width / height
      }
    }
  }

  return 1
}

// 根据宽高比动态设置 grid-column span
const getCardStyle = (image) => {
  const ratio = getAspectRatioValue(image)
  if (ratio >= 2.5) {
    return { gridColumn: 'span 3' }
  }
  if (ratio >= 1.3) {
    return { gridColumn: 'span 2' }
  }
  return {}
}

// 根据宽高比设置图片容器比例
const getImageWrapperStyle = (image) => {
  const ratio = getAspectRatioValue(image)
  return { aspectRatio: String(ratio) }
}

// 判断图片是否被批量选中
const isSelected = (image) => {
  return selectedImages.value.some(img => img.id === image.id)
}

// 切换批量选择模式
const toggleSelectionMode = () => {
  selectionMode.value = !selectionMode.value
  if (!selectionMode.value) {
    selectedImages.value = []
  }
}

// 全选所有非 generating 的图片
const handleSelectAll = () => {
  selectedImages.value = props.images.filter(img => !img.generating)
}

// 卡片点击：批量模式下切换选中，普通模式下打开对比预览
const handleCardClick = (image) => {
  if (selectionMode.value) {
    const index = selectedImages.value.findIndex(img => img.id === image.id)
    if (index === -1) {
      selectedImages.value.push(image)
    } else {
      selectedImages.value.splice(index, 1)
    }
  } else {
    handleSelect(image)
  }
}

// 点击卡片主体 → 打开对比预览
const handleSelect = (image) => {
  if (!image.generating) {
    emit('select', image)
  }
}

// 批量删除
const handleBatchDelete = () => {
  if (selectedImages.value.length === 0) return
  emit('batchDelete', [...selectedImages.value])
  selectedImages.value = []
  selectionMode.value = false
}

// 批量保存
const handleBatchSave = () => {
  if (selectedImages.value.length === 0) return
  emit('batchSave', [...selectedImages.value])
  selectedImages.value = []
  selectionMode.value = false
}

// 点击编辑按钮 → 设为当前编辑图
const handleEdit = (image) => {
  emit('edit', image)
}

// 点击删除按钮 → 确认删除
const handleDelete = (image) => {
  emit('delete', image)
}

// 点击保存按钮 → 打开保存弹窗
const handleSave = (image) => {
  emit('save', image)
}

// 点击下载按钮 → 下载到本地
const handleDownload = (image) => {
  emit('download', image)
}
</script>

<style lang="scss">
@use '@/styles/variables' as *;
@use '@/styles/mixins' as *;

.edit-board {
  width: 100%;
  height: 100%;

  &--selection-mode {
    .edit-board__card {
      cursor: pointer;
    }
  }

  &__toolbar {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    margin-bottom: $spacing-md;
  }

  &__toolbar-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    background: $color-bg-card;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    color: $color-text-secondary;
    font-size: 11px;
    cursor: pointer;
    transition: all $transition-fast;

    svg {
      width: 14px;
      height: 14px;
    }

    &:hover {
      border-color: $color-primary;
      color: $color-primary;
    }

    &--active {
      background: rgba($color-primary, 0.1);
      border-color: $color-primary;
      color: $color-primary;
    }
  }

  // 工具栏上的制作人筛选容器
  &__toolbar-creator {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: $spacing-xs;
    min-width: 200px;
  }

  &__toolbar-creator-label {
    font-size: 11px;
    font-weight: 500;
    color: $color-text-secondary;
    white-space: nowrap;
  }

  &__toolbar-creator-select {
    flex: 1;
    min-width: 140px;
  }

  &__batch-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $spacing-sm $spacing-md;
    margin-bottom: $spacing-md;
    background: rgba($color-primary, 0.08);
    border: 1px solid rgba($color-primary, 0.2);
    border-radius: $radius-md;
  }

  &__batch-count {
    font-size: 12px;
    font-weight: 500;
    color: $color-primary;
  }

  &__batch-actions {
    display: flex;
    gap: $spacing-sm;
  }

  &__batch-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 5px 10px;
    background: $color-bg-card;
    border: 1px solid $color-border;
    border-radius: $radius-sm;
    font-size: 11px;
    color: $color-text-secondary;
    cursor: pointer;
    transition: all $transition-fast;

    svg {
      width: 12px;
      height: 12px;
    }

    &:hover {
      border-color: $color-primary;
      color: $color-primary;
    }

    &--danger {
      &:hover {
        border-color: $color-danger;
        color: $color-danger;
      }
    }
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: $spacing-md;
  }

  &__card {
    background: $color-bg-card;
    border-radius: $radius-xl;
    overflow: hidden;
    cursor: pointer;
    transition: all $transition-fast;
    border: 2px solid transparent;
    box-shadow: $shadow-sm;

    &:hover {
      transform: translateY(-2px);
      box-shadow: $shadow-lg;
    }

    &--selected {
      border-color: $color-primary;
      box-shadow: 0 0 0 3px rgba($color-primary, 0.15);
    }

    &--checked {
      border-color: $color-primary;
      box-shadow: 0 0 0 3px rgba($color-primary, 0.2);
    }

    &--generating {
      cursor: wait;
    }

    &--error .edit-board__image-wrapper {
      opacity: 0.7;
    }
  }

  &__image-wrapper {
    position: relative;
    width: 100%;
    background: linear-gradient(135deg, $color-bg-secondary 0%, $color-bg-tertiary 100%);
  }

  &__image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  &__placeholder {
    @include flex-center;
    width: 100%;
    height: 100%;

    svg {
      width: 40px;
      height: 40px;
      color: $color-text-tertiary;
      opacity: 0.5;
    }
  }

  &__generating-overlay {
    @include absolute-fill;
    @include flex-column-center;
    gap: $spacing-sm;
    background: linear-gradient(135deg, rgba($color-primary, 0.9) 0%, rgba($color-primary, 0.8) 100%);
    color: $color-text-inverse;
  }

  &__spinner {
    width: 32px;
    height: 32px;
    border: 3px solid rgba(255, 255, 255, 0.25);
    border-top-color: $color-text-inverse;
    border-radius: $radius-full;
    animation: edit-board-spin 1s linear infinite;
  }

  &__generating-text {
    font-size: 11px;
    font-weight: 500;
  }

  &__error-overlay {
    @include absolute-fill;
    @include flex-column-center;
    gap: 6px;
    background: linear-gradient(135deg, rgba($color-danger, 0.95) 0%, rgba($color-danger, 0.9) 100%);
    color: $color-text-inverse;
  }

  &__error-icon {
    width: 28px;
    height: 28px;
  }

  &__error-text {
    font-size: 10px;
    text-align: center;
    padding: 0 8px;
    max-height: 40px;
    overflow: hidden;
  }

  &__retry-btn {
    @include flex-center;
    gap: 4px;
    margin-top: 4px;
    padding: 4px 10px;
    background: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.4);
    border-radius: $radius-md;
    color: $color-text-inverse;
    font-size: 11px;
    cursor: pointer;
    transition: all $transition-fast;

    svg {
      width: 12px;
      height: 12px;
    }

    &:hover {
      background: rgba(255, 255, 255, 0.32);
      border-color: rgba(255, 255, 255, 0.6);
      transform: scale(1.04);
    }
  }

  &__overlay {
    @include absolute-fill;
    background: rgba(0, 0, 0, 0.5);
    opacity: 0;
    transition: opacity $transition-fast;
    @include flex-center;

    &:hover {
      opacity: 1;
    }
  }

  &__actions {
    display: flex;
    gap: $spacing-xs;
    flex-wrap: wrap;
    justify-content: center;
    padding: $spacing-sm;
  }

  &__action-btn {
    @include flex-center;
    gap: 4px;
    padding: 6px 10px;
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: $radius-md;
    color: $color-text-inverse;
    font-size: 10px;
    cursor: pointer;
    transition: all $transition-fast;
    white-space: nowrap;

    svg {
      width: 12px;
      height: 12px;
    }

    &:hover {
      background: rgba(255, 255, 255, 0.25);
      border-color: rgba(255, 255, 255, 0.4);
      transform: scale(1.05);
    }
  }

  &__selected-mark {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 24px;
    height: 24px;
    background: $color-primary;
    border-radius: $radius-full;
    @include flex-center;

    svg {
      width: 14px;
      height: 14px;
      color: $color-text-inverse;
    }
  }

  &__info {
    padding: $spacing-xs $spacing-sm;
    display: flex;
    align-items: center;
  }

  &__meta {
    display: flex;
    align-items: center;
    gap: $spacing-xs;
    width: 100%;
    overflow: hidden;
  }

  &__meta-item {
    font-size: 9px;
    color: $color-text-tertiary;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;

    &:not(:last-child)::after {
      content: '·';
      margin-left: $spacing-xs;
    }
  }
}

@keyframes edit-board-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
