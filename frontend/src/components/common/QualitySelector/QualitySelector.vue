<template>
  <div class="quality-selector">
    <label v-if="label" class="quality-selector__label">{{ label }}</label>
    <div class="quality-selector__group">
      <button
        v-for="quality in qualities"
        :key="quality.value"
        type="button"
        :class="['quality-selector__option', { 'quality-selector__option--selected': modelValue === quality.value }]"
        @click="selectQuality(quality.value)"
      >
        <span class="quality-selector__icon">
          <svg v-if="quality.value === 'low'" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M4 8L8 4L12 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <svg v-else-if="quality.value === 'medium'" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M4 11L8 6L12 11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <svg v-else-if="quality.value === 'high'" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 8L8 3L13 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M5 11L8 8L11 11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="2" fill="currentColor"/>
            <path d="M8 2V4M8 12V14M2 8H4M12 8H14M3.5 3.5L5 5M11 11L12.5 12.5M12.5 3.5L11 5M5 11L3.5 12.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </span>
        <span class="quality-selector__text">{{ quality.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  modelValue: {
    type: String,
    default: 'medium'
  },
  label: {
    type: String,
    default: ''
  },
  options: {
    type: Array,
    default: () => ([
      { value: 'low', label: 'Low' },
      { value: 'medium', label: 'Medium' },
      { value: 'high', label: 'High' },
      { value: 'auto', label: 'Auto' }
    ])
  }
});

const emit = defineEmits(['update:modelValue']);

const selectQuality = (qualityValue) => {
  emit('update:modelValue', qualityValue);
};

const qualities = computed(() => props.options);
</script>

<script>
export default {
  name: 'QualitySelector'
};
</script>

<style lang="scss" src="./QualitySelector.scss"></style>
