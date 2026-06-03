<template>
  <button
    :class="[
      'btn',
      `btn--${type}`,
      `btn--${size}`,
      { 'btn--disabled': disabled, 'btn--loading': loading, 'btn--block': block }
    ]"
    :disabled="disabled || loading"
    :type="nativeType"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="btn__loader"></span>
    <span :class="{ 'btn__content--hidden': loading }">
      <slot></slot>
    </span>
  </button>
</template>

<script setup>
defineProps({
  type: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'secondary', 'danger', 'outline', 'ghost'].includes(value)
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg'].includes(value)
  },
  nativeType: {
    type: String,
    default: 'button',
    validator: (value) => ['button', 'submit', 'reset'].includes(value)
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  block: {
    type: Boolean,
    default: false
  }
});

defineEmits(['click']);
</script>

<script>
export default {
  name: 'AppButton'
};
</script>

<style lang="scss" src="./Button.scss"></style>