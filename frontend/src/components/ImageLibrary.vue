<template>
  <div
    class="image-library"
    :class="{ 'image-library--selection-mode': selectionMode }"
  >
    <div class="image-library__header">
      <div class="image-library__header-left">
        <div class="image-library__folder-select" @click="toggleFolderDropdown">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
          <span>{{ activeFolderName }}</span>
          <svg class="image-library__folder-select-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
          <div v-if="showFolderDropdown" class="image-library__folder-dropdown">
            <button
              v-for="folder in folders"
              :key="folder.id"
              class="image-library__folder-option"
              :class="{ 'image-library__folder-option--active': activeFolder === folder.id }"
              @click.stop="handleSelectFolder(folder.id); showFolderDropdown = false"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
              </svg>
              <span>{{ folder.name }}</span>
              <span class="image-library__folder-option-count">{{ folder.count }}</span>
              <button
                v-if="folder.id !== 'all' && folder.id !== 'recycle'"
                class="image-library__folder-option-delete"
                @click.stop="handleDeleteFolder(folder)"
                title="删除文件夹"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </button>
          </div>
        </div>

        <button 
          class="image-library__header-btn" 
          :class="{ 'image-library__header-btn--active': selectionMode }"
          @click="toggleSelectionMode"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
          </svg>
          <span>{{ selectionMode ? '取消多选' : '多选' }}</span>
        </button>

        <button v-if="selectionMode" class="image-library__header-btn" @click="handleSelectAll">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <polyline points="9 12 12 15 21 6"></polyline>
          </svg>
          <span>全选</span>
        </button>

        <button class="image-library__header-btn" @click="handleNewFolder">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 4v16m8-8H4"></path>
          </svg>
          <span>新建文件夹</span>
        </button>

        <button class="image-library__header-btn" @click="handleOpenMaterial">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
          </svg>
          <span>素材库</span>
        </button>
      </div>
      <div class="image-library__header-right">
        <div class="image-library__sort-select">
          <Select
            v-model="currentSortValue"
            :options="sortOptions"
            wrapper-class="image-library__sort-select-wrapper"
          />
        </div>
        <button class="image-library__header-btn image-library__header-btn--danger" @click="handleClearAll">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          <span>清空</span>
        </button>
      </div>
    </div>

    <div v-if="selectionMode && selectedImages.length > 0" class="image-library__batch-bar">
      <span class="image-library__batch-count">已选择 {{ selectedImages.length }} 张图片</span>
      <div class="image-library__batch-actions">
        <!-- 回收站视图的批量操作按钮 -->
        <template v-if="isRecycleBinView">
          <button class="image-library__batch-btn" @click="handleBatchRestore">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="1 4 1 10 7 10"></polyline>
              <polyline points="23 20 23 14 17 14"></polyline>
              <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path>
            </svg>
            批量恢复
          </button>
          <button class="image-library__batch-btn image-library__batch-btn--danger" @click="handleBatchPermanentDelete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            全部永久删除
          </button>
        </template>
        <!-- 普通视图的批量操作按钮 -->
        <template v-else>
          <button class="image-library__batch-btn" @click="handleBatchMove">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 19V5m0 0l7 7-7 7"></path>
            </svg>
            批量移动
          </button>
          <button class="image-library__batch-btn" @click="handleBatchAsReference">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <circle cx="8.5" cy="8.5" r="1.5"></circle>
              <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
            批量设为参考图
          </button>
          <button class="image-library__batch-btn image-library__batch-btn--danger" @click="handleBatchDelete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            批量删除
          </button>
        </template>
      </div>
    </div>

    <div v-if="initialLoading && (!images || images.length === 0)" class="image-library__loading">
      <div class="image-library__spinner"></div>
    </div>

    <div v-else-if="!isRecycleBinView && (!images || images.length === 0)" class="image-library__empty">
      <svg class="image-library__empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
        <circle cx="8.5" cy="8.5" r="1.5"></circle>
        <polyline points="21 15 16 10 5 21"></polyline>
      </svg>
      <p class="image-library__empty-text">暂无图像</p>
      <p class="image-library__empty-hint">在左侧输入提示词开始生成</p>
    </div>

    <div v-else-if="isRecycleBinView && recycleBinImages.length === 0" class="image-library__empty">
      <svg class="image-library__empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
      </svg>
      <p class="image-library__empty-text">回收站为空</p>
      <p class="image-library__empty-hint">被删除的图片将在这里显示</p>
    </div>

    <div v-else class="image-library__grid-container">
      <div v-if="refreshing" class="image-library__refreshing">图片列表刷新中...</div>
      <div class="image-library__grid">
          <div
            v-for="(image, index) in sortedImages"
            :key="image.id || index"
            class="image-card"
            :class="{
              'image-card--selected': isSelected(image),
              'image-card--generating': image.generating,
              'image-card--error': image.error
            }"
            :style="getCardStyle(image)"
            @click="handleCardClick(image)"
          >
            <div class="image-card__wrapper" :style="getImageWrapperStyle(image)">
              <div v-if="image.generating === true" class="image-card__generating-overlay">
                <div class="image-card__spinner"></div>
                <span class="image-card__generating-text">正在生成中...</span>
                <div class="image-card__generating-progress">
                  <div class="image-card__generating-progress-fill"></div>
                </div>
              </div>
              <div v-else-if="image.error" class="image-card__error-overlay">
                <svg class="image-card__error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <span class="image-card__error-text">{{ image.error }}</span>
              </div>
              <img
                v-else-if="(image.url || image.src || image.thumbnail) && !failedImageKeys.has(getImageKey(image))"
                :src="image.url || image.src || image.thumbnail"
                :alt="image.alt || image.title || ''"
                class="image-card__image"
                loading="lazy"
                @load="onCardImageLoad(image, $event)"
                @error="onCardImageError(image)"
              />
              <div v-else class="image-card__placeholder">
                <svg v-if="failedImageKeys.has(getImageKey(image))" class="image-card__placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="9" y1="9" x2="15" y2="15"></line>
                  <line x1="15" y1="9" x2="9" y2="15"></line>
                </svg>
                <span class="image-card__placeholder-text">{{ failedImageKeys.has(getImageKey(image)) ? '图片加载失败' : '缩略图生成中' }}</span>
              </div>
              <div v-if="!selectionMode" class="image-card__overlay">
                <div class="image-card__actions">
                  <!-- 回收站视图的操作按钮 -->
                  <template v-if="isRecycleBinView">
                    <button
                      class="image-card__action-btn"
                      @click.stop="handleRestoreImage(image)"
                    >
                      <svg class="image-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="1 4 1 10 7 10"></polyline>
                        <polyline points="23 20 23 14 17 14"></polyline>
                        <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path>
                      </svg>
                      <span>恢复</span>
                    </button>
                    <button
                      class="image-card__action-btn image-card__action-btn--danger"
                      @click.stop="handlePermanentDelete(image)"
                    >
                      <svg class="image-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                      <span>永久删除</span>
                    </button>
                  </template>
                  <!-- 普通视图的操作按钮 -->
                  <template v-else>
                    <button
                      v-if="!image.error && image.generating !== true"
                      class="image-card__action-btn"
                      @click.stop="handleReusePrompt(image)"
                      :disabled="image.disabled"
                    >
                      <svg class="image-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="1 4 1 10 7 10"></polyline>
                        <polyline points="23 20 23 14 17 14"></polyline>
                        <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path>
                      </svg>
                      <span>复用</span>
                    </button>
                    <button
                      v-if="!image.error && image.generating !== true"
                      class="image-card__action-btn"
                      @click.stop="handleEdit(image)"
                      :disabled="image.disabled"
                    >
                      <svg class="image-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                      </svg>
                      <span>编辑</span>
                    </button>
                    <button
                      v-if="!image.error && image.generating !== true"
                      class="image-card__action-btn"
                      @click.stop="handleMove(image)"
                      :disabled="image.disabled"
                    >
                      <svg class="image-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 19V5m0 0l7 7-7 7"></path>
                      </svg>
                      <span>移动</span>
                    </button>
                    <button
                      v-if="!image.error && image.generating !== true"
                      class="image-card__action-btn"
                      @click.stop="emit('add-to-preparation', image)"
                      :disabled="image.disabled"
                    >
                      <svg class="image-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                      </svg>
                      <span>预备</span>
                    </button>
                    <button
                      class="image-card__action-btn image-card__action-btn--danger"
                      @click.stop="handleDelete(image)"
                    >
                      <svg class="image-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                      <span>删除</span>
                    </button>
                    <button
                      v-if="image.error && image.gptsapiRawResult"
                      class="image-card__action-btn"
                      @click.stop="emit('gptsapi-retry', image)"
                    >
                      <svg class="image-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="1 4 1 10 7 10"></polyline>
                        <polyline points="23 20 23 14 17 14"></polyline>
                        <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path>
                      </svg>
                      <span>重新获取</span>
                    </button>
                  </template>
                </div>
              </div>
              <div v-if="selectionMode && isSelected(image)" class="image-card__selected-mark">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </div>
            </div>
            <div v-if="image.model || image.size" class="image-card__info">
              <div class="image-card__meta">
                <span class="image-card__meta-item">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                  </svg>
                  {{ image.apiSource === 'fal' ? 'Fal' : image.apiSource === 'gptsapi' ? 'GPTsAPI' : 'T8' }}
                </span>
                <span class="image-card__meta-item">{{ formatImageSizeMeta(image) }}</span>
                <span class="image-card__meta-item">PNG</span>
              </div>
            </div>
          </div>
        </div>
    </div>

    <div v-if="showMoveModal" class="image-library__modal-overlay" @click="showMoveModal = false">
      <div class="image-library__modal" @click.stop>
        <div class="image-library__modal-header">
          <span>{{ isBatchMove ? '批量移动到文件夹' : '移动到文件夹' }}</span>
          <button class="image-library__modal-close" @click="showMoveModal = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="image-library__modal-body">
          <button
            v-for="folder in folderList"
            :key="folder.id"
            class="image-library__modal-folder-item"
            :class="{ 'image-library__modal-folder-item--active': moveTargetFolderId === folder.id }"
            @click="moveTargetFolderId = folder.id"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
            </svg>
            <span>{{ folder.name }}</span>
            <span class="image-library__modal-folder-count">{{ folder.image_count }}</span>
          </button>
          <p v-if="folderList.length === 0" class="image-library__modal-empty">暂无文件夹</p>
        </div>
        <div class="image-library__modal-footer">
          <button class="image-library__modal-btn image-library__modal-btn--secondary" @click="showMoveModal = false">取消</button>
          <button class="image-library__modal-btn image-library__modal-btn--primary" :disabled="!moveTargetFolderId" @click="confirmMove">确认移动</button>
        </div>
      </div>
    </div>



    <ConfirmDialog
      v-model:visible="showClearConfirm"
      :title="isRecycleBinView ? '确认清空回收站' : '确认清空'"
      :message="isRecycleBinView ? '确定要清空回收站吗？所有图片将被永久删除，此操作不可撤销。' : '确定要清空所有图片吗？图片将移动到回收站。'"
      confirm-text="清空"
      cancel-text="取消"
      :danger="true"
      @confirm="confirmClearAll"
    />

    <ConfirmDialog
      v-model:visible="showDeleteConfirm"
      :title="isBatchDelete ? `确认删除 (${deleteCount} 张)` : '确认删除'"
      :message="isBatchDelete ? `确定要删除选中的 ${deleteCount} 张图片吗？此操作不可撤销。` : '确定要删除该图片吗？'"
      confirm-text="删除"
      cancel-text="取消"
      :danger="true"
      @confirm="confirmDelete"
    />

    <ConfirmDialog
      v-model:visible="showDeleteFolderConfirm"
      title="确认删除文件夹"
      :message="`确定要删除文件夹「${deleteFolderTarget?.name}」吗？该文件夹内的所有图片将自动移动到「全部图片」。`"
      confirm-text="删除"
      cancel-text="取消"
      :danger="true"
      @confirm="confirmDeleteFolder"
    />

    <MaterialSelector
      :show="showMaterialSelector"
      @close="showMaterialSelector = false"
      @select="handleMaterialSelect"
    />

    <div v-if="showFolderModal" class="image-library__modal-overlay" @click="closeFolderModal">
      <div class="image-library__modal" @click.stop>
        <div class="image-library__modal-header">
          <span>新建文件夹</span>
          <button class="image-library__modal-close" @click="closeFolderModal">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="image-library__modal-body">
          <input
            v-model="newFolderName"
            type="text"
            class="image-library__modal-input"
            placeholder="请输入文件夹名称"
            @keyup.enter="handleCreateFolder"
            ref="folderInputRef"
          />
        </div>
        <div class="image-library__modal-footer">
          <button class="image-library__modal-btn image-library__modal-btn--secondary" @click="closeFolderModal">
            取消
          </button>
          <button 
            class="image-library__modal-btn image-library__modal-btn--primary" 
            @click="handleCreateFolder"
            :disabled="!newFolderName.trim()"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * ImageLibrary 图片库卡片组件
 *
 * 功能描述：
 *   负责图片列表的展示、瀑布流布局、批量选择/移动/删除操作、文件夹管理
 *   支持多种排序方式，排序状态持久化到 localStorage
 *
 * 职责：
 *   - 根据图片尺寸和比例动态渲染卡片
 *   - 瀑布流网格布局（CSS Grid 自适应列数）
 *   - 批量选择、移动、删除图片
 *   - 文件夹切换和新建
 *   - 排序状态持久化
 *
 * Props:
 *   - images: 图片数据数组
 *   - loading / initialLoading / refreshing: 加载状态
 *   - emptyText: 空状态提示文本
 *
 * Emits:
 *   - view: 查看图片
 *   - edit: 编辑图片
 *   - delete: 删除图片（id 或对象）
 *   - refresh: 刷新列表
 *   - reuse-prompt: 复用提示词
 *   - sort: 排序变更
 *   - new-folder: 新建文件夹
 *   - clear-all: 清空全部
 *   - batch-reference: 批量设为参考图
 *   - select-folder: 选择文件夹
 */
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import Select from '@/components/common/Select/Select.vue'
import { getRecycleBinImages, restoreFromRecycleBin, permanentDelete, moveToRecycleBin, createFolder, deleteFolder } from '@/services/api'
import { useImageStore } from '@/stores/imageStore'
import './ImageLibrary.scss'

const props = defineProps({
  images: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  initialLoading: {
    type: Boolean,
    default: false
  },
  refreshing: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: '暂无图像'
  },
  totalCount: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits([
  'view', 'edit', 'delete', 'refresh', 'reuse-prompt',
  'sort', 'new-folder', 'clear-all', 'batch-reference', 'select-folder',
  'enter-recycle-bin', 'add-to-preparation', 'gptsapi-retry'
])

const imageStore = useImageStore()

const showSortDropdown = ref(false)
const showFolderDropdown = ref(false)
const showFolderModal = ref(false)
const showMaterialSelector = ref(false)
const newFolderName = ref('')
const folderInputRef = ref(null)
const activeFolder = ref('all')
const showMoveModal = ref(false)
const moveTargetFolderId = ref('')
const folderList = ref([])
const movingImage = ref(null)
const showClearConfirm = ref(false)
const showDeleteConfirm = ref(false)
const isBatchDelete = ref(false)
const deleteCount = ref(0)
const deleteTarget = ref(null)
const isRecycleBinView = ref(false)
const recycleBinImages = ref([])
const showDeleteFolderConfirm = ref(false)
const deleteFolderTarget = ref(null)

// 当前排序值（使用 Select 组件）
// 从 localStorage 读取上次的排序选择，如果没有则使用默认值 'latest'
const savedSort = typeof window !== 'undefined' ? localStorage.getItem('image-library-sort') : null
const currentSortValue = ref(savedSort || 'latest')

const selectionMode = ref(false)
const selectedImages = ref([])

/** 缩略图/原图加载后的真实像素，用于卡片比例与元数据（避免仅依赖库里过期的 size） */
const intrinsicByKey = ref({})

const imageMeasureKey = (image) => {
  if (!image) return ''
  return image.id || image.url || image.thumbnail || ''
}

const onCardImageLoad = (image, e) => {
  const key = imageMeasureKey(image)
  const el = e?.target
  if (!key || !el || !el.naturalWidth || !el.naturalHeight) return
  const w = el.naturalWidth
  const h = el.naturalHeight
  const ratio = w / h
  if (!(ratio > 0) || !Number.isFinite(ratio)) return
  intrinsicByKey.value = {
    ...intrinsicByKey.value,
    [key]: { width: w, height: h, ratio }
  }
}

// 追踪图片加载失败的集合，用于展示兜底占位符
const failedImageKeys = ref(new Set())

// 获取图片的唯一标识 key
const getImageKey = (image) => {
  if (!image) return ''
  return image.id || image.url || image.thumbnail || ''
}

// 图片加载失败时的处理：将图片 key 加入失败集合，显示兜底占位符
const onCardImageError = (image) => {
  const key = getImageKey(image)
  if (key) {
    const next = new Set(failedImageKeys.value)
    next.add(key)
    failedImageKeys.value = next
  }
}

// 监听图片列表变化，清理已不存在图片的失败记录
watch(
  () => props.images,
  (list) => {
    const validKeys = new Set((list || []).map(getImageKey).filter(Boolean))
    if (failedImageKeys.value.size > 0) {
      const next = new Set(failedImageKeys.value)
      let changed = false
      for (const k of next) {
        if (!validKeys.has(k)) {
          next.delete(k)
          changed = true
        }
      }
      if (changed) {
        failedImageKeys.value = next
      }
    }
  },
  { deep: true }
)

const formatImageSizeMeta = (image) => {
  const key = imageMeasureKey(image)
  const intr = key ? intrinsicByKey.value[key] : null
  if (intr?.width && intr?.height) {
    return `${intr.width}x${intr.height}`
  }
  return image.size || '1024x1024'
}

watch(
  () => props.images,
  (list) => {
    const valid = new Set((list || []).map(imageMeasureKey).filter(Boolean))
    const cur = intrinsicByKey.value
    const next = { ...cur }
    let changed = false
    for (const k of Object.keys(next)) {
      if (!valid.has(k)) {
        delete next[k]
        changed = true
      }
    }
    if (changed) {
      intrinsicByKey.value = next
    }
  },
  { deep: true }
)
const isBatchMove = ref(false)

const sortOptions = [
  { value: 'latest', label: '最新优先' },
  { value: 'oldest', label: '最早优先' },
  { value: 'name-asc', label: '名称升序' },
  { value: 'name-desc', label: '名称降序' }
]

const currentSort = computed(() => {
  return sortOptions.find(s => s.value === currentSortValue.value) || sortOptions[0]
})

const folders = ref([
  { id: 'all', name: '全部图片', count: 0 },
  { id: 'recycle', name: '回收站', count: 0 }
])

const activeFolderName = computed(() => {
  const folder = folders.value.find(f => f.id === activeFolder.value)
  return folder ? folder.name : '全部图片'
})

const sortedImages = computed(() => {
  const sourceImages = isRecycleBinView.value ? recycleBinImages.value : props.images
  const sorted = [...sourceImages]

  if (isRecycleBinView.value) {
    // 回收站视图按删除时间排序
    return sorted.sort((a, b) => {
      const timeA = new Date(a.deleted_at || a.deletedAt || 0).getTime()
      const timeB = new Date(b.deleted_at || b.deletedAt || 0).getTime()
      return timeB - timeA
    })
  }

  switch (currentSort.value.value) {
    case 'latest':
      // 最新优先：最新的排在最前面（降序）
      return sorted.sort((a, b) => {
        // 支持 created_at 和 createdAt 两种字段名（后端返回 created_at）
        const timeA = new Date(a.created_at || a.createdAt || a.timestamp || 0).getTime()
        const timeB = new Date(b.created_at || b.createdAt || b.timestamp || 0).getTime()
        return timeB - timeA  // 大的在前
      })
    case 'oldest':
      // 最早优先：最早的排在最前面（升序）
      return sorted.sort((a, b) => {
        // 支持 created_at 和 createdAt 两种字段名（后端返回 created_at）
        const timeA = new Date(a.created_at || a.createdAt || a.timestamp || 0).getTime()
        const timeB = new Date(b.created_at || b.createdAt || b.timestamp || 0).getTime()
        return timeA - timeB  // 小的在前
      })
    case 'name-asc':
      return sorted.sort((a, b) => {
        const nameA = (a.title || a.name || '').toLowerCase()
        const nameB = (b.title || b.name || '').toLowerCase()
        return nameA.localeCompare(nameB)
      })
    case 'name-desc':
      return sorted.sort((a, b) => {
        const nameA = (a.title || a.name || '').toLowerCase()
        const nameB = (b.title || b.name || '').toLowerCase()
        return nameB.localeCompare(nameA)
      })
    default:
      return sorted
  }
})

// 监听排序值变化
watch(currentSortValue, (newValue) => {
  // 持久化到 localStorage
  if (typeof window !== 'undefined') {
    localStorage.setItem('image-library-sort', newValue)
  }
  
  const selectedSort = sortOptions.find(s => s.value === newValue)
  if (selectedSort) {
    emit('sort', selectedSort)
  }
})

const isSelected = (image) => {
  return selectedImages.value.some(img => img.id === image.id || img.url === image.url)
}

const toggleSelectionMode = () => {
  selectionMode.value = !selectionMode.value
  if (!selectionMode.value) {
    selectedImages.value = []
  }
}

const handleSelectAll = () => {
  if (selectionMode.value) {
    selectedImages.value = [...sortedImages.value]
  }
}

const toggleFolderDropdown = () => {
  showFolderDropdown.value = !showFolderDropdown.value
}

const handleNewFolder = () => {
  showFolderModal.value = true
  nextTick(() => {
    folderInputRef.value?.focus()
  })
}

const closeFolderModal = () => {
  showFolderModal.value = false
  newFolderName.value = ''
}

const handleOpenMaterial = () => {
  showMaterialSelector.value = true
}

const handleMaterialSelect = (materials) => {
  showMaterialSelector.value = false
  if (materials && materials.length > 0) {
    emit('batch-reference', materials)
  }
}

const handleCreateFolder = async () => {
  const name = newFolderName.value.trim()
  if (!name) return

  try {
    const result = await createFolder(name)
    if (result?.success) {
      await loadAllFolders()
      closeFolderModal()
    } else {
      alert(result?.message || '创建文件夹失败')
    }
  } catch (e) {
    console.error('创建文件夹失败:', e)
    alert('创建文件夹失败，请重试')
  }
}

const handleDeleteFolder = (folder) => {
  deleteFolderTarget.value = folder
  showDeleteFolderConfirm.value = true
}

const confirmDeleteFolder = async () => {
  if (!deleteFolderTarget.value) return

  try {
    console.log('[ImageLibrary] 开始删除文件夹:', deleteFolderTarget.value.id, deleteFolderTarget.value.name)
    const result = await deleteFolder(deleteFolderTarget.value.id)
    console.log('[ImageLibrary] 删除文件夹API响应:', result)

    if (result?.success) {
      console.log('[ImageLibrary] 删除成功，重新加载文件夹列表')
      await loadAllFolders()

      if (activeFolder.value === deleteFolderTarget.value.id) {
        console.log('[ImageLibrary] 当前正在查看被删除的文件夹，切换到全部图片')
        activeFolder.value = 'all'
      }

      deleteFolderTarget.value = null
      showDeleteFolderConfirm.value = false
      console.log('[ImageLibrary] 触发刷新事件')
      emit('refresh')
    } else {
      alert(result?.message || '删除文件夹失败')
    }
  } catch (e) {
    console.error('删除文件夹失败:', e)
    alert('删除文件夹失败，请重试')
  }
}

const handleClearAll = () => {
  showClearConfirm.value = true
}

const confirmClearAll = async () => {
  if (isRecycleBinView.value) {
    // 回收站视图：永久删除所有图片
    if (!confirm('确定要清空回收站吗？所有图片将被永久删除，此操作不可撤销。')) {
      showClearConfirm.value = false
      return
    }
    try {
      for (const img of recycleBinImages.value) {
        await permanentDelete(img.id)
      }
      await loadRecycleBinImages()
      await imageStore.fetchImages()
      await updateRecycleBinCount()
      await loadAllFolders()
    } catch (e) {
      console.error('清空回收站失败:', e)
      alert('清空失败，请重试')
    }
  } else {
    // 普通视图：移动所有图片到回收站
    try {
      for (const img of props.images) {
        const sourcePath = img.local_path || img.localUrl || ''
        await moveToRecycleBin(img.id, sourcePath)
      }
      emit('refresh')
    } catch (e) {
      console.error('清空失败:', e)
      alert('清空失败，请重试')
    }
  }
  showClearConfirm.value = false
}

const handleDelete = (image) => {
  isBatchDelete.value = false
  deleteTarget.value = image
  deleteCount.value = 1
  showDeleteConfirm.value = true
}

const confirmDelete = () => {
  if (isBatchDelete.value && deleteTarget.value) {
    deleteTarget.value.forEach(img => {
      emit('delete', img.id || img)
    })
  } else if (deleteTarget.value) {
    emit('delete', deleteTarget.value.id || deleteTarget.value)
  }
  showDeleteConfirm.value = false
  deleteTarget.value = null
}

const handleSelectFolder = (folderId) => {
  console.log('[ImageLibrary] handleSelectFolder called:', folderId)
  activeFolder.value = folderId
  // 切换文件夹时清空选中状态
  selectedImages.value = []
  selectionMode.value = false
  if (folderId === 'recycle') {
    console.log('[ImageLibrary] Switching to recycle bin view')
    isRecycleBinView.value = true
    loadRecycleBinImages()
    emit('enter-recycle-bin')
    // 回收站不保存到 localStorage
  } else {
    console.log('[ImageLibrary] Switching to normal view:', folderId)
    isRecycleBinView.value = false
    recycleBinImages.value = []
    emit('select-folder', folderId)
    // 保存到 localStorage，持久化文件夹选择状态
    if (typeof window !== 'undefined') {
      localStorage.setItem('image-library-folder', folderId)
    }
  }
}

const loadRecycleBinImages = async () => {
  try {
    const data = await getRecycleBinImages()
    console.log('[ImageLibrary] loadRecycleBinImages response:', data)
    if (data.success && Array.isArray(data.data)) {
      recycleBinImages.value = data.data.map(img => {
        // 回收站图片使用缩略图显示，因为原图已被移动到回收站
        // thumbnail 格式可能是 /api/static/generated_thumbnails/xxx.png 或只有文件名
        let thumbnailUrl = img.thumbnail || ''
        // 如果是完整路径（以 /api/static/ 开头），直接使用
        // 否则假设是相对文件名，拼接完整路径
        let displayUrl = thumbnailUrl
        if (thumbnailUrl && !thumbnailUrl.startsWith('/api/static/') && !thumbnailUrl.startsWith('http') && !thumbnailUrl.startsWith('data:')) {
          displayUrl = `/api/static/generated_thumbnails/${thumbnailUrl}`
        }
        return {
          ...img,
          url: displayUrl || img.url || '',
          thumbnail: displayUrl || img.thumbnail || '',
          id: img.id
        }
      })
    } else {
      recycleBinImages.value = []
    }
  } catch (e) {
    console.error('获取回收站图片失败:', e)
    recycleBinImages.value = []
  }
}

const handleRestoreImage = async (image) => {
  try {
    await restoreFromRecycleBin(image.id)
    await loadRecycleBinImages()
    await imageStore.fetchImages()
    await loadAllFolders()
  } catch (e) {
    console.error('恢复图片失败:', e)
    recycleBinImages.value = recycleBinImages.value.filter(img => img.id !== image.id)
    await updateRecycleBinCount()
    alert('恢复失败，该图片可能已被清理')
  }
}

const handlePermanentDelete = async (image) => {
  if (!confirm('确定要永久删除该图片吗？此操作不可撤销。')) {
    return
  }
  try {
    await permanentDelete(image.id)
    await loadRecycleBinImages()
    await imageStore.fetchImages()
    await loadAllFolders()
  } catch (e) {
    console.error('永久删除失败:', e)
    alert('永久删除失败，请重试')
  }
}

const handleBatchRestore = async () => {
  if (selectedImages.value.length === 0) return
  try {
    for (const img of selectedImages.value) {
      await restoreFromRecycleBin(img.id)
    }
    selectedImages.value = []
    selectionMode.value = false
    await loadRecycleBinImages()
    await imageStore.fetchImages()
    await updateRecycleBinCount()
    await loadAllFolders()
  } catch (e) {
    console.error('批量恢复失败:', e)
    alert('批量恢复失败，请重试')
  }
}

const handleBatchPermanentDelete = async () => {
  if (selectedImages.value.length === 0) return
  if (!confirm(`确定要永久删除选中的 ${selectedImages.value.length} 张图片吗？此操作不可撤销。`)) {
    return
  }
  try {
    for (const img of selectedImages.value) {
      await permanentDelete(img.id)
    }
    selectedImages.value = []
    selectionMode.value = false
    await loadRecycleBinImages()
    await imageStore.fetchImages()
    await updateRecycleBinCount()
    await loadAllFolders()
  } catch (e) {
    console.error('批量永久删除失败:', e)
    alert('批量永久删除失败，请重试')
  }
}

const handleCardClick = (image) => {
  if (selectionMode.value) {
    const index = selectedImages.value.findIndex(img => img.id === image.id || img.url === image.url)
    if (index === -1) {
      selectedImages.value.push(image)
    } else {
      selectedImages.value.splice(index, 1)
    }
  } else {
    emit('view', image)
  }
}

const handleEdit = (image) => {
  emit('edit', image)
}

const getAspectRatioValue = (image) => {
  const key = imageMeasureKey(image)
  const intr = key ? intrinsicByKey.value[key] : null
  if (intr?.ratio > 0 && Number.isFinite(intr.ratio)) {
    return intr.ratio
  }
  if (image.aspect_ratio && typeof image.aspect_ratio === 'number' && image.aspect_ratio > 0) {
    return image.aspect_ratio
  }
  
  if (image.size && typeof image.size === 'string' && image.size.includes('x')) {
    const parts = image.size.split('x')
    if (parts.length === 2) {
      const width = parseFloat(parts[0])
      const height = parseFloat(parts[1])
      if (width > 0 && height > 0) {
        return width / height
      }
    }
  }
  
  return 1
}

const getImageWrapperStyle = (image) => {
  const ratio = getAspectRatioValue(image)
  return {
    aspectRatio: String(ratio)
  }
}

const handleMove = (image) => {
  movingImage.value = image
  isBatchMove.value = false
  moveTargetFolderId.value = ''
  showMoveModal.value = true
  fetchFolders()
}

const handleBatchMove = () => {
  movingImage.value = null
  isBatchMove.value = true
  moveTargetFolderId.value = ''
  showMoveModal.value = true
  fetchFolders()
}

const handleBatchAsReference = () => {
  if (selectedImages.value.length === 0) return
  emit('batch-reference', [...selectedImages.value])
  selectionMode.value = false
  selectedImages.value = []
}

const handleBatchDelete = () => {
  if (selectedImages.value.length === 0) return
  isBatchDelete.value = true
  deleteTarget.value = [...selectedImages.value]
  deleteCount.value = selectedImages.value.length
  showDeleteConfirm.value = true
}

const fetchFolders = async () => {
  try {
    const res = await fetch('/api/folders')
    const data = await res.json()
    if (data.success) {
      folderList.value = (data.data || []).filter(f => f.name !== '全部图片' && f.name !== '回收站')
    }
  } catch (e) {
    console.error('获取文件夹失败:', e)
    folderList.value = []
  }
}

const confirmMove = async () => {
  if (!moveTargetFolderId.value) return

  if (isBatchMove.value && selectedImages.value.length > 0) {
    try {
      const results = await Promise.allSettled(
        selectedImages.value.map(img =>
          fetch(`/api/images/${img.id}/move`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_folder_id: moveTargetFolderId.value })
          }).then(res => res.json())
        )
      )
      const failed = results.filter(r => r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.success))
      if (failed.length > 0) {
        console.error(`批量移动失败: ${failed.length} 张图片移动失败`)
        alert(`${failed.length} 张图片移动失败，请重试`)
        return
      }
      emit('refresh')
      selectedImages.value = []
      selectionMode.value = false
      await loadAllFolders()
    } catch (e) {
      console.error('批量移动失败:', e)
      alert('批量移动失败，请重试')
    }
  } else if (movingImage.value) {
    try {
      const res = await fetch(`/api/images/${movingImage.value.id}/move`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_folder_id: moveTargetFolderId.value })
      })
      const data = await res.json()
      if (data.success) {
        emit('refresh')
        await loadAllFolders()
      } else {
        alert(`移动失败: ${data.message}`)
      }
    } catch (e) {
      console.error('移动失败:', e)
      alert('移动失败，请重试')
    }
  }

  showMoveModal.value = false
  movingImage.value = null
  isBatchMove.value = false
}

const handleReusePrompt = (image) => {
  const promptText = image.prompt || image.title
  if (promptText) {
    emit('reuse-prompt', promptText)
  }
}

// 根据图片宽高比动态设置 grid-column span，横版图片获得更宽展示
const getCardStyle = (image) => {
  const ratio = getAspectRatioValue(image)
  if (ratio >= 2.5) {
    // 超宽横版（如 21:9），跨 3 列
    return { gridColumn: 'span 3' }
  }
  if (ratio >= 1.3) {
    // 宽横版（如 16:9、3:2），跨 2 列
    return { gridColumn: 'span 2' }
  }
  // 正方形或竖版，默认 1 列
  return {}
}

const updateRecycleBinCount = async () => {
  try {
    const recycleRes = await fetch('/api/recycle/list')
    const recycleData = await recycleRes.json()
    if (recycleData.success && recycleData.data) {
      const recycleCount = recycleData.data.length
      const recycleFolder = folders.value.find(f => f.id === 'recycle')
      if (recycleFolder) {
        recycleFolder.count = recycleCount
      }
    }
  } catch (e) {
    console.error('获取回收站文件列表失败:', e)
  }
}

const loadAllFolders = async () => {
  try {
    const res = await fetch('/api/folders')
    const data = await res.json()

    // 获取回收站文件夹中的文件数量
    let recycleCount = 0
    try {
      const recycleRes = await fetch('/api/recycle/list')
      const recycleData = await recycleRes.json()
      if (recycleData.success && recycleData.data) {
        recycleCount = recycleData.data.length
      }
    } catch (e) {
      console.error('获取回收站文件列表失败:', e)
    }

    if (data.success && data.data) {
      const apiFolders = data.data.map(f => ({
        id: f.id,
        name: f.name,
        count: f.image_count || 0
      }))
      folders.value = [
        { id: 'all', name: '全部图片', count: props.totalCount || props.images.length },
        ...apiFolders,
        { id: 'recycle', name: '回收站', count: recycleCount }
      ]
    }
  } catch (e) {
    console.error('加载文件夹列表失败:', e)
  }
}

const restoreFolderSelection = () => {
  // 从 localStorage 读取上次选择的文件夹
  const savedFolder = typeof window !== 'undefined' ? localStorage.getItem('image-library-folder') : null
  if (savedFolder && savedFolder !== 'recycle') {
    // 验证文件夹是否存在
    const folderExists = folders.value.some(f => f.id === savedFolder)
    if (folderExists) {
      console.log('[ImageLibrary] 恢复上次选择的文件夹:', savedFolder)
      activeFolder.value = savedFolder
      emit('select-folder', savedFolder)
    } else {
      // 文件夹不存在（可能已被删除），重置为全部图片并通知父组件
      console.log('[ImageLibrary] 保存的文件夹不存在，重置为全部图片')
      activeFolder.value = 'all'
      if (typeof window !== 'undefined') {
        localStorage.setItem('image-library-folder', 'all')
      }
      emit('select-folder', 'all')
    }
  } else if (savedFolder === 'recycle') {
    // 如果上次选择的是回收站，刷新后重置为全部图片
    console.log('[ImageLibrary] 上次选择的是回收站，重置为全部图片')
    activeFolder.value = 'all'
    if (typeof window !== 'undefined') {
      localStorage.setItem('image-library-folder', 'all')
    }
    emit('select-folder', 'all')
  }
}

onMounted(async () => {
  await loadAllFolders()
  // 等待文件夹加载完成后再恢复选择
  restoreFolderSelection()
})

watch(isRecycleBinView, (newVal) => {
  console.log('[ImageLibrary] isRecycleBinView changed:', newVal)
})

const refreshFolders = async () => {
  await loadAllFolders()
}

defineExpose({ refreshFolders })
</script>
