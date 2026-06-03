<template>
  <div id="app">
    <nav class="nav">
      <div class="nav__logo">
        <div class="nav__logo-icon">
          <svg viewBox="0 0 24 24" fill="none">
            <defs>
              <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#6366f1"/>
                <stop offset="100%" style="stop-color:#8b5cf6"/>
              </linearGradient>
            </defs>
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="url(#logoGradient)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="nav__brand">
          <span class="nav__brand-title">图像生成工作台</span>
          <span class="nav__brand-subtitle">本地运行，无需登录</span>
        </div>
      </div>
      <div class="nav__actions">
        <router-link to="/create" class="nav__action-btn" :class="{ 'nav__action-btn--active': $route.path === '/create' }">
          <svg class="nav__action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            <polyline points="17 7 12 2 7 7"/>
            <line x1="12" y1="2" x2="12" y2="15"/>
          </svg>
          <span>图像生成</span>
        </router-link>
        <router-link to="/edit" class="nav__action-btn" :class="{ 'nav__action-btn--active': $route.path === '/edit' }">
          <svg class="nav__action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          <span>图像编辑</span>
        </router-link>

        <router-link to="/prepare" class="nav__action-btn" :class="{ 'nav__action-btn--active': $route.path === '/prepare' }">
          <svg class="nav__action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span>预备</span>
        </router-link>
        <router-link to="/copy-management" class="nav__action-btn" :class="{ 'nav__action-btn--active': $route.path === '/copy-management' }">
          <svg class="nav__action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          <span>文案管理</span>
        </router-link>
        <router-link to="/settings" class="nav__action-btn nav__action-btn--icon-only">
          <svg class="nav__action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        </router-link>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style lang="scss">
@import '@/styles/common';

#app {
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(180deg, $color-bg-secondary 0%, $color-bg 100%);
}

.nav {
  @include flex-between;
  padding: $spacing-sm $spacing-xl;
  height: 72px;
  background: rgba($color-bg-card, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba($color-border, 0.4);
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.04);
}

.nav__logo {
  display: flex;
  align-items: center;
  gap: $spacing-md;
}

.nav__logo-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
  border-radius: $radius-lg;
  box-shadow: 0 4px 15px rgba($primary-color, 0.3);
}

.nav__logo-icon svg {
  width: 22px;
  height: 22px;
}

.nav__brand {
  display: flex;
  flex-direction: column;
}

.nav__brand-title {
  font-size: $font-size-lg;
  font-weight: 700;
  color: $color-text-primary;
}

.nav__brand-subtitle {
  font-size: 10px;
  color: $color-text-tertiary;
  letter-spacing: 0.02em;
}

.nav__actions {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.nav__action-btn {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  padding: $spacing-sm $spacing-md;
  border-radius: $radius-lg;
  color: $color-text-secondary;
  text-decoration: none;
  font-size: $font-size-sm;
  font-weight: 500;
  transition: all $transition-fast;
  background: transparent;
  border: none;
  cursor: pointer;

  &:hover {
    background: $color-bg-secondary;
    color: $color-text-primary;
  }

  &--active {
    background: linear-gradient(135deg, rgba($primary-color, 0.12) 0%, rgba($primary-color, 0.06) 100%);
    color: $color-primary;

    &:hover {
      background: linear-gradient(135deg, rgba($primary-color, 0.18) 0%, rgba($primary-color, 0.1) 100%);
    }
  }

  &--icon-only {
    padding: $spacing-sm;
  }
}

.nav__action-icon {
  width: 18px;
  height: 18px;
}

.main-content {
  width: 100%;
}
</style>
