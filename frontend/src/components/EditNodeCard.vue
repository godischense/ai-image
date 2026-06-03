
<template>
  <div
    class="edit-node-card"
    :class="{
      'edit-node-card--active': active,
      'edit-node-card--generating': node.generating,
      'edit-node-card--error': node.error
    }"
    @click="handleClick"
  >
    <div class="edit-node-card__wrapper" :style="{ aspectRatio: aspectRatio }">
      <div v-if="node.generating" class="edit-node-card__loading">
        <div class="edit-node-card__spinner"></div>
        <span class="edit-node-card__loading-text">正在生成中...</span>
        <span v-if="node.taskId" class="edit-node-card__task-id">{{ node.taskId.slice(0, 8) }}...</span>
      </div>
      <div v-else-if="node.error" class="edit-node-card__error">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span>{{ node.error }}</span>
      </div>
      <img
        v-else-if="previewSrc"
        :src="previewSrc"
        :alt="node.prompt"
        class="edit-node-card__image"
        loading="lazy"
      />
      <div v-else class="edit-node-card__placeholder">
        <span class="edit-node-card__placeholder-text">缩略图生成中</span>
      </div>
      <template v-if="!node.generating && !node.error">
        <div class="edit-node-card__overlay">
          <div class="edit-node-card__actions">
            <div class="edit-node-card__actions-row">
              <button
                class="edit-node-card__action-btn edit-node-card__action-btn--view"
                @click.stop="handleView"
                title="查看原图"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                  <circle cx="12" cy="12" r="3"></circle>
                </svg>
              </button>
              <button
                class="edit-node-card__action-btn edit-node-card__action-btn--download"
                @click.stop="handleDownload"
                title="下载图片"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
              </button>
            </div>
            <div class="edit-node-card__actions-row">
              <button
                class="edit-node-card__action-btn edit-node-card__action-btn--mask"
                @click.stop="handleMask"
                title="编辑遮罩"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 10H4"></path>
                  <path d="M14 14H4"></path>
                  <path d="M14 18H4"></path>
                  <path d="M20 4L14 10"></path>
                  <path d="M20 8L14 14"></path>
                  <path d="M20 12L14 18"></path>
                </svg>
              </button>
              <button
                class="edit-node-card__action-btn edit-node-card__action-btn--edit"
                @click.stop="handleContinueEdit"
                title="继续编辑"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
              </button>
              <button
                v-if="canDelete"
                class="edit-node-card__action-btn edit-node-card__action-btn--danger"
                @click.stop="handleDelete"
                title="删除图片"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  <line x1="10" y1="11" x2="10" y2="17"></line>
                  <line x1="14" y1="11" x2="14" y2="17"></line>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>
    <div class="edit-node-card__info">
      <div v-if="isEditingName" class="edit-node-card__name-edit">
        <input
          ref="nameInputRef"
          v-model="editingName"
          class="edit-node-card__name-input"
          type="text"
          :maxlength="MAX_NAME_LENGTH"
          @blur="handleNameBlur"
          @keyup.enter="handleNameSubmit"
          @keyup.esc="handleNameCancel"
        />
      </div>
      <div v-else class="edit-node-card__name-display">
        <span class="edit-node-card__name-text" :title="rawDisplayName">
          {{ displayName }}
        </span>
        <button
          v-if="canRename"
          class="edit-node-card__rename-btn"
          @click.stop="startEditingName"
          title="重命名"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
          </svg>
        </button>
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
import { ref, computed, nextTick } from 'vue'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'

const MAX_NAME_LENGTH = 12
const MAX_DISPLAY_NAME_LENGTH = 6

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  active: {
    type: Boolean,
    default: false
  },
  aspectRatio: {
    type: String,
    default: '1:1'
  }
})

const emit = defineEmits(['view', 'download', 'mask', 'edit', 'click', 'rename', 'delete'])

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

const downloadImageFromUrl = async (url, filename) => {
  try {
    const response = await fetch(url)
    const blob = await response.blob()
    const urlObject = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = urlObject
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(urlObject)
  } catch (error) {
    console.error('Download failed:', error)
  }
}

const isEditingName = ref(false)
const editingName = ref('')
const nameInputRef = ref(null)

const canDelete = computed(() => {
  return props.node.parentId !== null && props.node.parentId !== undefined
})

const rawDisplayName = computed(() => {
  return props.node.title || props.node.prompt || '未命名'
})

const displayName = computed(() => {
  if (rawDisplayName.value.length <= MAX_DISPLAY_NAME_LENGTH) {
    return rawDisplayName.value
  }

  return `${rawDisplayName.value.slice(0, MAX_DISPLAY_NAME_LENGTH)}...`
})

const displayUrl = computed(() => {
  return props.node.displayUrl || props.node.imageUrl || ''
})

const previewSrc = computed(() => {
  return props.node.thumbnail || displayUrl.value
})

const canRename = computed(() => {
  return props.node.parentId !== null && props.node.parentId !== undefined
})

const handleClick = () => {
  if (!props.node.generating && !props.node.error) {
    emit('click', props.node)
  }
}

const handleView = () => {
  if (!props.node.generating && !props.node.error) {
    emit('view', props.node)
  }
}

const handleDownload = async () => {
  if (!props.node.generating && displayUrl.value) {
    try {
      const filename = `edited-image-${Date.now()}.png`
      await downloadImageFromUrl(displayUrl.value, filename)
    } catch (error) {
      console.error('Download failed:', error)
    }
  }
}

const handleMask = () => {
  if (!props.node.generating && !props.node.error) {
    emit('mask', props.node)
  }
}

const handleContinueEdit = () => {
  if (!props.node.generating && !props.node.error) {
    emit('edit', props.node)
  }
}

const handleDelete = () => {
  if (!canDelete.value || props.node.generating) return

  openConfirmDialog({
    title: '确认删除',
    message: '确定要删除这张图片吗？',
    confirmText: '删除',
    cancelText: '取消',
    danger: true,
    onConfirm: () => {
      emit('delete', props.node)
    }
  })
}

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

const startEditingName = () => {
  if (!canRename.value) return
  editingName.value = rawDisplayName.value.slice(0, MAX_NAME_LENGTH)
  isEditingName.value = true
  nextTick(() => {
    nameInputRef.value?.focus()
    nameInputRef.value?.select()
  })
}

const handleNameBlur = () => {
  handleNameSubmit()
}

const handleNameSubmit = () => {
  if (!isEditingName.value) return

  const newName = editingName.value.trim().slice(0, MAX_NAME_LENGTH)
  if (newName && newName !== rawDisplayName.value) {
    emit('rename', props.node, newName)
  }
  isEditingName.value = false
}

const handleNameCancel = () => {
  isEditingName.value = false
  editingName.value = ''
}
</script>

<style lang="scss" scoped>
@import '@/styles/variables';
@import '@/styles/mixins';

.edit-node-card {
  background: $color-bg;
  border: 2px solid $color-border;
  border-radius: $radius-lg;
  overflow: hidden;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    border-color: $color-primary;
    transform: translateY(-2px);
    box-shadow: $shadow-md;
  }

  &--active {
    border-color: $color-primary;
    box-shadow: 0 0 0 2px rgba($color-primary, 0.2);
  }

  &--generating {
    opacity: 0.8;
  }

  &--error {
    border-color: $color-danger;
  }

  &__wrapper {
    position: relative;
    width: 100%;
    max-width: 100px;
    background: $color-bg-secondary;
    overflow: hidden;
    height: auto;
    min-height: 60px;
  }

  &__image {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  &__placeholder {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: $spacing-sm;
    background: $color-bg-secondary;
    color: $color-text-secondary;
    text-align: center;
  }

  &__placeholder-text {
    font-size: $font-size-xs;
    line-height: 1.4;
  }

  &__loading {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: $spacing-xs;
    background: $color-bg-secondary;
  }

  &__spinner {
    width: 32px;
    height: 32px;
    border: 3px solid $color-border;
    border-top-color: $color-primary;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  &__loading-text {
    font-size: $font-size-xs;
    color: $color-text-secondary;
  }

  &__task-id {
    font-size: $font-size-xs;
    color: $color-text-tertiary;
    font-family: monospace;
  }

  &__error {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: $spacing-xs;
    background: rgba($color-danger, 0.1);
    color: $color-danger;

    svg {
      width: 32px;
      height: 32px;
    }

    span {
      font-size: $font-size-xs;
      text-align: center;
      padding: 0 $spacing-sm;
    }
  }

  &__overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0);
    transition: background $transition-fast;

    &:hover {
      background: rgba(0, 0, 0, 0.6);
    }
  }

  &__actions {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    gap: $spacing-xs;
    padding: $spacing-sm;
    background: rgba(0, 0, 0, 0.7);
    border-radius: $radius-md;
    opacity: 0;
    transition: all $transition-fast;

    .edit-node-card__overlay:hover & {
      opacity: 1;
    }
  }

  &__actions-row {
    display: flex;
    gap: $spacing-xs;
  }

  &__action-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: $spacing-sm;
    background: rgba($color-bg, 0.9);
    border: none;
    border-radius: $radius-sm;
    cursor: pointer;
    transition: all $transition-fast;
    color: $color-text-primary;

    &:hover {
      background: $color-primary;
      color: $color-text-inverse;
    }

    svg {
      width: 16px;
      height: 16px;
    }

    span {
      display: none;
    }

    &--mask {
      background: rgba($color-primary, 0.2);
      color: $color-primary;

      &:hover {
        background: $color-primary;
        color: $color-text-inverse;
      }
    }

    &--danger {
      background: rgba($color-danger, 0.2);
      color: $color-danger;

      &:hover {
        background: $color-danger;
        color: $color-text-inverse;
      }
    }
  }

  &__info {
    padding: $spacing-xs $spacing-sm;
    background: $color-bg;
    border-top: 1px solid $color-border;
    min-height: 42px;
  }

  &__name-display {
    display: flex;
    align-items: flex-start;
    gap: $spacing-xs;
    min-height: 32px;
  }

  &__name-text {
    flex: 1;
    font-size: $font-size-xs;
    color: $color-text-primary;
    display: -webkit-box;
    overflow: hidden;
    line-height: 1.4;
    word-break: break-word;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  &__rename-btn {
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px;
    background: transparent;
    border: none;
    border-radius: $radius-sm;
    cursor: pointer;
    color: $color-text-tertiary;
    opacity: 0;
    flex-shrink: 0;
    transition: all $transition-fast;

    .edit-node-card:hover & {
      opacity: 1;
    }

    &:hover {
      background: rgba($color-primary, 0.1);
      color: $color-primary;
    }

    svg {
      width: 12px;
      height: 12px;
    }
  }

  &__name-edit {
    display: flex;
    align-items: center;
  }

  &__name-input {
    width: 100%;
    padding: 2px 4px;
    font-size: $font-size-xs;
    color: $color-text-primary;
    background: $color-bg-secondary;
    border: 1px solid $color-primary;
    border-radius: $radius-sm;
    outline: none;

    &:focus {
      box-shadow: 0 0 0 2px rgba($color-primary, 0.2);
    }
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
