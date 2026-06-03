<!--
  Topaz Gigapixel AI 图片放大页面
  父组件：负责所有状态管理、业务逻辑、与后端 API 通信
  子组件：仅接收 props、emit 事件
-->
<template>
  <div class="gigapixel-view">
    <!-- 顶部状态横幅 -->
    <div
      v-if="!checking && !available"
      class="gigapixel-view__banner gigapixel-view__banner--warning"
    >
      <span class="gigapixel-view__banner-icon">⚠️</span>
      <div class="gigapixel-view__banner-text">
        <strong>未检测到 Topaz Gigapixel AI</strong>
        <p>{{ availableMessage || '请到「设置」->「Topaz Gigapixel AI」配置 gigapixel.exe 路径，并确保已安装 Topaz Gigapixel AI ≥ 7.3.0' }}</p>
      </div>
    </div>

    <div class="gigapixel-view__content">
      <!-- 左侧：参数面板 -->
      <div class="gigapixel-view__panel">
        <!-- 1. 图片源卡片 -->
        <div class="gigapixel-view__card">
          <h3 class="gigapixel-view__card-title">
            <span>📁 选择图片</span>
            <span v-if="selectedImage" class="gigapixel-view__card-title-hint">已选 1 / 1</span>
          </h3>

          <!-- 已选图预览 -->
          <div v-if="selectedImage" class="gigapixel-view__selected">
            <div class="gigapixel-view__selected-thumb-wrap">
              <img
                :src="selectedImage.uploaded_preview_url || selectedImage.thumbnail || selectedImage.url"
                :alt="selectedImage.title || '已选图片'"
                class="gigapixel-view__selected-thumb"
                @click="handlePreviewSelected"
              />
            </div>
            <div class="gigapixel-view__selected-info">
              <div class="gigapixel-view__selected-name" :title="selectedImage.title || selectedImage.prompt">
                {{ selectedImage.title || selectedImage.prompt || '已选图片' }}
              </div>
              <div class="gigapixel-view__selected-actions">
                <button class="gigapixel-view__btn gigapixel-view__btn--small" type="button" @click="showImageSelector = true">
                  🔁 更换
                </button>
                <button class="gigapixel-view__btn gigapixel-view__btn--small gigapixel-view__btn--danger-text" type="button" @click="clearSelected">
                  ✕ 移除
                </button>
              </div>
            </div>
          </div>

          <!-- 未选图：显示两个选择入口 -->
          <div v-else class="gigapixel-view__picker">
            <div
              class="gigapixel-view__picker-zone"
              :class="{ 'gigapixel-view__picker-zone--dragover': isUploadDragOver, 'gigapixel-view__picker-zone--loading': uploading }"
              @dragenter.prevent="isUploadDragOver = true"
              @dragover.prevent="isUploadDragOver = true"
              @dragleave.prevent="isUploadDragOver = false"
              @drop.prevent="handleUploadDrop"
              @click="uploading ? undefined : triggerUpload()"
            >
              <div class="gigapixel-view__picker-icon">
                <svg v-if="uploading" class="gigapixel-view__spinner" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.25" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <div class="gigapixel-view__picker-text">{{ uploading ? '上传中...' : '点击或拖拽上传本地图片' }}</div>
              <div class="gigapixel-view__picker-hint">支持 JPG / PNG / WebP / TIFF，单张最大 50MB</div>
              <input
                ref="uploadInputRef"
                type="file"
                accept="image/jpeg,image/png,image/webp,image/tiff"
                class="gigapixel-view__upload-input"
                :disabled="uploading"
                @change="handleUploadChange"
              />
            </div>

            <div class="gigapixel-view__picker-divider">
              <span>或</span>
            </div>

            <button
              type="button"
              class="gigapixel-view__picker-btn"
              @click="showImageSelector = true"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
              </svg>
              <span>从图片库选择</span>
            </button>
          </div>
        </div>

        <!-- 2. 放大参数卡片 -->
        <div class="gigapixel-view__card">
          <h3 class="gigapixel-view__card-title">
            <span>⚙️ 放大参数</span>
            <button
              type="button"
              class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--global"
              @click="toggleAllDescVisibility"
              :title="allDescVisible() ? '隐藏全部参数说明' : '显示全部参数说明'"
            >
              {{ allDescVisible() ? '🔽 隐藏说明' : '▶ 显示说明' }}
            </button>
          </h3>

          <!-- 高级参数概览说明 -->
          <div v-if="getDescVisibility().intro" class="gigapixel-view__params-intro">
            <div class="gigapixel-view__params-intro-header">
              <strong>📖 参数说明（必读）</strong>
              <button
                type="button"
                class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--small"
                @click.stop="toggleDescVisibility('intro')"
                :title="getDescVisibility().intro ? '隐藏此说明' : '显示此说明'"
              >
                {{ getDescVisibility().intro ? '🔽' : '▶' }}
              </button>
            </div>
            <ul>
              <li><b>缩放倍率</b> 决定输出图分辨率；倍率越大越慢、显存占用越高。</li>
              <li><b>AI 模型</b> 决定 Topaz 用哪种"脑回路"补图；不同模型擅长场景不同，详见下方模型说明。</li>
              <li><b>详细参数</b> 默认关闭，沿用 Topaz 官方推荐值；开启后可微调锐化、降噪、压缩修复、细节保留等。</li>
              <li><b>关键约定：</b>参数值 <code>0</code> 等同于"不传给 gigapixel.exe 命令行，由 Topaz 内部决定"。所以如果你不想要某个效果，把它拉到 0 即可。</li>
            </ul>
            <div style="margin-top: 6px; padding-top: 6px; border-top: 1px dashed rgba(99,102,241,0.2); font-size: 10px; color: #6366f1;">
              <b>📋 官方默认速查：</b>scale=2.0 / model=Standard / sharpen=1 / denoise=1 / compression=67 / fr=50 / pre_downscaling=75
            </div>
          </div>

          <!-- 缩放倍率 -->
          <div class="gigapixel-view__field">
            <div class="gigapixel-view__label-row">
              <label class="gigapixel-view__label">📏 缩放倍率 (Scale)</label>
              <span class="gigapixel-view__value-tag">{{ form.scale }}x</span>
              <button
                type="button"
                class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--inline"
                @click="toggleDescVisibility('scale')"
                :title="getDescVisibility().scale ? '隐藏说明' : '显示说明'"
              >
                {{ getDescVisibility().scale ? '🔽' : '▶' }}
              </button>
            </div>
            <input
              v-model.number="form.scale"
              type="range"
              min="1"
              max="16"
              step="0.1"
              class="gigapixel-view__range"
            />
            <div v-if="getDescVisibility().scale" class="gigapixel-view__field-hint">
              <b>作用：</b>最终输出分辨率 = 原图尺寸 × 倍率。例如 1024×1024 图 ×4 = 4096×4096。
              <br><b>建议：</b>网络/手机端 2x 足够；印刷/大屏展示 4x；老照片/小图标可尝试 6x-8x（更高易失真且慢）。
              <br><b>官方默认：</b>2.0
            </div>
          </div>

          <!-- 模型 -->
          <div class="gigapixel-view__field">
            <div class="gigapixel-view__label-row">
              <label class="gigapixel-view__label">🧠 AI 模型 (Model)</label>
              <button
                type="button"
                class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--inline"
                @click="toggleDescVisibility('model')"
                :title="getDescVisibility().model ? '隐藏说明' : '显示说明'"
              >
                {{ getDescVisibility().model ? '🔽' : '▶' }}
              </button>
            </div>
            <div class="gigapixel-view__model-select">
              <button
                v-for="m in MODEL_OPTIONS"
                :key="m"
                type="button"
                class="gigapixel-view__model-chip"
                :class="{ 'gigapixel-view__model-chip--active': form.model === m }"
                @click="form.model = m"
                :title="MODEL_DESCRIPTIONS[m]"
              >
                {{ m }}
              </button>
            </div>
            <div v-if="getDescVisibility().model" class="gigapixel-view__field-hint gigapixel-view__field-hint--strong">
              <b>当前选中：</b>{{ form.model }} —— {{ MODEL_DESCRIPTIONS[form.model] }}
              <br><b>切换提示：</b>不确定选哪个时，先用 <b>Standard</b> 试一张，效果不满意再换。
            </div>
          </div>

          <!-- 启用详细参数开关 -->
          <div class="gigapixel-view__field gigapixel-view__field--toggle">
            <label class="gigapixel-view__toggle">
              <input v-model="form.enabled" type="checkbox" />
              <span class="gigapixel-view__toggle-slider"></span>
              <span class="gigapixel-view__toggle-text">
                启用详细参数
                <span class="gigapixel-view__toggle-sub">关闭时仅传倍率，使用 Topaz 默认参数（推荐新手）；开启后可微调下方 4-5 个进阶滑块</span>
              </span>
            </label>
          </div>

          <!-- 详细参数滑块 -->
          <template v-if="form.enabled">
            <div class="gigapixel-view__field-hint" style="margin-bottom: 12px;">
              💡 <b>进阶玩法：</b>下面 4 个参数互相影响，一般只需要微调 1-2 个。数值过高会产生"塑料感"或"油画感"，建议每次只改 10-20，对比效果。
            </div>

            <div class="gigapixel-view__field">
              <div class="gigapixel-view__label-row">
                <label class="gigapixel-view__label">🔪 锐化 (Sharpen)</label>
                <span class="gigapixel-view__value-tag">{{ form.sharpen }}</span>
                <button
                  type="button"
                  class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--inline"
                  @click="toggleDescVisibility('sharpen')"
                  :title="getDescVisibility().sharpen ? '隐藏说明' : '显示说明'"
                >
                  {{ getDescVisibility().sharpen ? '🔽' : '▶' }}
                </button>
              </div>
              <input
                v-model.number="form.sharpen"
                type="range"
                min="0"
                max="100"
                step="1"
                class="gigapixel-view__range"
              />
              <div v-if="getDescVisibility().sharpen" class="gigapixel-view__field-hint">
                <b>作用：</b>增强边缘与细节清晰度，让放大后的图看起来更"锐利"。
                <br><b>取值：</b>0=不传该参数（用 Topaz 内部默认）；值越高越锐利，过高会引入噪点和"光晕"。
                <br><b>建议：</b>人像 1-30（太高皮肤失真）；风光 30-60；文字/UI 截图 50-80。
                <br><b>官方默认：</b>1
              </div>
            </div>

            <div class="gigapixel-view__field">
              <div class="gigapixel-view__label-row">
                <label class="gigapixel-view__label">🔇 降噪 (Denoise)</label>
                <span class="gigapixel-view__value-tag">{{ form.denoise }}</span>
                <button
                  type="button"
                  class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--inline"
                  @click="toggleDescVisibility('denoise')"
                  :title="getDescVisibility().denoise ? '隐藏说明' : '显示说明'"
                >
                  {{ getDescVisibility().denoise ? '🔽' : '▶' }}
                </button>
              </div>
              <input
                v-model.number="form.denoise"
                type="range"
                min="0"
                max="100"
                step="1"
                class="gigapixel-view__range"
              />
              <div v-if="getDescVisibility().denoise" class="gigapixel-view__field-hint">
                <b>作用：</b>抑制高 ISO、夜景、暗光环境下产生的颗粒与彩色噪点。
                <br><b>取值：</b>0=不传该参数（用 Topaz 内部默认）；值越高画面越"干净"，但会损失细密纹理（如毛发、织物）。
                <br><b>建议：</b>夜景/高 ISO 照片 30-60；正常光照 1-20；二次元/插画保持 0-1（避免破坏线条）。
                <br><b>官方默认：</b>1
              </div>
            </div>

            <div class="gigapixel-view__field">
              <div class="gigapixel-view__label-row">
                <label class="gigapixel-view__label">🗜️ 压缩修复 (Compression)</label>
                <span class="gigapixel-view__value-tag">{{ form.compression }}</span>
                <button
                  type="button"
                  class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--inline"
                  @click="toggleDescVisibility('compression')"
                  :title="getDescVisibility().compression ? '隐藏说明' : '显示说明'"
                >
                  {{ getDescVisibility().compression ? '🔽' : '▶' }}
                </button>
              </div>
              <input
                v-model.number="form.compression"
                type="range"
                min="0"
                max="100"
                step="1"
                class="gigapixel-view__range"
              />
              <div v-if="getDescVisibility().compression" class="gigapixel-view__field-hint">
                <b>作用：</b>修复 JPEG 多次保存产生的块状伪影、马赛克、振铃效应（俗称"蚊子噪"）。
                <br><b>取值：</b>0=不传该参数（用 Topaz 内部默认）；值越高修复越强；只在源图有明显压缩痕迹时才需要调高。
                <br><b>建议：</b>默认 67 适合大多数情况；社媒下载图可提到 80-100；原始 RAW/PNG 保持 0-30。
                <br><b>官方默认：</b>67
              </div>
            </div>

            <div class="gigapixel-view__field">
              <div class="gigapixel-view__label-row">
                <label class="gigapixel-view__label">🔍 细节保留 (Fine Detail)</label>
                <span class="gigapixel-view__value-tag">{{ form.fr }}</span>
                <button
                  type="button"
                  class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--inline"
                  @click="toggleDescVisibility('fr')"
                  :title="getDescVisibility().fr ? '隐藏说明' : '显示说明'"
                >
                  {{ getDescVisibility().fr ? '🔽' : '▶' }}
                </button>
              </div>
              <input
                v-model.number="form.fr"
                type="range"
                min="0"
                max="100"
                step="1"
                class="gigapixel-view__range"
              />
              <div v-if="getDescVisibility().fr" class="gigapixel-view__field-hint">
                <b>作用：</b>控制在生成新细节时"创造"vs"保留"原图细节的平衡。
                <br><b>取值：</b>0=不传该参数（用 Topaz 内部默认）；值越高越忠实于原图；值越低 Topaz 越会"脑补"新细节（可能出现原本不存在的纹理）。
                <br><b>建议：</b>证件照/纪实摄影 70-100（防止 AI 脑补）；老照片修复 30-50（让 AI 脑补细节）；插画 50-70。
                <br><b>官方默认：</b>50
              </div>
            </div>

            <div v-if="form.model === 'Recover'" class="gigapixel-view__field gigapixel-view__field--highlight">
              <div class="gigapixel-view__label-row">
                <label class="gigapixel-view__label">
                  ♻️ 预降采样 (Pre-Downscaling)
                  <span class="gigapixel-view__label-badge">仅 Recover</span>
                </label>
                <span class="gigapixel-view__value-tag">{{ form.pre_downscaling }}</span>
                <button
                  type="button"
                  class="gigapixel-view__desc-toggle gigapixel-view__desc-toggle--inline"
                  @click="toggleDescVisibility('pre_downscaling')"
                  :title="getDescVisibility().pre_downscaling ? '隐藏说明' : '显示说明'"
                >
                  {{ getDescVisibility().pre_downscaling ? '🔽' : '▶' }}
                </button>
              </div>
              <input
                v-model.number="form.pre_downscaling"
                type="range"
                min="50"
                max="100"
                step="1"
                class="gigapixel-view__range"
              />
              <div v-if="getDescVisibility().pre_downscaling" class="gigapixel-view__field-hint">
                <b>作用：</b>Recover 模型专用 —— 先把图缩小到原尺寸的 {{ form.pre_downscaling }}% 再放大，避免恢复时引入伪影。
                <br><b>取值：</b>100=不降采样（适合原图较清晰的场景）；80-90=轻微降采样（推荐默认）；50-70=重度降采样（极差画质抢救）。
                <br><b>建议：</b>模糊严重的图 75 左右；轻度模糊 85-95；只有噪点没模糊保持 100。
                <br><b>官方默认：</b>75
              </div>
            </div>
          </template>

          <!-- 提交按钮 -->
          <button
            class="gigapixel-view__submit-btn"
            :disabled="!canSubmit"
            @click="handleSubmit"
          >
            <span v-if="submitting">⏳ 提交中...</span>
            <span v-else>🚀 开始放大</span>
          </button>
          <p v-if="!available" class="gigapixel-view__hint-error">⚠️ Topaz Gigapixel AI 不可用，无法提交</p>
          <p v-else-if="!selectedImage" class="gigapixel-view__hint">请先选择一张图片（图片库或本地上传）</p>
        </div>
      </div>

      <!-- 右侧：任务区 -->
      <div class="gigapixel-view__tasks">
        <!-- 当前任务进度卡片 -->
        <div v-if="currentTask" class="gigapixel-view__card gigapixel-view__card--task-current">
          <h3 class="gigapixel-view__card-title">
            <span>📊 当前任务</span>
            <span class="gigapixel-view__status" :class="`gigapixel-view__status--${currentTask.status?.toLowerCase()}`">
              {{ statusLabel(currentTask.status) }}
            </span>
          </h3>
          <div class="gigapixel-view__task-info">
            <div class="gigapixel-view__task-row">
              <span class="gigapixel-view__task-row-label">任务 ID</span>
              <code class="gigapixel-view__task-row-value">{{ currentTask.id }}</code>
            </div>
            <div class="gigapixel-view__task-row">
              <span class="gigapixel-view__task-row-label">进度</span>
              <div class="gigapixel-view__progress-bar">
                <div class="gigapixel-view__progress-fill" :style="{ width: progressPercent + '%' }"></div>
              </div>
              <span class="gigapixel-view__progress-text">{{ currentTask.progress || '0%' }}</span>
            </div>
            <div v-if="currentTask.fail_reason" class="gigapixel-view__task-row gigapixel-view__task-row--error">
              <span class="gigapixel-view__task-row-label">⚠️ 错误</span>
              <span class="gigapixel-view__error-text">{{ currentTask.fail_reason }}</span>
            </div>
            <div v-if="currentImage?.url" class="gigapixel-view__task-row">
              <span class="gigapixel-view__task-row-label">结果</span>
              <a :href="currentImage.url" target="_blank" class="gigapixel-view__link">查看大图 ↗</a>
            </div>
          </div>
          <div class="gigapixel-view__task-actions">
            <button
              v-if="isCancellable(currentTask.status)"
              class="gigapixel-view__btn gigapixel-view__btn--danger"
              @click="handleCancel(currentTask.id)"
            >
              取消任务
            </button>
            <button class="gigapixel-view__btn" @click="clearCurrentTask">关闭</button>
          </div>
        </div>

        <!-- 任务历史列表 -->
        <div class="gigapixel-view__card">
          <h3 class="gigapixel-view__card-title">
            <span>📜 任务历史</span>
            <button class="gigapixel-view__btn gigapixel-view__btn--small" @click="loadTaskHistory">🔄 刷新</button>
          </h3>
          <div v-if="loadingHistory" class="gigapixel-view__loading">加载中...</div>
          <div v-else-if="taskHistory.length === 0" class="gigapixel-view__empty">
            暂无任务历史
          </div>
          <ul v-else class="gigapixel-view__task-list">
            <li
              v-for="task in taskHistory"
              :key="task.id"
              class="gigapixel-view__task-item"
              :class="{ 'gigapixel-view__task-item--active': currentTask?.id === task.id }"
              @click="selectTask(task)"
            >
              <div class="gigapixel-view__task-item-header">
                <span class="gigapixel-view__status" :class="`gigapixel-view__status--${task.status?.toLowerCase()}`">
                  {{ statusLabel(task.status) }}
                </span>
                <span class="gigapixel-view__task-time">{{ formatTime(task.submit_time) }}</span>
              </div>
              <div class="gigapixel-view__task-item-body">
                <div v-if="task.data?.settings">
                  <strong>{{ task.data.settings.model || '?' }}</strong> · {{ task.data.settings.scale || '?' }}x
                </div>
                <div v-if="task.fail_reason" class="gigapixel-view__task-item-error">
                  {{ task.fail_reason }}
                </div>
                <div v-if="task.data?.input_path" class="gigapixel-view__task-item-path">
                  {{ basename(task.data.input_path) }}
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 图片库选择器（弹窗） -->
    <ImageSelector
      :visible="showImageSelector"
      :images="libraryImages"
      @update:visible="showImageSelector = $event"
      @select="handleSelectFromLibrary"
    />

    <!-- 预览大图 -->
    <ImagePreview
      v-if="previewImageUrl"
      :image="previewImageObject"
      @close="previewImageUrl = ''"
    />

    <!-- 确认弹窗 -->
    <ConfirmDialog
      v-model:visible="showConfirmDialog"
      :title="confirmDialogConfig.title"
      :message="confirmDialogConfig.message"
      :confirm-text="confirmDialogConfig.confirmText"
      :cancel-text="confirmDialogConfig.cancelText"
      :danger="confirmDialogConfig.danger"
      @confirm="confirmDialogConfig.onConfirm"
      @cancel="confirmDialogConfig.onCancel"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useConfigStore } from '@/stores/configStore'
import { useImageStore } from '@/stores/imageStore'
import {
  checkGigapixelAvailable,
  uploadGigapixelFile,
  submitGigapixelUpscale,
  queryGigapixelTask,
  listGigapixelTasks,
  cancelGigapixelTask
} from '@/services/api'
import ImageSelector from '@/components/common/ImageSelector/ImageSelector.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'
import ImagePreview from '@/components/ImagePreview.vue'

// Topaz Gigapixel 9 个模型选项（与后端 MODEL_MAPPING 一一对应）
const MODEL_OPTIONS = [
  'Art & CG',
  'Lines',
  'Very Compressed',
  'High Fidelity',
  'Low Resolution',
  'Standard',
  'Text & Shapes',
  'Redefine',
  'Recover'
]

// 模型中文说明（前端展示用）
const MODEL_DESCRIPTIONS = {
  'Art & CG': '针对艺术插画、CG 渲染、游戏原画优化，保留笔触与材质感',
  'Lines': '针对线稿、漫画、线描类图像，强化线条干净度',
  'Very Compressed': '针对高度压缩的 JPEG/社交媒体图片，强力修复压缩伪影',
  'High Fidelity': '高保真模式，最小改变原图，输出最接近原片',
  'Low Resolution': '针对低分辨率老照片/截图，最大幅度恢复细节',
  'Standard': '通用标准模型，适用大多数照片，平衡质量与速度',
  'Text & Shapes': '针对包含文字、几何形状、UI 截图的图像，锐化边缘',
  'Redefine': '重新定义模式，AI 主动"脑补"生成新细节',
  'Recover': '恢复模式，配合 Pre-Downscaling 使用，修复严重退化图'
}

// 各个高级参数的中文说明
// 结构：{ 作用: '...', 取值: '...', 建议: '...', 默认: '...' }
const PARAM_DESCRIPTIONS = {
  scale: {
    title: '缩放倍率 Scale',
    effect: '最终输出分辨率 = 原图尺寸 × 倍率。例如 1024×1024 图 ×4 = 4096×4096。',
    range: '1.0-16.0，可填小数（步进 0.1）',
    suggest: '网络/手机端 2x 足够；印刷/大屏展示 4x；老照片/小图标可尝试 6x-8x（更高易失真且慢）',
    default: '2.0'
  },
  model: {
    title: 'AI 模型 Model',
    effect: '决定 Topaz 用哪种"脑回路"补图；不同模型擅长场景不同',
    range: '9 个内置模型，详见下方芯片',
    suggest: '不确定选哪个时，先用 Standard 试一张，效果不满意再换',
    default: 'Standard'
  },
  detail: {
    title: '详细参数',
    effect: '关闭时仅传倍率，使用 Topaz 默认参数（推荐新手）；开启后可微调下方 4-5 个进阶滑块',
    range: '开 / 关',
    suggest: '新手保持关闭；想精细控制时再开启',
    default: '关'
  },
  sharpen: {
    title: '锐化 Sharpen',
    effect: '增强边缘与细节清晰度，让放大后的图看起来更"锐利"',
    range: '0-100（0 = 不传该参数，用 Topaz 内部默认）',
    suggest: '人像 1-30（太高皮肤失真）；风光 30-60；文字/UI 截图 50-80',
    default: '1'
  },
  denoise: {
    title: '降噪 Denoise',
    effect: '抑制高 ISO、夜景、暗光环境下产生的颗粒与彩色噪点',
    range: '0-100（0 = 不传该参数）',
    suggest: '夜景/高 ISO 照片 30-60；正常光照 1-20；二次元/插画保持 0-1（避免破坏线条）',
    default: '1'
  },
  compression: {
    title: '压缩修复 Compression',
    effect: '修复 JPEG 多次保存产生的块状伪影、马赛克、振铃效应（俗称"蚊子噪"）',
    range: '0-100（0 = 不传该参数）',
    suggest: '默认 67 适合大多数情况；社媒下载图可提到 80-100；原始 RAW/PNG 保持 0-30',
    default: '67'
  },
  fr: {
    title: '细节保留 Fine Detail',
    effect: '控制在生成新细节时"创造" vs "保留"原图细节的平衡',
    range: '0-100（0 = 不传该参数）',
    suggest: '证件照/纪实摄影 70-100（防止 AI 脑补）；老照片修复 30-50（让 AI 脑补细节）；插画 50-70',
    default: '50'
  },
  pre_downscaling: {
    title: '预降采样 Pre-Downscaling（仅 Recover）',
    effect: 'Recover 模型专用 —— 先把图缩小到指定比例再放大，避免恢复时引入伪影',
    range: '50-100',
    suggest: '模糊严重的图 75 左右；轻度模糊 85-95；只有噪点没模糊保持 100',
    default: '75'
  },
  keyRule: {
    title: '关键约定',
    effect: '参数值 0 等同于"不传给 gigapixel.exe 命令行，由 Topaz 内部决定"',
    range: '-',
    suggest: '如果你不想要某个效果，把它拉到 0 即可',
    default: '-'
  }
}

const configStore = useConfigStore()
const imageStore = useImageStore()

// 可用性检测
const checking = ref(true)
const available = ref(false)
const availableMessage = ref('')

// 选中的图片（单选）
const selectedImage = ref(null)

// 图片选择器弹窗
const showImageSelector = ref(false)

// 本地上传相关
const uploadInputRef = ref(null)
const isUploadDragOver = ref(false)
const uploading = ref(false)

// 预览
const previewImageUrl = ref('')
const previewImageObject = computed(() => previewImageUrl.value ? { url: previewImageUrl.value } : null)

// 提交参数（默认从 configStore 读取；这里仅作兜底，运行时会被 applyConfigDefaults 覆盖）
// 重要：与后端 config_model.py 保持一致，且与 ComfyUI 官方节点 GigapixelUpscaleSettings 默认值一致
// 注意：gigapixel.exe 命令行只有当参数 > 0 时才会真正传递；0 等同于"不传该参数"
const form = ref({
  scale: 2.0,
  model: 'Standard',
  enabled: true,
  sharpen: 1,        // 官方默认 1（0 = 不传）
  denoise: 1,        // 官方默认 1（0 = 不传）
  compression: 67,   // 官方默认 67
  fr: 50,            // 官方默认 50
  pre_downscaling: 75 // 官方默认 75（仅 Recover 模型生效）
})

// 提交状态
const submitting = ref(false)

// 当前任务
const currentTask = ref(null)
const currentImage = ref(null)
let pollingTimer = null

// 任务历史
const taskHistory = ref([])
const loadingHistory = ref(false)

// ConfirmDialog
const showConfirmDialog = ref(false)
const confirmDialogConfig = ref({
  title: '',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  onConfirm: () => {},
  onCancel: () => {}
})

function showConfirm(config) {
  confirmDialogConfig.value = { ...config }
  showConfirmDialog.value = true
}

const libraryImages = computed(() => {
  return Array.isArray(imageStore.images) ? imageStore.images : []
})

const canSubmit = computed(() => {
  return !submitting.value && available.value && selectedImage.value
})

const progressPercent = computed(() => {
  const p = currentTask.value?.progress || '0%'
  const match = String(p).match(/(\d+)/)
  return match ? Math.min(100, Math.max(0, parseInt(match[1]))) : 0
})

// 状态标签本地化
function statusLabel(status) {
  const map = {
    'PENDING': '排队中',
    'IN_PROGRESS': '处理中',
    'SUCCESS': '已完成',
    'FAILURE': '失败',
    'CANCELLED': '已取消'
  }
  return map[status] || status
}

function isCancellable(status) {
  return ['PENDING', 'IN_PROGRESS', '未启动', 'QUEUED', 'NOT_STARTED', 'NOT_START', 'WAITING'].includes(status)
}

function formatTime(ms) {
  if (!ms) return ''
  try {
    const d = new Date(Number(ms))
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch {
    return ''
  }
}

function basename(path) {
  if (!path) return ''
  return String(path).split(/[\\/]/).pop() || path
}

function clearSelected() {
  selectedImage.value = null
}

function handleSelectFromLibrary(image) {
  if (image) {
    selectedImage.value = image
  }
  showImageSelector.value = false
}

function handlePreviewSelected() {
  if (selectedImage.value?.url) {
    previewImageUrl.value = selectedImage.value.url
  }
}

// 本地上传：触发文件选择
function triggerUpload() {
  uploadInputRef.value?.click()
}

// 本地上传：文件选择变化
async function handleUploadChange(event) {
  const file = event.target.files?.[0]
  if (file) {
    await processUploadFile(file)
  }
  event.target.value = '' // 重置以便下次选同一文件
}

// 本地上传：拖拽文件
async function handleUploadDrop(event) {
  isUploadDragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) {
    await processUploadFile(file)
  }
}

// 本地上传：处理文件 -> multipart/form-data 上传到后端 -> 后端落盘 -> 返回绝对路径
// 后续提交时 image_path 直接传返回的本地路径，gigapixel.exe 用该路径读取原图
async function processUploadFile(file) {
  // 校验文件类型与大小
  const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/tiff']
  if (!validTypes.includes(file.type)) {
    showConfirm({
      title: '格式不支持',
      message: `仅支持 JPG / PNG / WebP / TIFF 格式，当前文件: ${file.type || '未知'}`,
      confirmText: '我知道了',
      cancelText: '关闭',
      onConfirm: () => { showConfirmDialog.value = false },
      onCancel: () => { showConfirmDialog.value = false }
    })
    return
  }
  if (file.size > 50 * 1024 * 1024) {
    showConfirm({
      title: '文件过大',
      message: `单张图片不能超过 50MB，当前文件: ${(file.size / 1024 / 1024).toFixed(1)}MB`,
      confirmText: '我知道了',
      cancelText: '关闭',
      onConfirm: () => { showConfirmDialog.value = false },
      onCancel: () => { showConfirmDialog.value = false }
    })
    return
  }

  uploading.value = true
  try {
    // multipart/form-data 上传到后端，后端落盘到 gigapixel_temp/uploads/
    const res = await uploadGigapixelFile(file)

    if (!res?.success || !res?.uploaded_path) {
      throw new Error(res?.error || '上传失败')
    }

    // 生成本地预览用的 dataURL（只用于 UI 显示缩略图，不参与业务逻辑）
    const dataUrl = await readFileAsDataUrl(file)

    selectedImage.value = {
      id: '',                          // 无图片库 id，标识为「本地上传」
      url: dataUrl,                    // 预览用 dataURL
      thumbnail: dataUrl,              // 缩略图同 dataURL
      prompt: file.name,
      title: file.name,
      local_path: res.uploaded_path,   // 后端落盘后的本地绝对路径（submit 时传这个）
      uploaded_preview_url: res.preview_url
    }
  } catch (e) {
    showConfirm({
      title: '上传失败',
      message: e?.message || '上传文件到服务器失败，请重试',
      confirmText: '我知道了',
      cancelText: '关闭',
      onConfirm: () => { showConfirmDialog.value = false },
      onCancel: () => { showConfirmDialog.value = false }
    })
  } finally {
    uploading.value = false
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(e.target.result)
    reader.onerror = (e) => reject(new Error('读取文件失败'))
    reader.readAsDataURL(file)
  })
}

async function checkAvailable() {
  checking.value = true
  try {
    const res = await checkGigapixelAvailable()
    if (res?.success) {
      available.value = !!res.available
      availableMessage.value = res.message || ''
    } else {
      available.value = false
      availableMessage.value = res?.error || '检测失败'
    }
  } catch (e) {
    available.value = false
    availableMessage.value = e?.message || '检测失败'
  } finally {
    checking.value = false
  }
}

function applyConfigDefaults() {
  // 从后端配置读取默认值，缺失字段时回退到 ComfyUI 官方节点默认
  // 注意：gigapixel.exe 只在参数 > 0 时才传给命令行
  const cfg = configStore.topazGigapixel || {}
  form.value.scale = cfg.defaultScale !== undefined ? cfg.defaultScale : 2.0
  form.value.model = cfg.defaultModel || 'Standard'
  form.value.enabled = cfg.defaultEnabled !== undefined ? !!cfg.defaultEnabled : true
  form.value.sharpen = cfg.defaultSharpen !== undefined ? cfg.defaultSharpen : 1
  form.value.denoise = cfg.defaultDenoise !== undefined ? cfg.defaultDenoise : 1
  form.value.compression = cfg.defaultCompression !== undefined ? cfg.defaultCompression : 67
  form.value.fr = cfg.defaultFr !== undefined ? cfg.defaultFr : 50
  form.value.pre_downscaling = cfg.defaultPreDownscaling !== undefined ? cfg.defaultPreDownscaling : 75
}

// 参数说明可见性默认值（去掉 global，每个参数独立控制）
const defaultDescVisibility = {
  intro: true,
  scale: true,
  model: true,
  sharpen: true,
  denoise: true,
  compression: true,
  fr: true,
  pre_downscaling: true
}

// 获取当前参数说明可见性配置（从 configStore 读取，已持久化到后端数据库）
function getDescVisibility() {
  return configStore.topazGigapixel?.descriptionVisibility || { ...defaultDescVisibility }
}

// 判断是否所有说明都可见（用于全局按钮文字）
function allDescVisible() {
  const vis = getDescVisibility()
  return Object.keys(defaultDescVisibility).every(k => vis[k])
}

// 切换单个参数的说明可见性，并同步保存到后端数据库
function toggleDescVisibility(key) {
  const current = getDescVisibility()
  const newVal = !current[key]
  const updated = { ...current, [key]: newVal }
  configStore.topazGigapixel.descriptionVisibility = updated
  configStore.saveConfig({ topazGigapixel: { descriptionVisibility: updated } }).catch(e => {
    console.error('[GigapixelView] 保存描述可见性失败:', e)
  })
}

// 批量操作：全部打开 或 全部关闭
// - 如果全部已打开 → 全部关闭（已关的不动，开的关掉）
// - 如果有任意关闭 → 全部打开（已开的不动，关的打开）
function toggleAllDescVisibility() {
  const current = getDescVisibility()
  const allVisible = Object.keys(defaultDescVisibility).every(k => current[k])
  const updated = {}
  for (const k of Object.keys(defaultDescVisibility)) {
    // 全部已打开 → 全部设为 false；否则全部设为 true
    updated[k] = allVisible ? false : true
  }
  configStore.topazGigapixel.descriptionVisibility = updated
  configStore.saveConfig({ topazGigapixel: { descriptionVisibility: updated } }).catch(e => {
    console.error('[GigapixelView] 保存全局描述可见性失败:', e)
  })
}

async function handleSubmit() {
  if (!selectedImage.value) {
    showConfirm({
      title: '提示',
      message: '请先选择一张图片（从图片库或本地上传）',
      confirmText: '我知道了',
      cancelText: '关闭',
      onConfirm: () => { showConfirmDialog.value = false },
      onCancel: () => { showConfirmDialog.value = false }
    })
    return
  }

  submitting.value = true
  try {
    // 构造 payload：image_id 优先；如果是本地上传没有 id，则用 image_path
    const payload = {
      scale: form.value.scale,
      model: form.value.model,
      enabled: form.value.enabled,
      sharpen: form.value.sharpen,
      denoise: form.value.denoise,
      compression: form.value.compression,
      fr: form.value.fr,
      pre_downscaling: form.value.pre_downscaling
    }
    if (selectedImage.value.id) {
      payload.image_id = selectedImage.value.id
    } else if (selectedImage.value.local_path) {
      payload.image_path = selectedImage.value.local_path
    }

    const res = await submitGigapixelUpscale(payload)

    if (res?.success && res?.task_id) {
      currentTask.value = {
        id: res.task_id,
        status: 'PENDING',
        progress: '0%'
      }
      currentImage.value = null
      startPolling(res.task_id)
      loadTaskHistory()
    } else {
      const errMsg = res?.error || '提交失败'
      showConfirm({
        title: '提交失败',
        message: errMsg,
        confirmText: '我知道了',
        cancelText: '关闭',
        onConfirm: () => { showConfirmDialog.value = false },
        onCancel: () => { showConfirmDialog.value = false }
      })
    }
  } catch (e) {
    showConfirm({
      title: '提交出错',
      message: e?.message || '未知错误',
      confirmText: '我知道了',
      cancelText: '关闭',
      onConfirm: () => { showConfirmDialog.value = false },
      onCancel: () => { showConfirmDialog.value = false }
    })
  } finally {
    submitting.value = false
  }
}

function startPolling(taskId) {
  stopPolling()
  pollingTimer = setInterval(async () => {
    try {
      const res = await queryGigapixelTask(taskId)
      if (res?.success && res?.task) {
        currentTask.value = res.task
        currentImage.value = res.image || null
        const status = res.task.status
        if (['SUCCESS', 'FAILURE', 'CANCELLED'].includes(status)) {
          stopPolling()
          loadTaskHistory()
        }
      }
    } catch (e) {
      console.error('[GigapixelView] polling error', e)
    }
  }, 3000)
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function clearCurrentTask() {
  stopPolling()
  currentTask.value = null
  currentImage.value = null
}

function selectTask(task) {
  currentTask.value = task
  stopPolling()
  if (isCancellable(task.status)) {
    startPolling(task.id)
  }
  queryGigapixelTask(task.id).then(res => {
    if (res?.success && res?.image) {
      currentImage.value = res.image
    }
  })
}

function handleCancel(taskId) {
  showConfirm({
    title: '取消任务',
    message: '确定要取消这个放大任务吗？取消后正在执行的子进程会完成后丢弃结果。',
    confirmText: '确定取消',
    cancelText: '继续等待',
    danger: true,
    onConfirm: async () => {
      showConfirmDialog.value = false
      try {
        const res = await cancelGigapixelTask(taskId)
        if (res?.success) {
          loadTaskHistory()
          if (currentTask.value?.id === taskId) {
            currentTask.value = { ...currentTask.value, status: 'CANCELLED', fail_reason: '用户取消' }
          }
        } else {
          showConfirm({
            title: '取消失败',
            message: res?.error || '未知错误',
            confirmText: '我知道了',
            cancelText: '关闭',
            onConfirm: () => { showConfirmDialog.value = false },
            onCancel: () => { showConfirmDialog.value = false }
          })
        }
      } catch (e) {
        showConfirm({
          title: '取消出错',
          message: e?.message || '未知错误',
          confirmText: '我知道了',
          cancelText: '关闭',
          onConfirm: () => { showConfirmDialog.value = false },
          onCancel: () => { showConfirmDialog.value = false }
        })
      }
    },
    onCancel: () => { showConfirmDialog.value = false }
  })
}

async function loadTaskHistory() {
  loadingHistory.value = true
  try {
    const res = await listGigapixelTasks()
    if (res?.success && Array.isArray(res.tasks)) {
      taskHistory.value = res.tasks
    } else {
      taskHistory.value = []
    }
  } catch (e) {
    console.error('[GigapixelView] loadTaskHistory error', e)
    taskHistory.value = []
  } finally {
    loadingHistory.value = false
  }
}

onMounted(async () => {
  if (!configStore.initialized) {
    try { await configStore.fetchConfig() } catch (e) { /* ignore */ }
  }
  applyConfigDefaults()
  await checkAvailable()
  try { await imageStore.fetchImages?.() } catch (e) { /* ignore */ }
  await loadTaskHistory()
})

onUnmounted(() => {
  stopPolling()
})

watch(() => configStore.topazGigapixel, () => {
  applyConfigDefaults()
}, { deep: true })
</script>

<style lang="scss" src="@/styles/GigapixelView.scss"></style>
