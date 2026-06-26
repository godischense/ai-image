<template>
  <!-- 头部余额展示：横向多 chip 布局，为未来多平台预留空间 -->
  <div class="user-balance-header"></div>
</template>

<style lang="scss" scoped>
@use '@/styles/variables' as *;
@use '@/styles/mixins' as *;

.user-balance-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: $spacing-xs;
  // 与 nav 按钮的垂直基线对齐
  padding: 0 $spacing-xs;
}

.balance-chip {
  display: inline-flex;
  align-items: center;
  gap: $spacing-xs;
  padding: 0.375rem 0.625rem;
  border: 1px solid $border-color;
  border-radius: $radius-full;
  background: rgba($color-bg-card, 0.7);
  color: $color-text-primary;
  font-size: $font-size-xs;
  font-weight: $font-weight-medium;
  transition: all $transition-fast;

  &--success {
    border-color: rgba($primary-color, 0.25);
    background: linear-gradient(135deg, rgba($primary-color, 0.08), rgba($secondary-color, 0.06));
    color: $color-primary;
  }

  &--error {
    border-color: rgba($danger-color, 0.3);
    background: rgba($danger-color, 0.06);
    color: $danger-hover;
    cursor: help;
  }

  &--loading {
    opacity: 0.7;
  }

  &--empty {
    background: transparent;
    border-style: dashed;
    color: $color-text-tertiary;
  }
}

.balance-name {
  font-weight: $font-weight-semibold;
  color: inherit;
  opacity: 0.9;
}

.balance-amount {
  font-variant-numeric: tabular-nums;
  font-weight: $font-weight-semibold;
  color: inherit;
}

.balance-link {
  color: $color-primary;
  text-decoration: none;
  font-weight: $font-weight-medium;
  transition: color $transition-fast;

  &:hover {
    color: $color-primary-hover;
    text-decoration: underline;
  }
}

.balance-refresh {
  @include flex-center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  border-radius: $radius-full;
  background: transparent;
  color: inherit;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  transition: background-color $transition-fast, transform $transition-fast;

  &:hover:not(:disabled) {
    background-color: rgba($primary-color, 0.12);
  }

  &:active:not(:disabled) {
    transform: scale(0.92);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  // 加载中时这个 span 也旋转
  &--spinning {
    display: inline-block;
    animation: ub-spin 1s linear infinite;
  }
}

@keyframes ub-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
