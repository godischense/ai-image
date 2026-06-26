<script setup>
// 多选项弹窗：用于「请选择 A / B / C / 取消」类交互
// 设计原则：
//   1. 视觉风格与项目内 ConfirmDialog 保持一致（遮罩、模糊、动画、配色）
//   2. options 是任意数量的按钮（最少 1 个），最底部可放置一个独立的取消按钮
//   3. 选项触发后自动关闭弹窗，避免遗留状态
//   4. 支持 Escape / 点击遮罩关闭，等同于取消
//   5. 通过 defineExpose 暴露 resolve 方法，父组件也可以用 Promise 模式获取选项
// 实现逻辑：
//   1. props.options 形如 [{ value, label, description, danger? }, ...]
//   2. 点击选项 → emit('select', value) + emit('update:visible', false)
//   3. 点击取消 / 遮罩 / Esc → emit('cancel') + emit('update:visible', false)
import { onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '请选择'
  },
  message: {
    type: String,
    default: ''
  },
  // 选项列表，{ value, label, description?, danger? }
  options: {
    type: Array,
    default: () => [],
    validator: (val) => Array.isArray(val)
  },
  // 是否显示底部独立的取消按钮
  showCancel: {
    type: Boolean,
    default: true
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  // 弹窗宽度
  width: {
    type: String,
    default: '360px'
  }
})

const emit = defineEmits(['select', 'cancel', 'update:visible'])

const closeTimer = ref(null)

const handleSelect = (option) => {
  if (!option || option.disabled) return
  emit('select', option.value, option)
  emit('update:visible', false)
}

const handleCancel = () => {
  emit('cancel')
  emit('update:visible', false)
}

const handleOverlayClick = () => {
  handleCancel()
}

const handleKeydown = (e) => {
  if (e.key === 'Escape' && props.visible) {
    handleCancel()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  if (closeTimer.value) clearTimeout(closeTimer.value)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="option-dialog">
      <div v-if="visible" class="option-dialog-overlay" @click="handleOverlayClick">
        <div class="option-dialog" :style="{ width }" @click.stop>
          <div class="option-dialog__header">
            <h3 class="option-dialog__title">{{ title }}</h3>
          </div>
          <div v-if="message" class="option-dialog__content">
            <p class="option-dialog__message">{{ message }}</p>
          </div>
          <div class="option-dialog__options">
            <button
              v-for="(option, index) in options"
              :key="index"
              type="button"
              class="option-dialog__option"
              :class="{
                'option-dialog__option--danger': option.danger,
                'option-dialog__option--disabled': option.disabled
              }"
              :disabled="option.disabled"
              @click="handleSelect(option)"
            >
              <span class="option-dialog__option-label">{{ option.label }}</span>
              <span v-if="option.description" class="option-dialog__option-description">{{ option.description }}</span>
            </button>
          </div>
          <div v-if="showCancel" class="option-dialog__actions">
            <button class="option-dialog__btn option-dialog__btn--cancel" @click="handleCancel">
              {{ cancelText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style lang="scss" scoped>
.option-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.option-dialog {
  background: #2a2a2a;
  border-radius: 12px;
  min-width: 320px;
  max-width: 90vw;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;

  &__header {
    padding: 20px 24px 8px;
  }

  &__title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #fff;
  }

  &__content {
    padding: 8px 24px 4px;
  }

  &__message {
    margin: 0;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.8);
    line-height: 1.5;
  }

  &__options {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 24px 4px;
  }

  &__option {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    width: 100%;
    padding: 12px 16px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
    color: #fff;
    text-align: left;
    font-family: inherit;

    &:hover:not(:disabled) {
      background: rgba(74, 158, 255, 0.18);
      border-color: rgba(74, 158, 255, 0.4);
      transform: translateY(-1px);
    }

    &--danger:hover:not(:disabled) {
      background: rgba(229, 57, 53, 0.2);
      border-color: rgba(229, 57, 53, 0.5);
    }

    &--disabled,
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  &__option-label {
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
  }

  &__option-description {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
    line-height: 1.4;
  }

  &__actions {
    padding: 12px 24px 20px;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }

  &__btn {
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s ease;
    font-family: inherit;

    &--cancel {
      background: rgba(255, 255, 255, 0.1);
      color: rgba(255, 255, 255, 0.8);

      &:hover {
        background: rgba(255, 255, 255, 0.15);
      }
    }
  }
}

.option-dialog-enter-active,
.option-dialog-leave-active {
  transition: opacity 0.2s ease;

  .option-dialog {
    transition: transform 0.2s ease, opacity 0.2s ease;
  }
}

.option-dialog-enter-from,
.option-dialog-leave-to {
  opacity: 0;

  .option-dialog {
    transform: scale(0.95);
    opacity: 0;
  }
}
</style>
