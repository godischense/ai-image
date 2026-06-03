<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '确认'
  },
  message: {
    type: String,
    default: '确定要执行此操作吗？'
  },
  confirmText: {
    type: String,
    default: '确定'
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  danger: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['confirm', 'cancel', 'update:visible'])

const handleConfirm = () => {
  emit('confirm')
  emit('update:visible', false)
}

const handleCancel = () => {
  emit('cancel')
  emit('update:visible', false)
}

const handleOverlayClick = () => {
  emit('cancel')
  emit('update:visible', false)
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
})
</script>

<template>
  <Teleport to="body">
    <Transition name="confirm-dialog">
      <div v-if="visible" class="confirm-dialog-overlay" @click="handleOverlayClick">
        <div class="confirm-dialog" @click.stop>
          <div class="confirm-dialog__header">
            <h3 class="confirm-dialog__title">{{ title }}</h3>
          </div>
          <div class="confirm-dialog__content">
            <p class="confirm-dialog__message">{{ message }}</p>
          </div>
          <div class="confirm-dialog__actions">
            <button v-if="cancelText" class="confirm-dialog__btn confirm-dialog__btn--cancel" @click="handleCancel">
              {{ cancelText }}
            </button>
            <button
              class="confirm-dialog__btn"
              :class="danger ? 'confirm-dialog__btn--danger' : 'confirm-dialog__btn--confirm'"
              @click="handleConfirm"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style lang="scss" scoped>
.confirm-dialog-overlay {
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

.confirm-dialog {
  background: #2a2a2a;
  border-radius: 12px;
  min-width: 320px;
  max-width: 90vw;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);

  &__header {
    padding: 20px 24px 0;
  }

  &__title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #fff;
  }

  &__content {
    padding: 16px 24px;
  }

  &__message {
    margin: 0;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.8);
    line-height: 1.5;
  }

  &__actions {
    padding: 16px 24px 20px;
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

    &--cancel {
      background: rgba(255, 255, 255, 0.1);
      color: rgba(255, 255, 255, 0.8);

      &:hover {
        background: rgba(255, 255, 255, 0.15);
      }
    }

    &--confirm {
      background: #4a9eff;
      color: #fff;

      &:hover {
        background: #3a8eef;
      }
    }

    &--danger {
      background: #e53935;
      color: #fff;

      &:hover {
        background: #d32f2f;
      }
    }
  }
}

.confirm-dialog-enter-active,
.confirm-dialog-leave-active {
  transition: opacity 0.2s ease;

  .confirm-dialog {
    transition: transform 0.2s ease, opacity 0.2s ease;
  }
}

.confirm-dialog-enter-from,
.confirm-dialog-leave-to {
  opacity: 0;

  .confirm-dialog {
    transform: scale(0.95);
    opacity: 0;
  }
}
</style>
