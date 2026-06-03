<template>
  <div class="global-select-wrapper" :class="wrapperClass">
    <div 
      class="global-select" 
      :class="{ 'global-select--disabled': disabled }"
      @click="toggleDropdown"
      ref="selectRef"
    >
      <span class="global-select__value">
        <slot name="value" :selected="selectedOption">
          {{ selectedOption?.label || placeholder }}
        </slot>
      </span>
      <svg class="global-select-arrow" :class="{ 'global-select-arrow--open': isOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </div>

    <teleport to="body">
      <transition name="select-dropdown">
        <div 
          v-if="isOpen" 
          class="global-select-dropdown"
          :style="dropdownStyle"
          ref="dropdownRef"
          @click.stop
          @wheel.stop
          @scroll.stop
        >
          <div 
            v-for="option in options" 
            :key="option.value"
            class="global-select-option"
            :class="{ 
              'global-select-option--selected': modelValue === option.value,
              'global-select-option--disabled': option.disabled
            }"
            @click="selectOption(option)"
          >
            <slot name="option" :option="option">
              <span class="global-select-option__label">{{ option.label }}</span>
            </slot>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: ''
  },
  options: {
    type: Array,
    default: () => []
  },
  placeholder: {
    type: String,
    default: '请选择'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  wrapperClass: {
    type: [String, Array, Object],
    default: ''
  }
});

const emit = defineEmits(['update:modelValue', 'change', 'open', 'close']);

const isOpen = ref(false);
const selectRef = ref(null);
const dropdownRef = ref(null);
const scrollTick = ref(0);

const selectedOption = computed(() => {
  return props.options.find(opt => opt.value === props.modelValue);
});

const dropdownStyle = computed(() => {
  if (!selectRef.value) return {};

  void scrollTick.value;

  const rect = selectRef.value.getBoundingClientRect();
  return {
    width: `${rect.width}px`,
    top: `${rect.bottom + window.scrollY + 6}px`,
    left: `${rect.left + window.scrollX}px`
  };
});

const toggleDropdown = () => {
  if (props.disabled) return;
  isOpen.value = !isOpen.value;
  if (isOpen.value) {
    emit('open');
  } else {
    emit('close');
  }
};

const selectOption = (option) => {
  if (option.disabled) return;
  
  emit('update:modelValue', option.value);
  emit('change', option);
  isOpen.value = false;
};

const handleClickOutside = (event) => {
  if (selectRef.value && !selectRef.value.contains(event.target)) {
    isOpen.value = false;
    emit('close');
  }
};

const handleScroll = (event) => {
  if (!isOpen.value) return;

  if (dropdownRef.value && dropdownRef.value.contains(event.target)) {
    return;
  }

  scrollTick.value++;
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
  window.addEventListener('scroll', handleScroll, true);
  window.addEventListener('resize', handleScroll);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
  window.removeEventListener('scroll', handleScroll, true);
  window.removeEventListener('resize', handleScroll);
});

watch(isOpen, (newVal) => {
  if (newVal) {
    // 打开下拉菜单时的逻辑
  }
});
</script>

<style lang="scss">
@import './Select.scss';
</style>
