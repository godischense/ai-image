<template>
  <div class="size-selector">
    <label v-if="label" class="size-selector__label">{{ label }}</label>
    <div class="size-selector__grid">
      <button
        v-for="size in sizes"
        :key="size.value"
        type="button"
        :class="['size-selector__item', { 'size-selector__item--selected': modelValue === size.value }]"
        @click="selectSize(size.value)"
      >
        <span class="size-selector__preview" :style="getPreviewStyle(size)"></span>
        <span class="size-selector__dimensions">{{ size.label || size.value }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    default: '1024x1024'
  },
  label: {
    type: String,
    default: ''
  },
  sizes: {
    type: Array,
    default: () => ([
      { value: '1024x1024', label: '1024x1024', ratio: '1:1', width: 1024, height: 1024 },
      { value: '1536x1024', label: '1536x1024', ratio: '3:2', width: 1536, height: 1024 },
      { value: '1024x1536', label: '1024x1536', ratio: '2:3', width: 1024, height: 1536 },
      { value: '2048x2048', label: '2048x2048', ratio: '1:1', width: 2048, height: 2048 },
      { value: '2048x1152', label: '2048x1152', ratio: '16:9', width: 2048, height: 1152 },
      { value: '3840x2160', label: '3840x2160', ratio: '16:9', width: 3840, height: 2160 },
      { value: '2160x3840', label: '2160x3840', ratio: '9:16', width: 2160, height: 3840 }
    ])
  }
});

const emit = defineEmits(['update:modelValue']);

const selectSize = (sizeValue) => {
  emit('update:modelValue', sizeValue);
};

const getPreviewStyle = (size) => {
  const maxPreviewSize = 40;
  const width = size.width || 1;
  const height = size.height || 1;
  const aspectRatio = width / height;

  let previewWidth;
  let previewHeight;
  if (aspectRatio >= 1) {
    previewWidth = maxPreviewSize;
    previewHeight = maxPreviewSize / aspectRatio;
  } else {
    previewHeight = maxPreviewSize;
    previewWidth = maxPreviewSize * aspectRatio;
  }

  return {
    width: `${previewWidth}px`,
    height: `${previewHeight}px`
  };
};
</script>

<script>
export default {
  name: 'SizeSelector'
};
</script>

<style lang="scss" src="./SizeSelector.scss"></style>
