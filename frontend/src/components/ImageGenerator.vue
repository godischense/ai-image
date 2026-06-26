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
              v-for="item in enabledPromptTransformButtons"
              :key="item.value"
              class="image-generator__prompt-transform-btn"
              :class="{ 'image-generator__prompt-transform-btn--loading': transformOptimizingMedia === item.value }"
              @click="handlePromptTransformOptimize(item.value)"
              :disabled="!prompt.trim() || optimizing || !!transformOptimizingMedia"
              :title="`${item.label}提示词改变`"
            >
              <svg v-if="transformOptimizingMedia === item.value" class="image-generator__spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="2" x2="12" y2="6"></line>
                <line x1="12" y1="18" x2="12" y2="22"></line>
                <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
                <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                <line x1="2" y1="12" x2="6" y2="12"></line>
                <line x1="18" y1="12" x2="22" y2="12"></line>
                <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
                <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
              </svg>
              <span>{{ transformOptimizingMedia === item.value ? '改变中...' : item.label }}</span>
            </button>
            <button
              class="image-generator__optimize-btn"
              :class="{ 'image-generator__optimize-btn--loading': optimizing }"
              @click="handleOptimize"
              :disabled="!prompt.trim() || optimizing || !!transformOptimizingMedia"
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

      <div class="image-generator__field image-generator__template-section">
        <div class="image-generator__template-header">
          <label class="image-generator__label">
            <svg class="image-generator__label-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5z"></path>
            </svg>
            模版
          </label>
          <div class="image-generator__template-actions">
            <span v-if="activeTemplateName" class="image-generator__template-active">{{ activeTemplateName }}</span>
            <button type="button" class="image-generator__reference-action-btn" @click="showTemplateDialog = true">
              模版库
            </button>
            <button
              v-if="activeTemplateName"
              type="button"
              class="image-generator__template-clear"
              @click="activeTemplateName = ''"
            >
              清除
            </button>
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

        <!-- 制作人选择器 - 独立一行；本地属性，不发送到生图请求，仅作为图片元数据保存到 images.creator -->
        <div class="image-generator__selector-row image-generator__selector-row--full">
          <div class="image-generator__selector">
            <label class="image-generator__label">制作人</label>
            <Select
              v-model="selectedCreator"
              :options="creatorOptions"
              :disabled="loading"
              placeholder="选择制作人"
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

          <div v-if="!isApiyiProvider || isApiyiGptImage2" class="image-generator__selector">
            <label class="image-generator__label">质量</label>
            <Select
              v-model="selectedQuality"
              :options="qualityOptions.map(q => ({ value: q.value, label: q.label }))"
              :disabled="loading"
            />
          </div>
        </div>

        <!-- 生成数量和随机种子 -->
        <div v-if="!isGptsapiProvider && !isApiyiProvider" class="image-generator__selector-row">
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

        <div v-if="!isGptsapiProvider && (!isApiyiProvider || isApiyiGptImage2)" class="image-generator__selector-row">
          <div class="image-generator__selector">
            <label class="image-generator__label">输出</label>
            <Select
              v-model="selectedOutputFormat"
              :options="outputFormats.map(f => ({ value: f.value, label: f.label }))"
              :disabled="loading"
            />
          </div>

          <div v-if="isApiyiGptImage2" class="image-generator__selector">
            <label class="image-generator__label">Moderation</label>
            <Select
              v-model="selectedModeration"
              :options="moderationOptions"
              :disabled="loading"
            />
          </div>

          <div v-else class="image-generator__selector">
            <label class="image-generator__label">背景</label>
            <Select
              v-model="selectedBackground"
              :options="backgroundOptions.map(b => ({ value: b.value, label: b.label }))"
              :disabled="loading"
            />
          </div>
        </div>

        <div
          v-if="(!isAsyncOnlyProvider || isApiyiGptImage2) && (selectedOutputFormat === 'jpeg' || selectedOutputFormat === 'webp')"
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
        <div v-if="isAsyncOnlyProvider" class="image-generator__meta-item">
          <span class="image-generator__meta-label">端点</span>
          <span class="image-generator__meta-value">{{ referenceImages.length > 0 ? '图生图' : '文生图' }}</span>
        </div>
        <div v-if="!isAsyncOnlyProvider" class="image-generator__meta-item">
          <span class="image-generator__meta-label">导出格式</span>
          <span class="image-generator__meta-value">{{ selectedOutputFormat.toUpperCase() }}</span>
        </div>
        <div v-if="!isAsyncOnlyProvider" class="image-generator__meta-item">
          <span class="image-generator__meta-label">清晰度</span>
          <span class="image-generator__meta-value">{{ selectedQualityLabel }}</span>
        </div>
        <div v-if="!isAsyncOnlyProvider" class="image-generator__meta-item">
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

    <div
      v-if="showPromptTransformSelector"
      class="image-generator__prompt-selector-backdrop"
      @click.self="closePromptTransformSelector"
    >
      <div class="image-generator__prompt-selector">
        <div class="image-generator__prompt-selector-header">
          <h3>{{ pendingPromptTransformMediaLabel }}提示词改变</h3>
          <button type="button" class="image-generator__prompt-selector-close" @click="closePromptTransformSelector">×</button>
        </div>
        <div class="image-generator__prompt-selector-list">
          <button
            v-for="item in pendingPromptTransformPrompts"
            :key="item.id"
            type="button"
            class="image-generator__prompt-selector-item"
            @click="confirmPromptTransformSelection(item.id)"
          >
            {{ item.name }}
          </button>
        </div>
      </div>
    </div>

    <MaterialSelector
      :show="showMaterialSelector"
      :multiple="true"
      :max-count="maxRefImages - referenceImages.length"
      @close="showMaterialSelector = false"
      @select="handleMaterialSelect"
    />

    <PromptTemplateDialog
      :show="showTemplateDialog"
      :aspect-ratio-options="templateAspectRatioOptions"
      :current-settings="currentTemplateSettings"
      @close="showTemplateDialog = false"
      @apply="handleApplyTemplate"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { generateImage, optimizePrompt, optimizePromptTransform, api } from '@/services/api'
import { useConfigStore } from '@/stores/configStore'
import ImagePreview from '@/components/ImagePreview.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import PromptTemplateDialog from '@/components/PromptTemplateDialog.vue'
import Select from '@/components/common/Select/Select.vue'
import { APIYI_ASPECT_RATIO_OPTIONS, APIYI_RESOLUTIONS, resolveApiyiSize } from '@/utils/apiyiOptions'
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
  { value: '9:21', width: 9, height: 21 },
  { value: 'wechat-cover', label: '公众号封面', width: 900, height: 383 }
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
  'wechat-cover': { '1k': '1456x624', '2k': '1456x624', '4k': '1456x624' },
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
const getDefaultQuality = (apiProvider) => apiProvider === 'fal' ? 'medium' : 'auto'

const outputFormats = [
  { value: 'png', label: 'PNG' },
  { value: 'jpeg', label: 'JPEG' },
  { value: 'webp', label: 'WebP' }
]

const backgroundOptions = [
  { value: 'auto', label: 'Auto' },
  { value: 'opaque', label: 'Opaque' },
  { value: 'transparent', label: 'Transparent' }
]

const moderationOptions = [
  { value: 'auto', label: 'Auto' },
  { value: 'low', label: 'Low' }
]

// Fal API 的生成数量选项
const numImageOptions = [
  { value: 1, label: '1' },
  { value: 2, label: '2' },
  { value: 3, label: '3' },
  { value: 4, label: '4' }
]

// 根据选择的 API 提供者返回对应的模型列表
// 选择 Fal 时使用 falModels，gptsapi/apiyi 走固定模型名（端口前置），其他使用 imageApi.imageModels
const models = computed(() => {
  if (selectedApiProvider.value === 'fal') {
    return Array.isArray(configStore.falApi?.falModels) && configStore.falApi.falModels.length > 0
      ? configStore.falApi.falModels
      : ['openai/gpt-image-2']
  }
  if (selectedApiProvider.value === 'gptsapi') {
    return ['gptsapi/gpt-image-2']
  }
  // APIYI 固定返回带前缀的模型名，便于后端识别 apiSource 与剥离前缀
  if (selectedApiProvider.value === 'apiyi') {
    const configuredModels = Array.isArray(configStore.apiyiApi?.imageModels) && configStore.apiyiApi.imageModels.length > 0
      ? configStore.apiyiApi.imageModels
      : ['gpt-image-2-vip', 'gpt-image-2']
    const mergedModels = Array.from(new Set([...configuredModels, 'gpt-image-2']))
    return mergedModels.map(model => model.startsWith('apiyi/') ? model : `apiyi/${model}`)
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

// 根据是否有对应 API Key 动态生成 API 提供者选项
// 仅在用户已配置 API Key 时才显示对应端口（避免空 Key 提交失败）
const apiProviderOptions = computed(() => {
  const options = [
    { value: 'openai', label: 'OpenAI 兼容' }
  ]
  const hasFalApiKey = configStore.falApi?.apiKey?.trim()
  if (hasFalApiKey) {
    options.push({ value: 'fal', label: 'Fal API' })
  }
  options.push({ value: 'gptsapi', label: 'GPTsAPI' })
  // APIYI：仅在配置了 API Key 时显示，与 Fal 同样的策略
  const hasApiyiApiKey = configStore.apiyiApi?.apiKey?.trim()
  if (hasApiyiApiKey) {
    options.push({ value: 'apiyi', label: 'APIYI' })
  }
  return options
})

const aspectRatioOptions = computed(() => {
  return aspectRatios.map((ratio) => ({
    value: ratio.value,
    label: ratio.label || ratio.value,
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
const selectedResolution = ref('1K')
const selectedOutputFormat = ref('png')
const selectedOutputCompression = ref(100)
const selectedModeration = ref('auto')
const selectedBackground = ref('auto')
const isAsync = ref(configStore.imageApi?.isAsync || false)
// 当前选择的 API 提供者（openai 或 fal），从 localStorage 恢复
const selectedApiProvider = ref(savedPrefs.selectedApiProvider || 'openai')
const selectedQuality = ref(getDefaultQuality(selectedApiProvider.value))
// Fal 模式下选中的生成数量
const selectedNumImages = ref(1)
// Fal 模式下随机种子（0=不使用固定种子）
const selectedSeed = ref(0)
// 制作人：本地属性，保存到 images.creator，不发送到生图 API
// 恢复顺序：localStorage.image_generator_prefs.creator -> 配置默认值 -> 空字符串
const selectedCreator = ref(savedPrefs.creator || '')
// 制作人下拉选项：从 configStore.creatorOptions.options 派生（设置页可配置）
const creatorOptions = computed(() => {
  const list = Array.isArray(configStore.creatorOptions?.options) ? configStore.creatorOptions.options : []
  return list.map((name) => ({ value: name, label: name }))
})
const loading = ref(false)
const optimizing = ref(false)
const transformOptimizingMedia = ref('')
const showPromptTransformSelector = ref(false)
const pendingPromptTransformMedia = ref('')
const originalPromptBeforeOptimize = ref('')
const optimizedPosterCopy = ref('')
const error = ref('')
const referenceImages = ref([])
const isDragOver = ref(false)
const fileInputRef = ref(null)
const previewRefImage = ref(null)
const showMaterialSelector = ref(false)
const showTemplateDialog = ref(false)
const activeTemplateName = ref('')
const maxRefSize = 10 * 1024 * 1024

const isGptsapiProvider = computed(() => selectedApiProvider.value === 'gptsapi')
const isApiyiProvider = computed(() => selectedApiProvider.value === 'apiyi')
const isApiyiGptImage2 = computed(() => selectedApiProvider.value === 'apiyi' && selectedModel.value.replace('apiyi/', '') === 'gpt-image-2')
const isAsyncOnlyProvider = computed(() => isGptsapiProvider.value || isApiyiProvider.value || selectedApiProvider.value === 'fal')
const usesCompactSizeOptions = computed(() => isGptsapiProvider.value || (isApiyiProvider.value && !isApiyiGptImage2.value))
const currentAspectRatioOptions = computed(() => {
  if (isApiyiProvider.value && !isApiyiGptImage2.value) return APIYI_ASPECT_RATIO_OPTIONS
  if (usesCompactSizeOptions.value) return gptsapiAspectRatioOptions
  return [...aspectRatioOptions.value, { value: 'fullscreen', label: '全屏' }]
})
const currentResolutions = computed(() => {
  if (isApiyiProvider.value) {
    if (isApiyiGptImage2.value) return resolutions
    return APIYI_RESOLUTIONS
  }
  if (!usesCompactSizeOptions.value) {
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
const templateAspectRatioOptions = computed(() => {
  const merged = [...aspectRatioOptions.value, { value: 'fullscreen', label: '全屏' }]
  return merged.map(item => ({ value: item.value, label: item.label || item.value }))
})
const currentTemplateSettings = computed(() => ({
  apiProvider: selectedApiProvider.value,
  model: selectedModel.value,
  aspectRatio: selectedAspectRatio.value,
  resolution: selectedResolution.value,
  quality: selectedQuality.value,
  outputFormat: selectedOutputFormat.value,
  outputCompression: selectedOutputCompression.value,
  background: selectedBackground.value,
  moderation: selectedModeration.value
}))

const promptTransformMediaOptions = [
  { value: 'officialAccount', label: '公众号' },
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'shortVideo', label: '短视频' }
]

const getPromptTransformPrompts = (item) => {
  const prompts = Array.isArray(item?.systemPrompts) ? item.systemPrompts : []
  const normalizedPrompts = prompts
    .map((promptItem, index) => ({
      id: promptItem?.id || `prompt_${index}`,
      name: promptItem?.name || `提示词 ${index + 1}`,
      content: promptItem?.content || ''
    }))
    .filter(promptItem => promptItem.content.trim())

  if (normalizedPrompts.length === 0 && item?.systemPrompt?.trim()) {
    return [{
      id: 'default',
      name: '默认提示词',
      content: item.systemPrompt.trim()
    }]
  }

  return normalizedPrompts
}

const isPromptTransformComplete = (item) => {
  return Boolean(
    item?.providerName?.trim() &&
    item?.baseUrl?.trim() &&
    item?.apiKey?.trim() &&
    item?.model?.trim() &&
    getPromptTransformPrompts(item).length > 0
  )
}

const enabledPromptTransformButtons = computed(() => {
  const items = configStore.promptTransform?.items || {}
  return promptTransformMediaOptions.filter((media) => isPromptTransformComplete(items[media.value]))
})

const pendingPromptTransformItem = computed(() => {
  const items = configStore.promptTransform?.items || {}
  return items[pendingPromptTransformMedia.value] || null
})

const pendingPromptTransformPrompts = computed(() => getPromptTransformPrompts(pendingPromptTransformItem.value))

const pendingPromptTransformMediaLabel = computed(() => {
  return promptTransformMediaOptions.find(item => item.value === pendingPromptTransformMedia.value)?.label || ''
})

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
  if (isApiyiProvider.value && !isApiyiGptImage2.value) {
    return resolveApiyiSize(selectedAspectRatio.value, selectedResolution.value)
  }

  if (isGptsapiProvider.value && selectedAspectRatio.value === 'auto') {
    return 'auto'
  }

  const sizeByAspect = sizeMap[selectedAspectRatio.value]
  if (!sizeByAspect) {
    return ''
  }

  const resolutionKey = resolutions.find(r => r.value === selectedResolution.value)?.key || '1k'
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
// APIYI 也需要强制将 isAsync 置为 true（接口文档视为异步执行，统一走任务卡片路径）
watch(selectedApiProvider, (val) => {
  savePrefs({ selectedApiProvider: val })
  selectedQuality.value = getDefaultQuality(val)
  if (val === 'apiyi') {
      if (!APIYI_ASPECT_RATIO_OPTIONS.some(option => option.value === selectedAspectRatio.value)) {
        selectedAspectRatio.value = '9:16'
      }
    }
  if (val === 'gptsapi') {
      if (!gptsapiAspectRatioOptions.some(option => option.value === selectedAspectRatio.value)) {
        selectedAspectRatio.value = '9:16'
      }
    }
  if (val === 'apiyi') {
    // APIYI 90-150s 同步阻塞，必须走异步任务卡，强制开启
    isAsync.value = true
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

// 制作人变化时保存到 localStorage（避免每次都重写整个 prefs 对象）
watch(selectedCreator, (val) => {
  savePrefs({ creator: val || '' })
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
    // 记录 push 后的下标，便于后续通过响应式 Proxy 更新
    // 避免直接修改原始对象导致 Vue 3 响应式失效，spinner 一直转
    const placeholderIndex = referenceImages.value.length
    const placeholderId = Date.now() + Math.random()
    reader.onload = async (e) => {
      const base64Url = e.target.result
      const imgEntry = {
        id: placeholderId,
        url: base64Url,
        name: file.name,
        size: file.size,
        type: file.type,
        uploading: true
      }
      // 仅当占位位下标仍属于当前列表时才 push，防止超过上限或被移除后重复插入
      if (placeholderIndex < maxRefImages.value && referenceImages.value.length === placeholderIndex) {
        referenceImages.value.push(imgEntry)
      }

      const uploadedUrl = await uploadReferenceImage(base64Url)

      // 通过数组下标访问响应式 Proxy，确保 uploading/url 等状态变更触发视图更新
      const target = referenceImages.value[placeholderIndex]
      if (target && target.id === placeholderId) {
        target.url = uploadedUrl || base64Url
        target.uploaded = !!uploadedUrl
        target.uploading = false
      }
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

const setIfOptionExists = (options, nextValue, targetRef) => {
  if (!nextValue) return
  if (options.some(item => item.value === nextValue)) {
    targetRef.value = nextValue
  }
}

const handleApplyTemplate = async (template) => {
  if (!template) return
  if (template.prompt) {
    prompt.value = template.prompt
    originalPromptBeforeOptimize.value = ''
    optimizedPosterCopy.value = ''
  }
  if (template.apiProvider && apiProviderOptions.value.some(item => item.value === template.apiProvider)) {
    selectedApiProvider.value = template.apiProvider
  }
  await Promise.resolve()
  if (template.model && models.value.includes(template.model)) {
    selectedModel.value = template.model
  }
  setIfOptionExists(currentAspectRatioOptions.value, template.aspectRatio, selectedAspectRatio)
  setIfOptionExists(currentResolutions.value, template.resolution, selectedResolution)
  if (template.quality && qualityOptions.some(item => item.value === template.quality)) {
    selectedQuality.value = template.quality
  }
  if (template.outputFormat && outputFormats.some(item => item.value === template.outputFormat)) {
    selectedOutputFormat.value = template.outputFormat
  }
  if (Number.isFinite(Number(template.outputCompression))) {
    selectedOutputCompression.value = Math.max(0, Math.min(100, Number(template.outputCompression)))
  }
  if (template.background && backgroundOptions.some(item => item.value === template.background)) {
    selectedBackground.value = template.background
  }
  if (template.moderation && moderationOptions.some(item => item.value === template.moderation)) {
    selectedModeration.value = template.moderation
  }
  const refs = Array.isArray(template.referenceImages) ? template.referenceImages : []
  for (const refImage of refs) {
    if (referenceImages.value.length >= maxRefImages.value) break
    await addReferenceImage({
      id: refImage.id || `${template.id}_${refImage.url}`,
      url: refImage.url,
      name: refImage.name || '模版参考图',
      size: refImage.size || 0,
      type: refImage.type || 'image/png',
      base64: refImage.url?.startsWith('data:') ? refImage.url : ''
    })
  }
  activeTemplateName.value = template.name || ''
  showTemplateDialog.value = false
}

const handleGenerate = async () => {
  if (!canGenerate.value) {
    return
  }

  loading.value = true
    error.value = ''

    try {
      // APIYI 90-150s 同步阻塞：无论用户是否开启 isAsync，提交时都强制走异步任务卡
      // 这样后端 ThreadPoolExecutor 才能并发处理多个任务，提交后立即返回 task_id
      const effectiveAsyncFlag = selectedApiProvider.value === 'apiyi' ? true : isAsync.value
      const payload = {
        api_provider: selectedApiProvider.value,
        prompt: prompt.value.trim(),
        poster_copy: optimizedPosterCopy.value,
        model: selectedModel.value,
        async: effectiveAsyncFlag,
        // 制作人：随生图请求一起上传到后端，由后端写入 images.creator 字段；
        // 父组件仍可从 emit('generate-start'/'generate') 中拿到 creator 用于占位卡片显示
        creator: (selectedCreator.value || '').trim(),
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
        payload.aspectRatio = selectedAspectRatio.value
        payload.resolution = selectedResolution.value
        payload.size = resolvedSize.value
      } else if (selectedApiProvider.value === 'apiyi') {
        // APIYI：size 透传 'auto' 或 'WxH' 字符串（30 档之一），不发 quality/n/num_images/seed
        payload.size = resolvedSize.value
        if (isApiyiGptImage2.value) {
          payload.quality = selectedQuality.value
          payload.output_format = selectedOutputFormat.value
          payload.background = 'auto'
          payload.moderation = selectedModeration.value
          if (selectedOutputFormat.value === 'jpeg' || selectedOutputFormat.value === 'webp') {
            payload.output_compression = selectedOutputCompression.value
          }
        }
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
      // 注意：creator 已经包含在 payload 中上传到后端；同时这里再透传一次给父组件，
      // 让 DirectCreateView 的占位卡片在等待后端响应期间也能展示正确的制作人
      emit('generate-start', {
        payload: { ...payload },
        isAsync: effectiveAsyncFlag,
        creator: selectedCreator.value
      })

      const response = await generateImage(payload)

      emit('generate', {
        response,
        payload,
        isAsync: effectiveAsyncFlag,
        creator: selectedCreator.value
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

const handlePromptTransformOptimize = async (mediaType) => {
  if (!prompt.value.trim() || optimizing.value || transformOptimizingMedia.value) {
    return
  }

  const item = configStore.promptTransform?.items?.[mediaType]
  const prompts = getPromptTransformPrompts(item)
  if (prompts.length === 0) {
    error.value = '请先在设置中配置该平台的系统提示词'
    return
  }
  if (prompts.length > 1) {
    pendingPromptTransformMedia.value = mediaType
    showPromptTransformSelector.value = true
    return
  }

  await executePromptTransformOptimize(mediaType, prompts[0].id)
}

const executePromptTransformOptimize = async (mediaType, systemPromptId = '') => {
  if (!prompt.value.trim() || optimizing.value || transformOptimizingMedia.value) {
    return
  }

  originalPromptBeforeOptimize.value = prompt.value.trim()
  optimizedPosterCopy.value = ''
  transformOptimizingMedia.value = mediaType
  error.value = ''

  try {
    const result = await optimizePromptTransform(prompt.value.trim(), mediaType, systemPromptId)

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
    error.value = err.message || '提示词改变失败，请重试'
  } finally {
    transformOptimizingMedia.value = ''
  }
}

const closePromptTransformSelector = () => {
  showPromptTransformSelector.value = false
  pendingPromptTransformMedia.value = ''
}

const confirmPromptTransformSelection = async (systemPromptId) => {
  const mediaType = pendingPromptTransformMedia.value
  closePromptTransformSelector()
  await executePromptTransformOptimize(mediaType, systemPromptId)
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
  selectedResolution.value = '1K'
  selectedNumImages.value = 1
  selectedQuality.value = 'auto'
  selectedOutputFormat.value = 'png'
  selectedModeration.value = 'auto'
  selectedBackground.value = 'auto'
  referenceImages.value = []
  activeTemplateName.value = ''
  error.value = ''
  savePrefs({ selectedApiProvider: 'openai', selectedModel: models.value[0] || 'gpt-image-2' })
  emit('reset')
}

// 添加单张参考图，触发上传到文件 API 获取 HTTP URL 后再插入列表
// 功能描述：
//     接收任意格式的图片 URL（base64 Data URL、HTTP/HTTPS 远程链接、/api/... 本地代理路径），
//     自动转 base64 并上传到 /api/files/upload-reference 获取可被外部 AI API 访问的 HTTP URL，
//     上传期间显示 uploading 状态，避免用户立即点击"开始生成"时把相对路径传给后端。
// 实现逻辑：
//     1. 校验入参，重复 id 去重，达到上限直接返回
//     2. 立刻 push uploading=true 的占位项，保证参考图列表立即可见
//     3. base64 直接走 uploadReferenceImage；非 base64 走 fetchMaterialAsBase64 转 base64
//     4. 上传成功：更新 url 为返回的 HTTP URL，标记 uploaded=true
//     5. 上传失败/异常：保留原 URL，标记 uploaded=false，uploading=false
//     6. 失败时记录错误日志但不影响其他参考图
const addReferenceImage = async (imageData) => {
  if (!imageData || !imageData.url) {
    return
  }
  if (referenceImages.value.length >= maxRefImages.value) {
    return
  }

  const newId = imageData.id || Date.now() + Math.random()
  // 去重：相同 id 的参考图已存在则跳过，避免重复上传
  if (referenceImages.value.some((img) => img.id === newId)) {
    return
  }

  const sourceUrl = imageData.url
  // 优先复用调用方声明的 base64 内容；否则按 URL 走转码 + 上传流程
  const initialBase64 = typeof imageData.base64 === 'string' && imageData.base64.startsWith('data:')
    ? imageData.base64
    : ''

  // 立刻插入占位项：uploading=true 让用户看到加载状态，url 用原始 URL 作为兜底预览
  const refEntry = {
    id: newId,
    url: sourceUrl,
    name: imageData.name || '参考图',
    size: imageData.size || 0,
    type: imageData.type || 'image/png',
    uploading: true,
    uploaded: false,
    uploadError: ''
  }
  referenceImages.value.push(refEntry)

  try {
    let base64ForUpload = initialBase64
    if (!base64ForUpload) {
      base64ForUpload = await fetchMaterialAsBase64(sourceUrl)
    }

    // 转码失败兜底：保留原 URL 结束 uploading 状态，避免列表一直转圈
    if (!base64ForUpload || !base64ForUpload.startsWith('data:')) {
      refEntry.uploading = false
      refEntry.uploaded = false
      refEntry.uploadError = '图片转码失败'
      console.warn('[ImageGenerator] 编辑图片转 base64 失败，使用原 URL:', sourceUrl)
      return
    }

    const uploadedUrl = await uploadReferenceImage(base64ForUpload)
    if (uploadedUrl) {
      refEntry.url = uploadedUrl
      refEntry.uploaded = true
    } else {
      // 上传接口返回 null：保留原 URL，标记未上传成功，让用户能看出状态
      refEntry.uploaded = false
      refEntry.uploadError = '上传到文件服务失败，将使用原 URL 提交'
      console.warn('[ImageGenerator] 编辑图片上传失败，使用原 URL:', sourceUrl)
    }
  } catch (err) {
    refEntry.uploaded = false
    refEntry.uploadError = err?.message || '上传异常'
    console.error('[ImageGenerator] 编辑参考图上传异常:', err)
  } finally {
    refEntry.uploading = false
  }
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
  addReferenceImages: async (images) => {
    // 顺序等待：每张图的上传是独立的异步流程，串行执行避免并发抢占 maxRefImages 上限
    for (const img of images) {
      await addReferenceImage(img)
    }
  }
})
</script>

