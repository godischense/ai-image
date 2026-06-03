<template>
  <Teleport to="body">
    <div v-if="visible" class="save-dialog" @click.self="emit('update:visible', false)">
      <div class="save-dialog__container">
        <div class="save-dialog__header">
          <h3 class="save-dialog__title">保存到素材库</h3>
          <button class="save-dialog__close" @click="emit('update:visible', false)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div class="save-dialog__body">
          <img v-if="previewImage" :src="previewImage.url || previewImage.thumbnail" class="save-dialog__preview" />
          <p v-if="previewImage" class="save-dialog__prompt">{{ previewImage.prompt || '无描述' }}</p>
          <p v-else-if="isBatch" class="save-dialog__prompt">已选择 {{ imageCount }} 张图片</p>
          <p class="save-dialog__hint">将自动下载原图到 edit_folders，再保存副本到素材库</p>
          <div v-if="saveError" class="save-dialog__error">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>{{ saveError }}</span>
          </div>
        </div>
        <div class="save-dialog__footer">
          <button class="save-dialog__btn save-dialog__btn--cancel" @click="emit('update:visible', false)" :disabled="saving">取消</button>
          <button class="save-dialog__btn save-dialog__btn--primary" @click="handleSave" :disabled="saving">
            <span v-if="saving" class="save-dialog__spinner"></span>
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { saveEditToLibrary } from '@/services/api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  image: { type: [Object, Array], default: null }
})

const emit = defineEmits(['update:visible', 'saved'])

const saving = ref(false)
const saveError = ref('')

const isBatch = computed(() => Array.isArray(props.image))
const imageCount = computed(() => isBatch.value ? props.image.length : 0)
const previewImage = computed(() => {
  if (!props.image) return null
  if (isBatch.value) return props.image[0] || null
  return props.image
})

const saveSingleImage = async (img) => {
  if (!img?.url) return true
  const result = await saveEditToLibrary({
    image_url: img.url,
    prompt: img.prompt || ''
  })
  return result?.success
}

const handleSave = async () => {
  if (!props.image) return

  saving.value = true
  saveError.value = ''

  try {
    if (isBatch.value) {
      let successCount = 0
      let failCount = 0
      for (const img of props.image) {
        try {
          const ok = await saveSingleImage(img)
          if (ok) successCount++
          else failCount++
        } catch {
          failCount++
        }
      }
      if (failCount === 0) {
        emit('saved')
        emit('update:visible', false)
      } else {
        saveError.value = `成功 ${successCount} 张，失败 ${failCount} 张`
      }
    } else {
      const imageUrl = props.image.url || ''
      if (!imageUrl) {
        throw new Error('无法获取图片信息')
      }

      const result = await saveEditToLibrary({
        image_url: imageUrl,
        prompt: props.image.prompt || ''
      })

      if (result?.success) {
        emit('saved')
        emit('update:visible', false)
      } else {
        saveError.value = result?.error || '保存失败，请重试'
      }
    }
  } catch (err) {
    saveError.value = err.message || '网络错误，请检查后端服务是否正常运行'
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss">
@use '@/styles/variables' as *;

.save-dialog {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;

  &__container {
    background: $color-bg-card;
    border-radius: $radius-xl;
    width: 400px;
    max-width: 90vw;
    box-shadow: $shadow-xl;
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $spacing-md $spacing-lg;
    border-bottom: 1px solid $color-border-light;
  }

  &__title {
    margin: 0;
    font-size: $font-size-base;
    font-weight: 600;
    color: $color-text-primary;
  }

  &__close {
    background: none;
    border: none;
    cursor: pointer;
    color: $color-text-tertiary;

    svg {
      width: 18px;
      height: 18px;
    }

    &:hover {
      color: $color-text-primary;
    }
  }

  &__body {
    padding: $spacing-lg;
    text-align: center;
  }

  &__preview {
    max-width: 200px;
    max-height: 200px;
    object-fit: contain;
    border-radius: $radius-md;
    margin-bottom: $spacing-md;
  }

  &__prompt {
    font-size: 12px;
    color: $color-text-secondary;
    margin: 0;
  }

  &__hint {
    font-size: 11px;
    color: $color-text-tertiary;
    margin: $spacing-sm 0 0;
    padding: $spacing-xs $spacing-sm;
    background: rgba($color-primary, 0.06);
    border-radius: $radius-sm;
  }

  &__error {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    margin-top: $spacing-md;
    padding: $spacing-sm $spacing-md;
    background: rgba($color-danger, 0.1);
    border: 1px solid rgba($color-danger, 0.25);
    border-radius: $radius-md;
    color: $color-danger;
    font-size: 12px;
    text-align: left;

    svg {
      width: 14px;
      height: 14px;
      flex-shrink: 0;
    }
  }

  &__footer {
    display: flex;
    justify-content: flex-end;
    gap: $spacing-sm;
    padding: $spacing-md $spacing-lg;
    border-top: 1px solid $color-border-light;
  }

  &__btn {
    padding: $spacing-sm $spacing-lg;
    border-radius: $radius-md;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all $transition-fast;

    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    &--cancel {
      background: $color-bg-secondary;
      color: $color-text-secondary;
      border: 1px solid $color-border;

      &:hover:not(:disabled) {
        background: $color-bg-tertiary;
      }
    }

    &--primary {
      background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
      color: $color-text-inverse;

      &:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba($color-primary, 0.3);
      }
    }
  }

  &__spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: save-dialog-spin 0.6s linear infinite;
    margin-right: 4px;
    vertical-align: middle;
  }
}

@keyframes save-dialog-spin {
  to { transform: rotate(360deg); }
}
</style>
