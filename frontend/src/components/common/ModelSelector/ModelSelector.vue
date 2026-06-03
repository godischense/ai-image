<template>
  <div class="model-selector">
    <label v-if="label" class="model-selector__label">{{ label }}</label>
    <div v-if="showModes" class="model-selector__mode-tabs">
      <button
        v-for="mode in modes"
        :key="mode.value"
        type="button"
        :class="['model-selector__tab', { 'model-selector__tab--active': currentMode === mode.value }]"
        @click="currentMode = mode.value"
      >
        {{ mode.label }}
      </button>
    </div>
    <div class="model-selector__grid">
      <button
        v-for="model in availableModels"
        :key="model.id"
        type="button"
        :class="['model-selector__item', { 'model-selector__item--selected': modelValue === model.id }]"
        @click="selectModel(model.id)"
      >
        <span class="model-selector__item-name">{{ model.name }}</span>
        <span v-if="model.description" class="model-selector__item-desc">{{ model.description }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  label: {
    type: String,
    default: ''
  },
  showModes: {
    type: Boolean,
    default: false
  },
  models: {
    type: Array,
    default: () => ([
      { id: 'gpt-image-2', name: 'GPT Image 2', description: 'OpenAI latest image model', mode: 'direct' },
      { id: 'flux-kontext-pro', name: 'Flux Kontext Pro', description: 'Black Forest Lab professional', mode: 'direct' },
      { id: 'flux-kontext-max', name: 'Flux Kontext Max', description: 'Black Forest Lab maximum', mode: 'direct' },
      { id: 'gpt-image-2', name: 'GPT Image 2', description: 'OpenAI latest with chat', mode: 'chat' },
      { id: 'flux-kontext-pro', name: 'Flux Kontext Pro', description: 'Professional with chat', mode: 'chat' }
    ])
  }
});

const emit = defineEmits(['update:modelValue']);

const modes = [
  { value: 'direct', label: 'Direct Mode' },
  { value: 'chat', label: 'Chat Mode' }
];

const currentMode = ref('direct');

const availableModels = computed(() => {
  const normalizedModels = props.models
    .map((model) => {
      if (typeof model === 'string') {
        return {
          id: model,
          name: model,
          description: '',
          mode: 'all'
        };
      }

      return {
        id: model.id || model.value || model.name,
        name: model.name || model.label || model.id || model.value,
        description: model.description || '',
        mode: model.mode || 'all'
      };
    })
    .filter((model) => Boolean(model.id));

  if (!props.showModes) {
    return normalizedModels;
  }

  return normalizedModels.filter((model) => model.mode === 'all' || model.mode === currentMode.value);
});

const selectModel = (modelId) => {
  emit('update:modelValue', modelId);
};

watch(
  [currentMode, () => props.models, () => props.showModes],
  () => {
    const currentModel = availableModels.value.find(m => m.id === props.modelValue);
    if (!currentModel) {
      emit('update:modelValue', availableModels.value[0]?.id || '');
    }
  },
  { deep: true, immediate: true }
);
</script>

<script>
export default {
  name: 'ModelSelector'
};
</script>

<style lang="scss" src="./ModelSelector.scss"></style>
