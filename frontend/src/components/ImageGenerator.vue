<template>
  <div class="image-generator">
    <div class="image-generator__header">
      <h2 class="image-generator__title">图像生成</h2>
      <div class="image-generator__mode-toggle">
        <span :class="{ 'u-text-primary': !isAsync }">同步</span>
        <button
          class="image-generator__toggle-switch"
          :class="{ 'image-generator__toggle-switch--active': isAsync }"
          @click="toggleAsync"
          :disabled="loading"
        ></button>
        <span :class="{ 'u-text-primary': isAsync }">异步</span>
      </div>
    </div>

    <div class="image-generator__form">
      <div class="image-generator__field">
        <div class="image-generator__field-header">
          <label class="image-generator__label">
            <svg class="image-generator__label-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7.5 18H4v-3.667L16.5 3.5z"></path>
            </svg>
            提示词
            <span class="image-generator__label-required">*</span>
          </label>
          <div class="image-generator__field-header-right">
            <button
              class="image-generator__optimize-btn"
              :class="{ 'image-generator__optimize-btn--loading': optimizing }"
              @click="handleOptimize"
              :disabled="!prompt.trim() || optimizing"
              :title="optimizing ? '优化中...' : '优化提示词'"
            >
              <svg v-if="optimizing" class="image-generator__spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="2" x2="12" y2="6"></line>
                <line x1="12" y1="18" x2="12" y2="22"></line>
                <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
                <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                <line x1="2" y1="12" x2="6" y2="12"></line>
                <line x1="18" y1="12" x2="22" y2="12"></line>
                <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
                <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
              </svg>
              <span>{{ optimizing ? '优化中...' : '优化提示词' }}</span>
            </button>
          </div>
        </div>
        <div class="image-generator__textarea-wrapper">
          <textarea
            v-model="prompt"
            class="image-generator__textarea"
            placeholder="请输入你想生成的画面描述..."
            :disabled="loading"
          ></textarea>
          <div class="image-generator__textarea-actions">
            <button
              v-if="originalPromptBeforeOptimize"
              class="image-generator__revert-btn"
              @click="handleRevertOptimize"
              title="返回原文"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="1 4 1 10 7 10"></polyline>
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
              </svg>
              <span>返回原文</span>
            </button>
            <svg class="image-generator__textarea-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7.5 18H4v-3.667L16.5 3.5z"></path>
            </svg>
          </div>
        </div>
      </div>

      <div class="image-generator__field">
        <div class="image-generator__reference-header">
          <label class="image-generator__label">
            <svg class="image-generator__label-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <circle cx="8.5" cy="8.5" r="1.5"></circle>
              <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
            参考图
          </label>
          <div class="image-generator__reference-actions">
            <button class="image-generator__reference-action-btn" @click="showMaterialSelector = true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
              </svg>
              素材库
            </button>
            <span class="image-generator__reference-count">{{ referenceImages.length }}/{{ maxRefImages }}</span>
          </div>
        </div>
        <div class="image-generator__reference">
          <div
            class="image-generator__reference-dropzone"
            :class="{ 'image-generator__reference-dropzone--dragover': isDragOver }"
            @dragover.prevent="handleDragOver"
            @dragleave.prevent="handleDragLeave"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <div class="image-generator__reference-icon-wrapper">
              <svg class="image-generator__reference-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
            </div>
            <span class="image-generator__reference-text">点击或拖拽上传参考图</span>
            <span class="image-generator__reference-hint">支持 JPG、PNG、WebP，最多上传 {{ maxRefImages }} 张</span>
            <input
              type="file"
              ref="fileInputRef"
              class="image-generator__reference-input"
              accept="image/jpeg,image/png,image/webp"
              multiple
              @change="handleFileSelect"
            />
          </div>
          <div v-if="referenceImages.length > 0" class="image-generator__reference-grid">
            <div
              v-for="(img, index) in referenceImages"
              :key="img.id"
              class="image-generator__reference-item"
            >
              <img v-if="!img.uploading" :src="img.url" class="image-generator__reference-thumb" />
              <div v-else class="image-generator__reference-uploading">
                <svg class="image-generator__spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="2" x2="12" y2="6"></line>
                  <line x1="12" y1="18" x2="12" y2="22"></line>
                  <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
                  <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                  <line x1="2" y1="12" x2="6" y2="12"></line>
                  <line x1="18" y1="12" x2="22" y2="12"></line>
                  <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
                  <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
                </svg>
              </div>
              <div v-if="!img.uploading" class="image-generator__reference-overlay">
                <button class="image-generator__reference-btn" @click.stop="handlePreviewRefImage(img)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                  </svg>
                </button>
                <button class="image-generator__reference-btn image-generator__reference-btn--danger" @click.stop="handleRemoveRefImage(index)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="image-generator__selectors">
        <!-- API 提供者选择器 - 独立一行 -->
        <div class="image-generator__selector-row image-generator__selector-row--full">
          <div class="image-generator__selector">
            <label class="image-generator__label">API</label>
            <Select
              v-model="selectedApiProvider"
              :options="apiProviderOptions"
              :disabled="loading"
            />
          </div>
        </div>

        <div v-if="isGptsapiProvider" class="image-generator__selector-row image-generator__selector-row--gptsapi">
          <div class="image-generator__selector">
            <label class="image-generator__label">比例</label>
            <Select
              v-model="selectedAspectRatio"
              :options="currentAspectRatioOptions.map(r => ({ value: r.value, label: r.label }))"
              :disabled="loading"
            />
          </div>

          <div class="image-generator__selector">
            <label class="image-generator__label">res</label>
            <div class="image-generator__button-group">
              <button
                v-for="resolution in currentResolutions"
                :key="resolution.value"
                type="button"
                :class="['image-generator__btn-option', { 'image-generator__btn-option--selected': selectedResolution === resolution.value }]"
                @click="selectedResolution = resolution.value"
                :disabled="loading"
              >
                {{ resolution.label }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="!isGptsapiProvider" class="image-generator__selector-row">
          <div class="image-generator__selector">
            <label class="image-generator__label">模型</label>
            <Select
              v-model="selectedModel"
              :options="modelOptions.map(m => ({ value: m.id, label: m.name }))"
              :disabled="loading"
            />
          </div>

          <div class="image-generator__selector">
            <label class="image-generator__label">比例</label>
            <Select
              v-model="selectedAspectRatio"
              :options="currentAspectRatioOptions.map(r => ({ value: r.value, label: r.label }))"
              :disabled="loading"
            />
          </div>
        </div>

        <div v-if="!isGptsapiProvider" class="image-generator__selector-row">
          <div class="image-generator__selector">
            <label class="image-generator__label">res</label>
            <div class="image-generator__button-group">
              <button
                v-for="resolution in currentResolutions"
                :key="resolution.value"
                type="button"
                :class="['image-generator__btn-option', { 'image-generator__btn-option--selected': selectedResolution === resolution.value }]"
                @click="selectedResolution = resolution.value"
                :disabled="loading"
              >
                {{ resolution.label }}
              </button>
            </div>
          </div>

          <div class="image-generator__selector">
            <label class="image-generator__label">质量</label>
            <Select
              v-model="selectedQuality"
              :options="qualityOptions.map(q => ({ value: q.value, label: q.label }))"
              :disabled="loading"
            />
          </div>
        </div>

        <!-- 生成数量和随机种子 -->
        <div v-if="!isGptsapiProvider" class="image-generator__selector-row">
          <div v-if="selectedApiProvider === 'fal'" class="image-generator__selector">
            <label class="image-generator__label">生成数量</label>
            <Select
              v-model="selectedNumImages"
              :options="numImageOptions"
              :disabled="loading"
            />
          </div>
          <div class="image-generator__selector">
            <label class="image-generator__label">随机种子</label>
            <div class="image-generator__seed-wrapper">
              <input
                v-model.number="selectedSeed"
                type="number"
                class="image-generator__seed-input"
                min="0"
                max="2147483647"
                :disabled="loading"
                placeholder="0=随机"
              />
              <button
                type="button"
                class="image-generator__seed-dice"
                :disabled="loading"
                @click="randomizeSeed"
                title="随机生成种子"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="3" width="18" height="18" rx="3"></rect>
                  <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor"></circle>
                  <circle cx="15.5" cy="8.5" r="1.5" fill="currentColor"></circle>
                  <circle cx="8.5" cy="15.5" r="1.5" fill="currentColor"></circle>
                  <circle cx="15.5" cy="15.5" r="1.5" fill="currentColor"></circle>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div v-if="!isGptsapiProvider" class="image-generator__selector-row">
          <div class="image-generator__selector">
            <label class="image-generator__label">输出</label>
            <Select
              v-model="selectedOutputFormat"
              :options="outputFormats.map(f => ({ value: f.value, label: f.label }))"
              :disabled="loading"
            />
          </div>

          <div class="image-generator__selector">
            <label class="image-generator__label">背景</label>
            <Select
              v-model="selectedBackground"
              :options="backgroundOptions.map(b => ({ value: b.value, label: b.label }))"
              :disabled="loading"
            />
          </div>
        </div>

        <div
          v-if="!isGptsapiProvider && (selectedOutputFormat === 'jpeg' || selectedOutputFormat === 'webp')"
          class="image-generator__compression-row"
        >
          <label class="image-generator__label">
            压缩率: {{ selectedOutputCompression }}%
          </label>
          <input
            v-model.number="selectedOutputCompression"
            type="range"
            min="0"
            max="100"
            class="image-generator__compression-slider"
            :disabled="loading"
          />
        </div>
      </div>

      <div class="image-generator__meta">
        <div class="image-generator__meta-item">
          <span class="image-generator__meta-label">实际尺寸</span>
          <span class="image-generator__meta-value">{{ resolvedSize }}</span>
        </div>
        <div v-if="isGptsapiProvider" class="image-generator__meta-item">
          <span class="image-generator__meta-label">端点</span>
          <span class="image-generator__meta-value">{{ referenceImages.length > 0 ? '图生图' : '文生图' }}</span>
        </div>
        <div v-if="!isGptsapiProvider" class="image-generator__meta-item">
          <span class="image-generator__meta-label">导出格式</span>
          <span class="image-generator__meta-value">{{ selectedOutputFormat.toUpperCase() }}</span>
        </div>
        <div v-if="!isGptsapiProvider" class="image-generator__meta-item">
          <span class="image-generator__meta-label">清晰度</span>
          <span class="image-generator__meta-value">{{ selectedQualityLabel }}</span>
        </div>
        <div v-if="!isGptsapiProvider" class="image-generator__meta-item">
          <span class="image-generator__meta-label">背景</span>
          <span class="image-generator__meta-value">{{ selectedBackground.toUpperCase() }}</span>
        </div>
      </div>

      <div v-if="error" class="image-generator__error">
        <svg class="image-generator__error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        {{ error }}
      </div>

      <div class="image-generator__actions">
        <button
          class="image-generator__btn image-generator__btn--secondary"
          @click="handleReset"
          :disabled="loading"
        >
          重置
        </button>
        <button
          class="image-generator__btn image-generator__btn--primary"
          @click="handleGenerate"
          :disabled="!canGenerate || loading"
        >
          <svg v-if="loading" class="image-generator__btn-icon image-generator__spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="2" x2="12" y2="6"></line>
            <line x1="12" y1="18" x2="12" y2="22"></line>
            <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
            <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
            <line x1="2" y1="12" x2="6" y2="12"></line>
            <line x1="18" y1="12" x2="22" y2="12"></line>
            <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
            <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
          </svg>
          <span>{{ loading ? (isAsync ? '提交中...' : '生成中...') : '开始生成' }}</span>
          <svg v-if="!loading" class="image-generator__btn-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="image-generator__status-bar">
      <div class="image-generator__status-left">
        <div class="image-generator__status-dot"></div>
        <span class="image-generator__status-text">本地服务运行中</span>
      </div>
      <div class="image-generator__status-right">
        <svg class="image-generator__status-settings" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      </div>
    </div>

    <ImagePreview
      v-if="previewRefImage"
      :image="previewRefImage"
      @close="previewRefImage = null"
    />

    <MaterialSelector
      :show="showMaterialSelector"
      :multiple="true"
      :max-count="maxRefImages - referenceImages.length"
      @close="showMaterialSelector = false"
      @select="handleMaterialSelect"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { generateImage, optimizePrompt, api } from '@/services/api'
import { useConfigStore } from '@/stores/configStore'
import ImagePreview from '@/components/ImagePreview.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import Select from '@/components/common/Select/Select.vue'
import './ImageGenerator.scss'

const emit = defineEmits(['generate', 'generate-start', 'download', 'reset', 'error'])
const props = defineProps({
  generating: {
    type: Boolean,
    default: false
  }
})

const configStore = useConfigStore()

const IMAGE_GENERATOR_PREFS_KEY = 'image_generator_prefs'

function loadSavedPrefs() {
  try {
    const data = localStorage.getItem(IMAGE_GENERATOR_PREFS_KEY)
    if (data) {
      return JSON.parse(data)
    }
  } catch {}
  return {}
}

function savePrefs(prefs) {
  try {
    const existing = loadSavedPrefs()
    localStorage.setItem(IMAGE_GENERATOR_PREFS_KEY, JSON.stringify({ ...existing, ...prefs }))
  } catch {}
}

const aspectRatios = [
  { value: '1:1', width: 1, height: 1 },
  { value: '3:2', width: 3, height: 2 },
  { value: '2:3', width: 2, height: 3 },
  { value: '4:3', width: 4, height: 3 },
  { value: '3:4', width: 3, height: 4 },
  { value: '5:4', width: 5, height: 4 },
  { value: '4:5', width: 4, height: 5 },
  { value: '16:9', width: 16, height: 9 },
  { value: '9:16', width: 9, height: 16 },
  { value: '2:1', width: 2, height: 1 },
  { value: '1:2', width: 1, height: 2 },
  { value: '21:9', width: 21, height: 9 },
  { value: '9:21', width: 9, height: 21 }
]

const resolutions = [
  { value: '1K', label: '1K', key: '1k' },
  { value: '2K', label: '2K', key: '2k' },
  { value: '4K', label: '4K', key: '4k' }
]

const sizeMap = {
  '1:1': { '1k': '1024x1024', '2k': '2048x2048', '4k': '2880x2880' },
  '16:9': { '1k': '1280x720', '2k': '2560x1440', '4k': '3840x2160' },
  '9:16': { '1k': '720x1280', '2k': '1440x2560', '4k': '2160x3840' },
  '4:3': { '1k': '1152x864', '2k': '2304x1728', '4k': '3264x2448' },
  '3:4': { '1k': '864x1152', '2k': '1728x2304', '4k': '2448x3264' },
  '3:2': { '1k': '1248x832', '2k': '2496x1664', '4k': '3504x2336' },
  '2:3': { '1k': '832x1248', '2k': '1664x2496', '4k': '2336x3504' },
  '5:4': { '1k': '1120x896', '2k': '2240x1792', '4k': '3200x2560' },
  '4:5': { '1k': '896x1120', '2k': '1792x2240', '4k': '2560x3200' },
  '21:9': { '1k': '1456x624', '2k': '3024x1296', '4k': '3696x1584' },
  '9:21': { '1k': '624x1456', '2k': '1296x3024', '4k': '1584x3696' },
  '2:1': { '1k': '2048x1024', '2k': '2688x1344', '4k': '3840x1920' },
  '1:2': { '1k': '1024x2048', '2k': '1344x2688', '4k': '1920x3840' },
  'fullscreen': { '1k': '688x1488', '2k': '1072x2336', '4k': '1760x3840' }
}

const qualityOptions = [
  { value: 'auto', label: 'Auto' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' }
]

const outputFormats = [
  { value: 'png', label: 'PNG' },
  { value: 'jpeg', label: 'JPEG' },
  { value: 'webp', label: 'WebP' }
]

const backgroundOptions = [
  { value: 'auto', label: 'Auto' },
  { value: 'opaque', label: 'Opaque' }
]

// Fal API 的生成数量选项
const numImageOptions = [
  { value: 1, label: '1' },
  { value: 2, label: '2' },
  { value: 3, label: '3' },
  { value: 4, label: '4' }
]

// 根据选择的 API 提供者返回对应的模型列表
// 选择 Fal 时使用 falModels，否则使用 imageModels
const models = computed(() => {
  if (selectedApiProvider.value === 'fal') {
    return Array.isArray(configStore.falApi.falModels) && configStore.falApi.falModels.length > 0
      ? configStore.falApi.falModels
      : ['openai/gpt-image-2/edit']
  }
  if (selectedApiProvider.value === 'gptsapi') {
    return ['gptsapi/gpt-image-2']
  }
  return Array.isArray(configStore.imageApi.imageModels) && configStore.imageApi.imageModels.length > 0
    ? configStore.imageApi.imageModels
    : ['gpt-image-2/edit']
})



const modelOptions = computed(() => {
  return models.value.map((model) => ({
    id: model,
    name: model,
    description: ''
  }))
})

// 根据是否有 Fal API Key 动态生成 API 提供者选项
const apiProviderOptions = computed(() => {
  const options = [
    { value: 'openai', label: 'OpenAI 兼容' }
  ]
  const hasFalApiKey = configStore.falApi?.apiKey?.trim()
  if (hasFalApiKey) {
    options.push({ value: 'fal', label: 'Fal API' })
  }
  options.push({ value: 'gptsapi', label: 'GPTsAPI' })
  return options
})

const aspectRatioOptions = computed(() => {
  return aspectRatios.map((ratio) => ({
    value: ratio.value,
    label: ratio.value,
    ratio: `${ratio.width}:${ratio.height}`,
    width: ratio.width,
    height: ratio.height
  }))
})

const gptsapiAspectRatioOptions = [
  { value: 'auto', label: '自动' },
  { value: '1:1', label: '1:1' },
  { value: '9:16', label: '9:16' },
  { value: '16:9', label: '16:9' },
  { value: '4:3', label: '4:3' },
  { value: '3:4', label: '3:4' }
]

const savedPrefs = loadSavedPrefs()
const prompt = ref('')
const selectedModel = ref(savedPrefs.selectedModel || 'gpt-image-2')
const selectedAspectRatio = ref('9:16')
const selectedResolution = ref('2K')
const selectedQuality = ref('auto')
const selectedOutputFormat = ref('png')
const selectedOutputCompression = ref(100)
const selectedBackground = ref('auto')
const isAsync = ref(configStore.imageApi?.isAsync || false)
// 当前选择的 API 提供者（openai 或 fal），从 localStorage 恢复
const selectedApiProvider = ref(savedPrefs.selectedApiProvider || 'openai')
// Fal 模式下选中的生成数量
const selectedNumImages = ref(1)
// Fal 模式下随机种子（0=不使用固定种子）
const selectedSeed = ref(0)
const loading = ref(false)
const optimizing = ref(false)
const originalPromptBeforeOptimize = ref('')
const optimizedPosterCopy = ref('')
const error = ref('')
const referenceImages = ref([])
const isDragOver = ref(false)
const fileInputRef = ref(null)
const previewRefImage = ref(null)
const showMaterialSelector = ref(false)
const maxRefSize = 10 * 1024 * 1024

const isGptsapiProvider = computed(() => selectedApiProvider.value === 'gptsapi')
const currentAspectRatioOptions = computed(() => {
  if (isGptsapiProvider.value) return gptsapiAspectRatioOptions
  return [...aspectRatioOptions.value, { value: 'fullscreen', label: '全屏' }]
})
const currentResolutions = computed(() => {
  if (!isGptsapiProvider.value) {
    return resolutions
  }
  if (selectedAspectRatio.value === 'auto') {
    return resolutions.filter(resolution => resolution.value === '1K')
  }
  if (selectedAspectRatio.value === '1:1' && referenceImages.value.length > 0) {
    return resolutions.filter(resolution => resolution.value !== '4K')
  }
  return resolutions
})
const maxRefImages = computed(() => selectedApiProvider.value === 'fal' ? 4 : 16)

const toggleAsync = async () => {
  if (loading.value) return;
  isAsync.value = !isAsync.value;
  try {
    await configStore.saveConfig({
      imageApi: {
        ...configStore.imageApi,
        isAsync: isAsync.value
      }
    });
  } catch (err) {
    console.error('Failed to save isAsync preference', err);
  }
};

const selectedQualityLabel = computed(() => {
  return qualityOptions.find((item) => item.value === selectedQuality.value)?.label || 'Auto'
})


const resolvedSize = computed(() => {
  if (isGptsapiProvider.value && selectedAspectRatio.value === 'auto') {
    return 'auto'
  }

  const sizeByAspect = sizeMap[selectedAspectRatio.value]
  if (!sizeByAspect) {
    return ''
  }

  const resolutionKey = resolutions.find(r => r.value === selectedResolution.value)?.key || '2k'
  return sizeByAspect[resolutionKey] || ''
})

const canGenerate = computed(() => {
  const allRefsReady = referenceImages.value.every(img => !img.uploading)
  return Boolean(prompt.value.trim() && selectedModel.value && resolvedSize.value && allRefsReady)
})

const randomizeSeed = () => {
  selectedSeed.value = Math.floor(Math.random() * 2147483647) + 1
}

onMounted(async () => {
  if (!configStore.initialized) {
    await configStore.fetchConfig()
  }

  isAsync.value = configStore.imageApi?.isAsync || false;

  if (!models.value.includes(selectedModel.value)) {
    selectedModel.value = models.value[0] || 'gpt-image-2'
  }
})

// 当 API 提供者切换时，更新模型选择为对应列表的第一个模型
watch(selectedApiProvider, (val) => {
  savePrefs({ selectedApiProvider: val })
  if (val === 'gptsapi') {
      if (!gptsapiAspectRatioOptions.some(option => option.value === selectedAspectRatio.value)) {
        selectedAspectRatio.value = '9:16'
      }
    }
  if (!models.value.includes(selectedModel.value)) {
    selectedModel.value = models.value[0] || 'gpt-image-2'
  }
})

watch([selectedAspectRatio, selectedApiProvider, () => referenceImages.value.length], () => {
  if (!currentResolutions.value.some(option => option.value === selectedResolution.value)) {
    selectedResolution.value = currentResolutions.value[0]?.value || '1K'
  }
})

// 模型选择变化时保存到 localStorage
watch(selectedModel, (val) => {
  savePrefs({ selectedModel: val })
})

watch(
  models,
  (nextModels) => {
    if (!nextModels.includes(selectedModel.value)) {
      selectedModel.value = nextModels[0] || 'gpt-image-2'
    }
  },
  { deep: true }
)

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleDragOver = () => {
  isDragOver.value = true
}

const handleDragLeave = () => {
  isDragOver.value = false
}

const handleDrop = (event) => {
  isDragOver.value = false
  const files = Array.from(event.dataTransfer.files)
  processRefFiles(files)
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  processRefFiles(files)
  event.target.value = ''
}

// 上传参考图到文件 API 获取 HTTP URL
// 功能描述：
//     将 base64 Data URL 上传到 /api/files/upload-reference，
//     获取文件 API 返回的 HTTP URL，统一 Fal 和 OpenAI 双模式的参考图传递方式。
// 实现逻辑：
//     1. POST { image: "data:..." } 到后端上传接口
//     2. 成功返回 URL，失败返回 null（调用方保留 base64 作为 fallback）
const uploadReferenceImage = async (base64Url) => {
  try {
    const response = await api.post('/api/files/upload-reference', {
      image: base64Url
    })
    if (response?.status === 'success' && response?.url) {
      return response.url
    }
    console.warn('[ImageGenerator] 参考图上传失败:', response?.data?.message || '未知错误')
    return null
  } catch (err) {
    console.error('[ImageGenerator] 参考图上传异常:', err)
    return null
  }
}

const processRefFiles = (files) => {
  const validTypes = ['image/jpeg', 'image/png', 'image/webp']
  const validFiles = files.filter(file => {
    if (!validTypes.includes(file.type)) {
      console.error('Unsupported file type:', file.type)
      return false
    }
    if (file.size > maxRefSize) {
      console.error('File too large:', file.size)
      return false
    }
    return true
  })

  validFiles.forEach(file => {
    if (referenceImages.value.length >= maxRefImages.value) {
      return
    }
    const reader = new FileReader()
    reader.onload = async (e) => {
      const base64Url = e.target.result
      const imgEntry = {
        id: Date.now() + Math.random(),
        url: base64Url,
        name: file.name,
        size: file.size,
        type: file.type,
        uploading: true
      }
      referenceImages.value.push(imgEntry)

      const uploadedUrl = await uploadReferenceImage(base64Url)
      imgEntry.url = uploadedUrl || base64Url
      imgEntry.uploaded = !!uploadedUrl
      imgEntry.uploading = false
    }
    reader.readAsDataURL(file)

    uploadRefToMaterial(file)
  })
}

const uploadRefToMaterial = async (file) => {
  try {
    const formData = new FormData()
    formData.append('file', file)
    await fetch('/api/material/upload', {
      method: 'POST',
      body: formData
    })
  } catch (e) {
    console.error('上传参考图到素材库失败:', e)
  }
}

// 构造素材图片的 HTTP 访问 URL
// 功能描述：
//     将后端返回的素材数据转换为浏览器可访问的 HTTP URL
//     支持根目录图片和子文件夹图片两种路径格式
const getMaterialUrl = (material) => {
  if (material.folder) {
    return `/api/static/material/${encodeURIComponent(material.folder)}/${encodeURIComponent(material.filename)}`
  }
  return `/api/static/material/${encodeURIComponent(material.filename)}`
}

// 通过 HTTP URL 获取素材图片并转为 base64 Data URL
// 功能描述：
//     从后端静态服务获取图片 blob，通过 FileReader 转为 base64
//     失败时返回原始 HTTP URL 作为兜底，确保预览不会完全白屏
const fetchMaterialAsBase64 = async (url) => {
  try {
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const blob = await response.blob()
    return await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = () => reject(new Error('FileReader 读取失败'))
      reader.readAsDataURL(blob)
    })
  } catch (err) {
    console.error('[ImageGenerator] 素材转 base64 失败:', err)
    return url
  }
}

// 从素材库选择参考图
// 功能描述：
//     将选中的素材转为 base64 Data URL 后存入 referenceImages 列表
//     如果素材有 manual_url，直接使用该 URL 并标记为已上传
//     否则从本地获取后自动上传到文件 API 获取 HTTP URL
const handleMaterialSelect = async (materials) => {
  for (const material of materials) {
    if (referenceImages.value.length >= maxRefImages.value) {
      break
    }

    if (material.manual_url) {
      // 优先使用手动填写的 URL，无需上传
      const imgEntry = {
        id: material.id || Date.now() + Math.random(),
        url: material.manual_url,
        name: material.name || material.filename,
        size: material.size || 0,
        type: 'image/png',
        uploaded: true,
        uploading: false
      }
      referenceImages.value.push(imgEntry)
    } else {
      // 没有 manual_url，走原有的获取+上传流程
      const materialUrl = getMaterialUrl(material)
      const base64Url = await fetchMaterialAsBase64(materialUrl)

      const imgEntry = {
        id: material.id || Date.now() + Math.random(),
        url: base64Url,
        name: material.name || material.filename,
        size: material.size || 0,
        type: 'image/png'
      }
      referenceImages.value.push(imgEntry)

      // 自动上传到文件 API 获取 HTTP URL
      const uploadedUrl = await uploadReferenceImage(base64Url)
      if (uploadedUrl) {
        imgEntry.url = uploadedUrl
        imgEntry.uploaded = true
      }
    }
  }
  showMaterialSelector.value = false
}

const handleRemoveRefImage = (index) => {
  referenceImages.value.splice(index, 1)
}

const handlePreviewRefImage = (img) => {
  previewRefImage.value = img
}

const handleGenerate = async () => {
  if (!canGenerate.value) {
    return
  }

  loading.value = true
    error.value = ''

    try {
      const payload = {
        api_provider: selectedApiProvider.value,
        prompt: prompt.value.trim(),
        poster_copy: optimizedPosterCopy.value,
        model: selectedModel.value,
        async: isAsync.value,
        aspectRatio: selectedAspectRatio.value,
        resolution: selectedResolution.value,
        image: referenceImages.value.length > 0
          ? referenceImages.value.map(img => img.url)
          : undefined
      }

      if (selectedApiProvider.value === 'fal') {
        payload.quality = selectedQuality.value
        payload.outputFormat = selectedOutputFormat.value
        payload.outputCompression = selectedOutputCompression.value
        payload.background = selectedBackground.value
        // Fal 模式：size 发送 {width, height} 对象格式
        const parts = resolvedSize.value.split('x')
        payload.size = parts.length === 2
          ? { width: parseInt(parts[0]), height: parseInt(parts[1]) }
          : resolvedSize.value
        payload.num_images = selectedNumImages.value
        if (selectedSeed.value > 0) {
          payload.seed = selectedSeed.value
        }
      } else if (selectedApiProvider.value === 'gptsapi') {
        payload.size = resolvedSize.value
      } else {
        payload.quality = selectedQuality.value
        payload.output_format = selectedOutputFormat.value
        payload.output_compression = selectedOutputCompression.value
        payload.background = selectedBackground.value
        payload.size = resolvedSize.value
        if (selectedNumImages.value > 1) {
          payload.n = selectedNumImages.value
        }
        if (selectedSeed.value > 0) {
          payload.seed = selectedSeed.value
        }
      }

      // 在 API 调用前通知父组件创建占位卡片
      const effectiveAsync = isAsync.value
      emit('generate-start', {
        payload: { ...payload },
        isAsync: effectiveAsync
      })

      const response = await generateImage(payload)

      emit('generate', {
        response,
        payload,
        isAsync: effectiveAsync
      })

      loading.value = false
    } catch (err) {
      const errorMessage = err.message || '生成失败，请重试'
      const rawResult = err?.response?.data?.raw_result || null
      error.value = errorMessage
      emit('error', { message: errorMessage, rawResult })
      loading.value = false
    }
}

const handleGenerateComplete = () => {
  loading.value = false
}

const handleGenerateError = (errorMessage) => {
  error.value = errorMessage
  loading.value = false
}

const handleOptimize = async () => {
  if (!prompt.value.trim() || optimizing.value) {
    return
  }

  if (!configStore.promptOptimize?.apiKey) {
    error.value = '请先在设置中配置优化提示词的API Key'
    return
  }

  originalPromptBeforeOptimize.value = prompt.value.trim()
  optimizedPosterCopy.value = ''
  optimizing.value = true
  error.value = ''

  try {
    const result = await optimizePrompt(prompt.value.trim())

    if (result.error) {
      originalPromptBeforeOptimize.value = ''
      optimizedPosterCopy.value = ''
      error.value = result.error
      return
    }

    if (result.optimized_prompt) {
      optimizedPosterCopy.value = originalPromptBeforeOptimize.value
      prompt.value = result.optimized_prompt
    }
  } catch (err) {
    originalPromptBeforeOptimize.value = ''
    optimizedPosterCopy.value = ''
    error.value = err.message || '优化失败，请重试'
  } finally {
    optimizing.value = false
  }
}

const handleRevertOptimize = () => {
  if (originalPromptBeforeOptimize.value) {
    prompt.value = originalPromptBeforeOptimize.value
    originalPromptBeforeOptimize.value = ''
    optimizedPosterCopy.value = ''
  }
}

const handleReset = () => {
  prompt.value = ''
  originalPromptBeforeOptimize.value = ''
  optimizedPosterCopy.value = ''
  selectedModel.value = models.value[0] || 'gpt-image-2'
  selectedApiProvider.value = 'openai'
  selectedAspectRatio.value = '9:16'
  selectedResolution.value = '2K'
  selectedNumImages.value = 1
  selectedQuality.value = 'auto'
  selectedOutputFormat.value = 'png'
  selectedBackground.value = 'auto'
  referenceImages.value = []
  error.value = ''
  savePrefs({ selectedApiProvider: 'openai', selectedModel: models.value[0] || 'gpt-image-2' })
  emit('reset')
}

const addReferenceImage = (imageData) => {
  if (!imageData || !imageData.url) {
    return
  }
  if (referenceImages.value.length >= maxRefImages.value) {
    return
  }
  referenceImages.value.push({
    id: imageData.id || Date.now() + Math.random(),
    url: imageData.url,
    name: imageData.name || '参考图',
    size: imageData.size || 0,
    type: imageData.type || 'image/png'
  })
}

defineExpose({
  handleGenerateComplete,
  handleGenerateError,
  setPrompt: (text) => {
    prompt.value = text
    originalPromptBeforeOptimize.value = ''
    optimizedPosterCopy.value = ''
  },
  addReferenceImage,
  addReferenceImages: (images) => {
    images.forEach(img => {
      addReferenceImage(img)
    })
  }
})
</script>
