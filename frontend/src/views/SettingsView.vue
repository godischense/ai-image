<template>
  <div class="settings-view">
    <div class="settings-view__content">
      <ConfigPanel />
    </div>
  </div>
</template>

<script setup>
import ConfigPanel from '@/components/ConfigPanel.vue'
</script>

<style lang="scss" scoped>
@import '@/styles/SettingsView.scss';
</style>