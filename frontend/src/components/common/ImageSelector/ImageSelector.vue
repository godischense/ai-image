<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="image-selector-overlay" @click.self="handleClose">
        <div class="image-selector">
          <div class="image-selector__header">
            <h2 class="image-selector__title">选择图片</h2>
            <button class="image-selector__close" @click="handleClose">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
              </svg>
            </button>
          </div>
          <div class="image-selector__content">
            <div v-if="images.length === 0" class="image-selector__empty">
              暂无图片
            </div>
            <div v-else class="image-selector__grid">
              <div
                v-for="(image, index) in images"
                :key="index"
                :class="['image-selector__item', { 'image-selector__item--selected': selectedIndex === index }]"
                @click="handleSelect(image, index)"
              >
                <img :src="image.url || image.src" :alt="image.name || image.alt || 'image'" />
                <div v-if="selectedIndex === index" class="image-selector__check">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  images: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['update:visible', 'select']);

const selectedIndex = ref(-1);

watch(() => props.visible, (newVal) => {
  if (newVal) {
    selectedIndex.value = -1;
  }
});

const handleClose = () => {
  emit('update:visible', false);
};

const handleSelect = (image, index) => {
  selectedIndex.value = index;
  setTimeout(() => {
    emit('select', image);
    emit('update:visible', false);
  }, 200);
};
</script>

<script>
export default {
  name: 'ImageSelector'
};
</script>

<style lang="scss" src="./ImageSelector.scss"></style>