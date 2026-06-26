<template>
  <Teleport to="body">
    <div class="image-compare" @click.self="emit('close')">
      <button class="image-compare__close" @click="emit('close')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
      <div
        class="image-compare__slider"
        ref="sliderRef"
        @mousemove="updatePos"
        @touchmove.prevent="updatePos"
      >
        <img :src="newImage.url" class="image-compare__img" />
        <img
          :src="originalImage?.url || newImage.url"
          class="image-compare__img image-compare__img--top"
          :style="{ clipPath: `inset(0 0 0 ${sliderPos}%)` }"
        />
        <div class="image-compare__line" :style="{ left: sliderPos + '%' }">
          <div class="image-compare__handle">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </div>
        </div>
      </div>
      <div class="image-compare__labels">
        <span class="image-compare__label image-compare__label--left">{{ leftLabel }}</span>
        <span class="image-compare__label image-compare__label--right">{{ rightLabel }}</span>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  newImage: { type: Object, required: true },
  originalImage: { type: Object, default: null },
  leftLabel: { type: String, default: '编辑后' },
  rightLabel: { type: String, default: '原图' }
})

const emit = defineEmits(['close'])

const sliderRef = ref(null)
const sliderPos = ref(50)

// 鼠标移动时实时更新滑杆位置，无需点击
const updatePos = (e) => {
  const rect = sliderRef.value?.getBoundingClientRect()
  if (!rect) return
  const clientX = e.touches ? e.touches[0].clientX : e.clientX
  const pos = ((clientX - rect.left) / rect.width) * 100
  sliderPos.value = Math.max(0, Math.min(100, pos))
}

const handleKeydown = (e) => {
  if (e.key === 'Escape') {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style lang="scss">
.image-compare {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;

  &__close {
    position: absolute;
    top: 16px;
    right: 24px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 50%;
    width: 40px;
    height: 40px;
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;

    svg {
      width: 20px;
      height: 20px;
    }

    &:hover {
      background: rgba(255, 255, 255, 0.2);
    }
  }

  &__slider {
    position: relative;
    max-width: 90vw;
    max-height: 80vh;
    cursor: col-resize;
    user-select: none;
    -webkit-user-select: none;
    overflow: hidden;
  }

  &__img {
    max-width: 90vw;
    max-height: 80vh;
    object-fit: contain;
    display: block;

    &--top {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      max-width: none;
      max-height: none;
      object-fit: fill;
    }
  }

  &__line {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #fff;
    box-shadow: 0 0 6px rgba(0, 0, 0, 0.4);
    pointer-events: none;
    z-index: 2;
  }

  &__handle {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 44px;
    height: 44px;
    background: #fff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);

    svg {
      width: 22px;
      height: 22px;
      color: #333;
    }
  }

  &__labels {
    display: flex;
    justify-content: space-between;
    width: 100%;
    max-width: 90vw;
    padding: 0 8px;
  }

  &__label {
    color: rgba(255, 255, 255, 0.6);
    font-size: 13px;
    font-weight: 500;

    &--left {
      padding-left: 4px;
    }

    &--right {
      padding-right: 4px;
    }
  }
}
</style>
