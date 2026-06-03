<template>
  <div class="preparation-view">
    <div class="preparation-view__header">
      <h1 class="preparation-view__title">预备成品</h1>
      <button class="preparation-view__sync-btn" :disabled="syncing" @click="handleSync">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'animate-spin': syncing }">
          <polyline points="23 4 23 10 17 10"></polyline>
          <polyline points="1 20 1 14 7 14"></polyline>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
        </svg>
        {{ syncing ? '同步中...' : '同步刷新' }}
      </button>
    </div>

    <div class="filter-tabs">
      <button class="filter-tabs__btn" :class="{ 'filter-tabs__btn--active': filterMode === 'preparation' }" @click="filterMode = 'preparation'">
        预成品
        <span class="filter-tabs__count">{{ preparationCount }}</span>
      </button>
      <button class="filter-tabs__btn filter-tabs__btn--usable" :class="{ 'filter-tabs__btn--active': filterMode === 'usable' }" @click="filterMode = 'usable'">
        可用
        <span class="filter-tabs__count">{{ usableCount }}</span>
      </button>
      <button class="filter-tabs__btn filter-tabs__btn--publishable" :class="{ 'filter-tabs__btn--active': filterMode === 'publishable' }" @click="filterMode = 'publishable'">
        可发布
        <span class="filter-tabs__count">{{ publishableCount }}</span>
      </button>
    </div>

    <div v-if="selectedIds.length > 0" class="batch-bar">
      <span class="batch-bar__count">
        已选 <span class="batch-bar__count-num">{{ selectedIds.length }}</span> 张
      </span>
      <div class="batch-bar__divider"></div>
      <button class="batch-bar__btn" @click="showBatchPlatform = true">批量改平台</button>
      <button class="batch-bar__btn" @click="showBatchScore = true">批量改评分</button>
      <button class="batch-bar__btn" @click="showBatchCopyText = true">批量改文案</button>
      <button class="batch-bar__btn batch-bar__btn--usable" @click="batchMarkUsable(1)">标记可用</button>
      <button class="batch-bar__btn batch-bar__btn--usable-cancel" @click="batchMarkUsable(0)">取消可用</button>
      <button class="batch-bar__btn batch-bar__btn--publishable" @click="batchMarkPublishable(1)">标记可发布</button>
      <button class="batch-bar__btn batch-bar__btn--publishable-cancel" @click="batchMarkPublishable(0)">取消可发布</button>
      <button class="batch-bar__btn batch-bar__btn--cancel" @click="clearSelection">取消选择</button>
    </div>

    <div v-if="loading" class="u-flex u-justify-center u-p-xl">
      <span class="animate-pulse" style="color: $color-text-tertiary;">加载中...</span>
    </div>

    <div v-else-if="error" class="u-flex u-justify-center u-p-xl">
      <span style="color: $color-danger;">加载失败：{{ error }}</span>
    </div>

    <div v-else-if="isCurrentFilterEmpty && filterMode !== 'publishable'" class="u-flex u-justify-center u-p-xl">
      <span style="color: $color-text-tertiary;">暂无成品图片，请将图片放入「预备」目录后点击同步刷新</span>
    </div>

    <template v-else>
      <template v-if="filterMode !== 'publishable'">
        <template v-if="activeGeneralView === 'cards'">
          <div v-for="timeGroup in groupedImages" :key="timeGroup.date" class="time-group-section">
            <div class="time-group-section__header">
              <span class="time-group-section__date">{{ timeGroup.date }}</span>
              <span class="time-group-section__stats">{{ getTimeGroupStats(timeGroup) }}</span>
            </div>
            <div class="publishable-cards-grid">
              <div
                v-for="copyGroup in timeGroup.copyGroups"
                :key="copyGroup.key"
                class="publishable-group-card"
                @click="selectGeneralGroup(copyGroup.key)"
              >
                <div class="publishable-group-card__thumbnail">
                  <img v-if="copyGroup.items.length > 0" :src="copyGroup.items[0].url" :alt="getGeneralGroupTitle(copyGroup)" loading="lazy" />
                  <div v-else class="publishable-group-card__empty-thumb">暂无图片</div>
                </div>
                <div class="publishable-group-card__info">
                  <span class="publishable-group-card__title">{{ getGeneralGroupTitle(copyGroup) }}</span>
                  <span class="publishable-group-card__count">{{ copyGroup.items.length }} 张</span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="publishable-detail-view">
            <div class="publishable-detail-header">
              <button class="publishable-detail-header__back" @click="backToGeneralCardsView">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
                返回
              </button>
              <div v-if="currentGeneralGroup && currentGeneralGroup.poster_copy" class="publishable-detail-header__toolbar">
                <button class="publishable-card__link-btn" @click="viewGroupCopy(currentGeneralGroup)">查看/修改 海报文案</button>
                <button class="publishable-card__link-btn" @click="copyGroupCopy(currentGeneralGroup)">复制海报文案</button>
                <button class="publishable-card__link-btn" @click="startEditGroupTitle(currentGeneralGroup, currentGeneralGroup.key)">改标题</button>
              </div>
            </div>
            <div class="publishable-detail-body">
              <div class="publishable-sidebar">
                <div v-for="timeGroup in groupedImages" :key="'ts-' + timeGroup.date" class="publishable-sidebar__time-group">
                  <div
                    class="publishable-sidebar__time-header"
                    :class="{ 'publishable-sidebar__time-header--collapsed': !expandedGroups[timeGroup.date] }"
                    @click="toggleGroup(timeGroup.date)"
                  >
                    <svg class="publishable-sidebar__time-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                    <span class="publishable-sidebar__time-date">{{ timeGroup.date }}</span>
                    <span class="publishable-sidebar__time-count">{{ getTimeGroupItemCount(timeGroup) }}</span>
                  </div>
                  <div v-show="expandedGroups[timeGroup.date]" class="publishable-sidebar__time-items">
                    <div
                      v-for="copyGroup in timeGroup.copyGroups"
                      :key="copyGroup.key"
                      class="publishable-sidebar__item"
                      :class="{ 'publishable-sidebar__item--active': selectedGeneralGroupKey === copyGroup.key }"
                      @click="selectGeneralGroup(copyGroup.key)"
                    >
                      <span class="publishable-sidebar__date">{{ getGeneralGroupTitle(copyGroup) }}</span>
                      <span class="publishable-sidebar__count">{{ copyGroup.items.length }} 张</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="publishable-main">
                <template v-if="selectedGeneralGroupKey && currentGeneralGroup">
                  <div class="publishable-main__header">
                    <template v-if="currentGeneralGroup.poster_copy && editingGroupTitle === currentGeneralGroup.key">
                      <input class="publishable-main__title-input" v-model="groupTitleEditValue" ref="groupTitleInputRef" @blur="saveGroupTitle(currentGeneralGroup, currentGeneralGroup.key)" @keyup.enter="$event.target.blur()" @keyup.esc="cancelEditGroupTitle(currentGeneralGroup.key)" />
                    </template>
                    <template v-else>
                      <span class="publishable-main__title" @dblclick.stop="currentGeneralGroup.poster_copy && startEditGroupTitle(currentGeneralGroup, currentGeneralGroup.key)">{{ getGeneralGroupTitle(currentGeneralGroup) }}</span>
                    </template>
                    <span class="publishable-main__count">{{ currentGeneralGroup.items.length }} 张</span>
                  </div>
                  <div v-if="currentGeneralGroup.items.length === 0" class="publishable-empty publishable-empty--inline">暂无图片</div>
                  <div v-else class="publishable-grid">
                    <div
                      v-for="item in currentGeneralGroup.items"
                      :key="item.id"
                      class="publishable-card publishable-card--general"
                      :class="{ 'publishable-card--selected': selectedIds.includes(item.id) }"
                    >
                      <div class="publishable-card__media">
                        <input type="checkbox" class="publishable-card__checkbox" :checked="selectedIds.includes(item.id)" @change="toggleSelect(item.id)" />
                        <img class="publishable-card__image" :src="item.url" :alt="item.display_name" @click="previewImage = item" loading="lazy" />
                      </div>
                      <div class="publishable-card__content">
                        <div class="publishable-card__meta publishable-card__meta--general">
                          <div class="publishable-card__field">
                            <span class="publishable-card__label">名称</span>
                            <input class="publishable-card__input" :value="item.display_name" @blur="updateField(item, 'display_name', $event.target.value)" @keyup.enter="$event.target.blur()" />
                          </div>
                          <div class="publishable-card__field">
                            <span class="publishable-card__label">编号</span>
                            <input class="publishable-card__input" :value="item.publish_code" @blur="updateField(item, 'publish_code', $event.target.value)" @keyup.enter="$event.target.blur()" placeholder="输入编号" />
                          </div>
                          <div class="publishable-card__field">
                            <span class="publishable-card__label">平台</span>
                            <input class="publishable-card__input" :value="item.platform" @blur="updateField(item, 'platform', $event.target.value)" @keyup.enter="$event.target.blur()" placeholder="如 Midjourney, DALL-E" />
                          </div>
                          <div class="publishable-card__field">
                            <span class="publishable-card__label">评分 (0-100)</span>
                            <div class="publishable-card__score-row">
                              <input type="range" class="publishable-card__score-slider" min="0" max="100" :value="item.score" @input="updateScore(item, parseInt($event.target.value))" />
                              <input class="publishable-card__score-value" type="number" min="0" max="100" :value="item.score" @blur="updateScore(item, clampScore($event.target.value))" @keyup.enter="$event.target.blur()" />
                            </div>
                          </div>
                        </div>
                        <div class="publishable-card__copy-row">
                          <div class="publishable-card__copy-block publishable-card__copy-block--poster">
                            <div class="publishable-card__copy-head">
                              <span>海报文案</span>
                              <button class="publishable-card__link-btn" @click="viewPosterCopy(item)">查看/修改</button>
                            </div>
                            <div class="publishable-card__copy">{{ item.poster_copy || '暂无' }}</div>
                          </div>
                          <div class="publishable-card__copy-block publishable-card__copy-block--prompt">
                            <div class="publishable-card__copy-head">
                              <span>生图提示词</span>
                              <button class="publishable-card__link-btn" @click="viewItemPrompt(item)">查看/修改</button>
                            </div>
                            <div class="publishable-card__copy">{{ item.copy_text || '暂无' }}</div>
                          </div>
                        </div>
                        <div class="publishable-card__actions">
                          <button class="image-card__copy-btn" @click="openImageFolder(item)">打开图片</button>
                          <button class="image-card__rename-btn" @click="showRenameDialog(item)">重命名文件</button>
                          <button class="image-card__usable-btn" :class="{ 'image-card__usable-btn--active': item.is_usable === 1 }" @click="toggleUsable(item)">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                            {{ item.is_usable === 1 ? '可用' : '标记可用' }}
                          </button>
                          <button class="image-card__publishable-btn" :class="{ 'image-card__publishable-btn--active': item.is_publishable === 1 }" @click="togglePublishable(item)">
                            {{ item.is_publishable === 1 ? '可发布' : '标记可发布' }}
                          </button>
                          <button class="image-card__delete-btn" @click="confirmDelete(item)">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <polyline points="3 6 5 6 21 6"></polyline>
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
                <div v-else class="publishable-empty">请选择一个分组</div>
              </div>
            </div>
          </div>
        </template>
      </template>
      <template v-else>
        <!-- 可发布：分组卡片总览视图（默认） -->
        <template v-if="activePublishableView === 'cards'">
          <div class="publishable-toolbar">
            <button class="publishable-toolbar__btn" :disabled="creatingPublishGroup" @click="openPublishDateDialog">新建日期分组</button>
          </div>
          <div v-if="publishableGroupedByDay.length === 0" class="publishable-empty">暂无日期分组</div>
          <div v-else class="publishable-cards-grid">
            <div
              v-for="group in publishableGroupedByDay"
              :key="group.day"
              class="publishable-group-card"
              :class="{ 'publishable-group-card--drag-over': dragOverPublishDate === group.day }"
              @dragover.prevent="handlePublishDragOver(group.day)"
              @dragleave="handlePublishDragLeave(group.day)"
              @drop.prevent="handlePublishDrop(group.day)"
              @click="selectPublishGroup(group.day)"
            >
              <div class="publishable-group-card__thumbnail">
                <img v-if="group.items.length > 0" :src="group.items[0].url" :alt="group.day" loading="lazy" />
                <div v-else class="publishable-group-card__empty-thumb">暂无图片</div>
              </div>
              <div class="publishable-group-card__info">
                <span class="publishable-group-card__title">{{ group.day }}</span>
                <span class="publishable-group-card__count">{{ group.items.length }} 张</span>
              </div>
            </div>
          </div>
        </template>

        <!-- 可发布：侧边栏详情视图 -->
        <template v-else>
          <div class="publishable-detail-view">
            <div class="publishable-detail-header">
              <button class="publishable-detail-header__back" @click="backToCardsView">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
                返回
              </button>
              <div class="publishable-detail-header__toolbar">
                <button class="publishable-toolbar__btn" :disabled="creatingPublishGroup" @click="openPublishDateDialog">新建日期分组</button>
              </div>
            </div>
            <div class="publishable-detail-body">
              <div class="publishable-sidebar">
                <div
                  v-for="group in publishableGroupedByDay"
                  :key="group.day"
                  class="publishable-sidebar__item"
                  :class="{
                    'publishable-sidebar__item--active': selectedPublishGroup === group.day,
                    'publishable-sidebar__item--drag-over': dragOverPublishDate === group.day
                  }"
                  @click="selectPublishGroup(group.day)"
                  @dragover.prevent="handlePublishDragOver(group.day)"
                  @dragleave="handlePublishDragLeave(group.day)"
                  @drop.prevent="handlePublishDrop(group.day)"
                >
                  <span class="publishable-sidebar__date">{{ group.day }}</span>
                  <span class="publishable-sidebar__count">{{ group.items.length }} 张</span>
                </div>
              </div>
              <div class="publishable-main">
                <template v-if="selectedPublishGroup && currentDetailGroup">
                  <div class="publishable-main__header">
                    <span class="publishable-main__title">{{ currentDetailGroup.day }}</span>
                    <span class="publishable-main__count">{{ currentDetailGroup.items.length }} 张</span>
                    <button
                      class="publishable-main__compress-btn"
                      :disabled="compressingPublishGroup === currentDetailGroup.day || currentDetailGroup.items.length === 0"
                      @click="compressCurrentPublishGroup"
                    >
                      {{ compressingPublishGroup === currentDetailGroup.day ? '压缩中...' : '压缩当前分组' }}
                    </button>
                  </div>
                  <div v-if="currentDetailGroup.items.length === 0" class="publishable-empty publishable-empty--inline">暂无图片</div>
                  <div v-else class="publishable-grid">
                    <div
                      v-for="item in currentDetailGroup.items"
                      :key="item.id"
                      class="publishable-card"
                      :class="{ 'publishable-card--selected': selectedIds.includes(item.id), 'publishable-card--dragging': draggingPublishItemId === item.id }"
                      draggable="true"
                      @dragstart="handlePublishDragStart(item, $event)"
                      @dragend="handlePublishDragEnd"
                    >
                      <div class="publishable-card__media">
                        <input type="checkbox" class="publishable-card__checkbox" :checked="selectedIds.includes(item.id)" @change="toggleSelect(item.id)" />
                        <img class="publishable-card__image" :src="item.url" :alt="item.display_name" @click="previewImage = item" loading="lazy" />
                      </div>
                      <div class="publishable-card__content">
                        <div class="publishable-card__meta">
                          <div class="publishable-card__field">
                            <span class="publishable-card__label">编号</span>
                            <input class="publishable-card__input" :value="item.publish_code" @blur="updateField(item, 'publish_code', $event.target.value)" @keyup.enter="$event.target.blur()" placeholder="输入编号" />
                          </div>
                          <div class="publishable-card__field">
                            <span class="publishable-card__label">文件名</span>
                            <input class="publishable-card__input" :value="item.filename"
                                   @blur="renameInline(item, $event.target.value, $event)"
                                   @keyup.enter="$event.target.blur()" />
                          </div>
                          <div class="publishable-card__field">
                            <span class="publishable-card__label">负责人</span>
                            <input class="publishable-card__input" :value="item.person_in_charge" @blur="updateField(item, 'person_in_charge', $event.target.value)" @keyup.enter="$event.target.blur()" placeholder="自动分配" />
                          </div>
                        </div>
                        <div class="publishable-card__copy-row">
                          <div class="publishable-card__copy-block publishable-card__copy-block--poster">
                            <div class="publishable-card__copy-head">
                              <span>海报文案</span>
                              <button class="publishable-card__link-btn" @click="viewPosterCopy(item)">查看/修改</button>
                            </div>
                            <div class="publishable-card__copy">{{ item.poster_copy || '暂无' }}</div>
                          </div>
                          <div class="publishable-card__copy-block publishable-card__copy-block--prompt">
                            <div class="publishable-card__copy-head">
                              <span>生图提示词</span>
                              <button class="publishable-card__link-btn" @click="viewItemPrompt(item)">查看/修改</button>
                            </div>
                            <div class="publishable-card__copy">{{ item.copy_text || '暂无' }}</div>
                          </div>
                        </div>
                        <div class="publishable-card__copy-block publishable-card__copy-block--social">
                          <div class="publishable-card__copy-head">
                            <span>朋友圈文案</span>
                            <div class="publishable-card__copy-actions">
                              <button class="publishable-card__link-btn" :disabled="!item.social_copy" @click="openMomentsPreview(item)">查看</button>
                              <button class="publishable-card__link-btn" :disabled="!item.social_copy" @click="copyText(item.social_copy, '朋友圈文案')">复制</button>
                            </div>
                          </div>
                          <div class="publishable-card__social-copy">{{ item.social_copy || '尚未生成朋友圈文案' }}</div>
                        </div>
                        <div class="publishable-card__actions">
                          <button class="image-card__copy-btn" @click="openImageFolder(item)">打开图片</button>
                          <button class="publishable-card__generate-btn" :disabled="isGeneratingSocialCopy(item.id)" @click="generateSocialCopyForItem(item)">
                            {{ isGeneratingSocialCopy(item.id) ? '生成中...' : (item.social_copy ? '重新生成' : '生成文案') }}
                          </button>
                          <button class="publishable-card__edit-btn" @click="openSocialCopyEdit(item)">编辑文案</button>
                          <button class="image-card__publishable-btn image-card__publishable-btn--active" @click="togglePublishable(item)">取消发布</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
                <div v-else class="publishable-empty">请选择一个分组</div>
              </div>
            </div>
          </div>
        </template>
      </template>
    </template>

    <div v-if="previewImage" class="preview-overlay" @click.self="previewImage = null">
      <div class="preview-modal">
        <button class="preview-modal__close" @click="previewImage = null">&times;</button>
        <img class="preview-modal__image" :src="previewImage.url" :alt="previewImage.display_name" />
        <div class="preview-modal__info">{{ previewImage.display_name }}</div>
      </div>
    </div>

    <div v-if="showRenameItem" class="preview-overlay" @click.self="showRenameItem = null">
      <div class="rename-dialog">
        <h3 class="rename-dialog__title">重命名文件</h3>
        <p class="rename-dialog__old-name">原文件名：{{ showRenameItem.filename }}</p>
        <input class="rename-dialog__input" v-model="renameNewName" placeholder="输入新文件名（含扩展名）" @keyup.enter="confirmRename" />
        <div class="rename-dialog__actions">
          <button class="rename-dialog__btn rename-dialog__btn--cancel" @click="showRenameItem = null">取消</button>
          <button class="rename-dialog__btn rename-dialog__btn--confirm" @click="confirmRename" :disabled="renaming">确定</button>
        </div>
      </div>
    </div>

    <div v-if="showBatchPlatform" class="preview-overlay" @click.self="showBatchPlatform = false">
      <div class="batch-dialog">
        <h3 class="batch-dialog__title">批量修改平台</h3>
        <input class="batch-dialog__input" v-model="batchPlatformValue" placeholder="输入平台名称，如 Midjourney" @keyup.enter="confirmBatchPlatform" />
        <div class="batch-dialog__actions">
          <button class="batch-dialog__btn batch-dialog__btn--cancel" @click="showBatchPlatform = false">取消</button>
          <button class="batch-dialog__btn batch-dialog__btn--confirm" @click="confirmBatchPlatform" :disabled="batchUpdating">确定</button>
        </div>
      </div>
    </div>

    <div v-if="showBatchScore" class="preview-overlay" @click.self="showBatchScore = false">
      <div class="batch-dialog">
        <h3 class="batch-dialog__title">批量修改评分</h3>
        <div class="batch-dialog__score-row">
          <input type="range" class="batch-dialog__slider" min="0" max="100" v-model.number="batchScoreValue" />
          <input class="batch-dialog__score-input" type="number" min="0" max="100" v-model.number="batchScoreValue" />
        </div>
        <div class="batch-dialog__actions">
          <button class="batch-dialog__btn batch-dialog__btn--cancel" @click="showBatchScore = false">取消</button>
          <button class="batch-dialog__btn batch-dialog__btn--confirm" @click="confirmBatchScore" :disabled="batchUpdating">确定</button>
        </div>
      </div>
    </div>

    <div v-if="showBatchCopyText" class="preview-overlay" @click.self="showBatchCopyText = false">
      <div class="batch-dialog">
        <h3 class="batch-dialog__title">批量修改文案分组</h3>
        <input class="batch-dialog__input" v-model="batchCopyTextValue" placeholder="输入文案内容" @keyup.enter="confirmBatchCopyText" />
        <div class="batch-dialog__actions">
          <button class="batch-dialog__btn batch-dialog__btn--cancel" @click="showBatchCopyText = false">取消</button>
          <button class="batch-dialog__btn batch-dialog__btn--confirm" @click="confirmBatchCopyText" :disabled="batchUpdating">确定</button>
        </div>
      </div>
    </div>

    <div v-if="showGroupCopyDialog" class="preview-overlay">
      <div class="group-copy-dialog">
        <div class="group-copy-dialog__split">
          <div class="group-copy-dialog__panel">
            <div class="group-copy-dialog__label">文案编辑</div>
            <textarea class="group-copy-dialog__textarea" v-model="groupCopyEditText" rows="8"></textarea>
          </div>
          <div class="group-copy-dialog__panel">
            <div class="group-copy-dialog__label">预览</div>
            <div class="group-copy-dialog__preview" v-html="renderMarkdown(groupCopyEditText)"></div>
          </div>
        </div>
        <div class="group-copy-dialog__actions">
          <button class="group-copy-dialog__btn group-copy-dialog__btn--save" @click="saveGroupCopyEdit" :disabled="savingCopyText">保存</button>
          <button class="group-copy-dialog__btn group-copy-dialog__btn--cancel" @click="closeGroupCopyDialog">关闭</button>
        </div>
      </div>
    </div>
    <div v-if="showPosterCopyDialog" class="preview-overlay" @click.self="closePosterCopyDialog">
      <div class="social-copy-dialog">
        <h3 class="social-copy-dialog__title">海报文案</h3>
        <textarea class="social-copy-dialog__textarea" v-model="posterCopyEditText" rows="10" placeholder="输入海报文案"></textarea>
        <div class="social-copy-dialog__actions">
          <button class="batch-dialog__btn batch-dialog__btn--cancel" @click="closePosterCopyDialog">取消</button>
          <button class="batch-dialog__btn batch-dialog__btn--confirm" @click="savePosterCopy" :disabled="savingPosterCopy">{{ savingPosterCopy ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>
    <div v-if="showSocialCopyDialog" class="preview-overlay" @click.self="closeSocialCopyDialog">
      <div class="social-copy-dialog">
        <h3 class="social-copy-dialog__title">朋友圈文案</h3>
        <textarea class="social-copy-dialog__textarea" v-model="socialCopyEditText" rows="10" placeholder="输入朋友圈文案"></textarea>
        <div class="social-copy-dialog__actions">
          <button class="batch-dialog__btn batch-dialog__btn--cancel" @click="closeSocialCopyDialog">取消</button>
          <button class="batch-dialog__btn batch-dialog__btn--confirm" @click="saveSocialCopyEdit" :disabled="savingSocialCopy">保存</button>
        </div>
      </div>
    </div>
    <div v-if="showMomentsPreviewDialog" class="preview-overlay" @click.self="closeMomentsPreview">
      <div class="moments-preview-dialog">
        <div class="moments-preview-dialog__header">
          <h3 class="moments-preview-dialog__title">朋友圈排版预览</h3>
          <button class="moments-preview-dialog__close" type="button" @click="closeMomentsPreview" aria-label="关闭">&times;</button>
        </div>
        <div class="moments-preview-dialog__phones">
          <section class="moments-phone moments-phone--android" aria-label="Android 微信朋友圈预览">
            <div class="moments-phone__label">Android 基准</div>
            <div class="moments-phone__screen">
              <div class="moments-phone__status moments-phone__status--android">
                <span>14:45</span>
                <span>5G&nbsp;&nbsp;WiFi&nbsp;&nbsp;95</span>
              </div>
              <div class="moments-phone__cover">
                <div class="moments-phone__nav">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                    <polyline points="15 18 9 12 15 6"></polyline>
                  </svg>
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M9 4 7.2 6H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-3.2L15 4H9Zm3 14a5 5 0 1 1 0-10 5 5 0 0 1 0 10Z" />
                  </svg>
                </div>
                <div class="moments-phone__profile">
                  <span class="moments-phone__profile-name">默默</span>
                  <img class="moments-phone__profile-avatar" :src="momentsPreviewTargetItem?.url" :alt="momentsPreviewTargetItem?.display_name || '头像'" />
                </div>
              </div>
              <article class="moments-post">
                <img class="moments-post__avatar" :src="momentsPreviewTargetItem?.url" :alt="momentsPreviewTargetItem?.display_name || '头像'" />
                <div class="moments-post__body">
                  <div class="moments-post__name">默默</div>
                  <div class="moments-post__text">{{ momentsPreviewTargetItem?.social_copy }}</div>
                  <div class="moments-post__footer">
                    <span>1分钟前</span>
                    <button type="button" aria-label="更多">··</button>
                  </div>
                </div>
              </article>
            </div>
          </section>
          <section class="moments-phone moments-phone--iphone" aria-label="iPhone 微信朋友圈预览">
            <div class="moments-phone__label">iPhone 基准</div>
            <div class="moments-phone__screen">
              <div class="moments-phone__status moments-phone__status--iphone">
                <span>14:45</span>
                <span>5G&nbsp;&nbsp;95%</span>
              </div>
              <div class="moments-phone__cover">
                <div class="moments-phone__nav">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                    <polyline points="15 18 9 12 15 6"></polyline>
                  </svg>
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M9 4 7.2 6H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-3.2L15 4H9Zm3 14a5 5 0 1 1 0-10 5 5 0 0 1 0 10Z" />
                  </svg>
                </div>
                <div class="moments-phone__profile">
                  <span class="moments-phone__profile-name">默默</span>
                  <img class="moments-phone__profile-avatar" :src="momentsPreviewTargetItem?.url" :alt="momentsPreviewTargetItem?.display_name || '头像'" />
                </div>
              </div>
              <article class="moments-post">
                <img class="moments-post__avatar" :src="momentsPreviewTargetItem?.url" :alt="momentsPreviewTargetItem?.display_name || '头像'" />
                <div class="moments-post__body">
                  <div class="moments-post__name">默默</div>
                  <div class="moments-post__text">{{ momentsPreviewTargetItem?.social_copy }}</div>
                  <div class="moments-post__footer">
                    <span>1分钟前</span>
                    <button type="button" aria-label="更多">··</button>
                  </div>
                </div>
              </article>
            </div>
          </section>
        </div>
      </div>
    </div>
    <ConfirmDialog
      v-model:visible="showDeleteDialog"
      title="删除确认"
      :message="deleteDialogMessage"
      confirm-text="删除"
      cancel-text="取消"
      :danger="true"
      @confirm="handleDeleteConfirm"
    />
    <ConfirmDialog
      v-model:visible="showNotificationDialog"
      :title="notificationDialogTitle"
      :message="notificationDialogMessage"
      confirm-text="确定"
      cancel-text=""
      :danger="notificationDialogDanger"
    />
    <ConfirmDialog
      v-model:visible="showRegenerateSocialCopyDialog"
      title="重新生成文案"
      message="当前图片已有朋友圈文案，重新生成会覆盖现有内容。确定继续吗？"
      confirm-text="重新生成"
      cancel-text="取消"
      @confirm="handleRegenerateSocialCopyConfirm"
    />

    <div v-if="showPublishDateDialog" class="preview-overlay" @click.self="closePublishDateDialog">
      <div class="publish-date-dialog">
        <h3 class="publish-date-dialog__title">新建日期分组</h3>
        <input class="publish-date-dialog__input" type="date" v-model="newPublishDate" @keyup.enter="handleCreatePublishGroup" />
        <div class="publish-date-dialog__actions">
          <button class="batch-dialog__btn batch-dialog__btn--cancel" @click="closePublishDateDialog">取消</button>
          <button class="batch-dialog__btn batch-dialog__btn--confirm" @click="handleCreatePublishGroup" :disabled="creatingPublishGroup">
            {{ creatingPublishGroup ? '创建中...' : '确定' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import {
  getPreparationList,
  updatePreparationItem,
  batchUpdatePreparationItems,
  renamePreparationItem,
  syncPreparation,
  deletePreparationItem,
  generateSocialCopy,
  openPreparationFolder,
  getPublishGroups,
  createPublishGroup,
  movePublishGroup,
  compressPublishGroup
} from '@/services/api'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'

const images = ref([])
const loading = ref(true)
const error = ref(null)
const syncing = ref(false)
const expandedGroups = ref({})
const expandedPublishableGroups = ref({})
const savedFilterMode = localStorage.getItem('preparation_filter_mode')
const filterMode = ref(savedFilterMode && ['preparation', 'usable', 'publishable'].includes(savedFilterMode) ? savedFilterMode : 'preparation')

watch(filterMode, (val) => {
  localStorage.setItem('preparation_filter_mode', val)
  backToGeneralCardsView()
  backToCardsView()
})
const publishGroups = ref([])
const newPublishDate = ref(new Date().toISOString().slice(0, 10))
const creatingPublishGroup = ref(false)
const draggingPublishItemId = ref(null)
const dragOverPublishDate = ref('')
const activeGeneralView = ref('cards')
const selectedGeneralGroupKey = ref('')
const activePublishableView = ref('cards')
const selectedPublishGroup = ref('')
const showPublishDateDialog = ref(false)
const compressingPublishGroup = ref('')

const selectedIds = ref([])
const showRenameItem = ref(null)
const renameNewName = ref('')
const renaming = ref(false)

const showBatchPlatform = ref(false)
const showBatchScore = ref(false)
const showBatchCopyText = ref(false)
const batchUpdating = ref(false)
const batchPlatformValue = ref('')
const batchScoreValue = ref(50)
const batchCopyTextValue = ref('')

const previewImage = ref(null)

const showDeleteDialog = ref(false)
const deleteDialogMessage = ref('')
const deleteTargetItem = ref(null)

const showNotificationDialog = ref(false)
const notificationDialogTitle = ref('')
const notificationDialogMessage = ref('')
const notificationDialogDanger = ref(false)

const editingGroupTitle = ref(-1)
const groupTitleEditValue = ref('')
const groupTitleInputRef = ref(null)

const showGroupCopyDialog = ref(false)
const groupCopyEditText = ref('')
const groupCopyTargetGroup = ref(null)
const groupCopyTargetItem = ref(null)
const savingCopyText = ref(false)

const showPosterCopyDialog = ref(false)
const posterCopyEditText = ref('')
const posterCopyTargetItem = ref(null)
const savingPosterCopy = ref(false)

const generatingSocialCopyIds = ref([])
const showRegenerateSocialCopyDialog = ref(false)
const regenerateSocialCopyTarget = ref(null)
const showSocialCopyDialog = ref(false)
const socialCopyEditText = ref('')
const socialCopyTargetItem = ref(null)
const savingSocialCopy = ref(false)
const showMomentsPreviewDialog = ref(false)
const momentsPreviewTargetItem = ref(null)

const handleGroupCopyKeydown = (e) => {
  if (e.key === 'Escape' && showGroupCopyDialog.value) {
    closeGroupCopyDialog()
  }
}

const handlePosterCopyKeydown = (e) => {
  if (e.key === 'Escape' && showPosterCopyDialog.value) {
    closePosterCopyDialog()
  }
}

const handleMomentsPreviewKeydown = (e) => {
  if (e.key === 'Escape' && showMomentsPreviewDialog.value) {
    closeMomentsPreview()
  }
}

watch(showGroupCopyDialog, (val) => {
  if (val) {
    document.addEventListener('keydown', handleGroupCopyKeydown)
  } else {
    document.removeEventListener('keydown', handleGroupCopyKeydown)
  }
})

watch(showPosterCopyDialog, (val) => {
  if (val) {
    document.addEventListener('keydown', handlePosterCopyKeydown)
  } else {
    document.removeEventListener('keydown', handlePosterCopyKeydown)
  }
})

watch(showMomentsPreviewDialog, (val) => {
  if (val) {
    document.addEventListener('keydown', handleMomentsPreviewKeydown)
  } else {
    document.removeEventListener('keydown', handleMomentsPreviewKeydown)
  }
})

const usableCount = computed(() => {
  return images.value.filter(i => i.is_usable === 1).length
})

const preparationCount = computed(() => {
  return images.value.filter(i => i.is_usable !== 1 && !isPublishedPreparationItem(i)).length
})

const publishableImages = computed(() => {
  return images.value.filter(i => i.is_usable === 1 && i.is_publishable === 1)
})

const publishableCount = computed(() => {
  return publishableImages.value.length
})

function isPublishFolderItem(item) {
  const folderPath = (item.folder_path || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
  return /^可发布\/\d{4}-\d{2}-\d{2}$/.test(folderPath)
}

function isPublishedPreparationItem(item) {
  return item.is_publishable === 1 || !!item.publish_date || isPublishFolderItem(item)
}

const filteredImages = computed(() => {
  if (filterMode.value === 'preparation') {
    return images.value.filter(i => i.is_usable !== 1 && !isPublishedPreparationItem(i))
  }
  if (filterMode.value === 'usable') {
    return images.value.filter(i => i.is_usable === 1 && !isPublishedPreparationItem(i))
  }
  if (filterMode.value === 'publishable') {
    return publishableImages.value
  }
  return images.value.filter(i => !isPublishedPreparationItem(i))
})

// 按时间（created_at的日期部分）→ 文案（poster_copy）两级分组
const groupedImages = computed(() => {
  const timeGroups = {}
  for (const item of filteredImages.value) {
    const date = (item.created_at || '').slice(0, 10) || '未知日期'
    if (!timeGroups[date]) {
      timeGroups[date] = { date, copyGroupsMap: {} }
    }
    const copyKey = item.poster_copy || ''
    if (!timeGroups[date].copyGroupsMap[copyKey]) {
      timeGroups[date].copyGroupsMap[copyKey] = {
        key: `poster:${copyKey}`,
        poster_copy: copyKey,
        copy_title: item.copy_title || '',
        items: []
      }
    } else {
      if (item.copy_title && !timeGroups[date].copyGroupsMap[copyKey].copy_title) {
        timeGroups[date].copyGroupsMap[copyKey].copy_title = item.copy_title
      }
    }
    timeGroups[date].copyGroupsMap[copyKey].items.push(item)
  }
  const sorted = Object.entries(timeGroups).sort((a, b) => {
    if (a[0] === '未知日期') return 1
    if (b[0] === '未知日期') return -1
    return b[0].localeCompare(a[0])
  })
  return sorted.map(([date, tg]) => {
    const copyGroups = Object.values(tg.copyGroupsMap).sort((a, b) => {
      if (!a.poster_copy) return 1
      if (!b.poster_copy) return -1
      return a.poster_copy.localeCompare(b.poster_copy, 'zh-CN')
    })
    return { date, copyGroups }
  })
})

// 将所有时间分组内的文案分组展平为一维数组，供查找使用
const flatCopyGroups = computed(() => {
  const result = []
  for (const timeGroup of groupedImages.value) {
    for (const copyGroup of timeGroup.copyGroups) {
      result.push(copyGroup)
    }
  }
  return result
})

const publishableGroupedByDay = computed(() => {
  const groups = {}
  for (const day of publishGroups.value) {
    if (day) groups[day] = { day, items: [] }
  }
  for (const item of publishableImages.value) {
    const day = item.publish_date || (item.created_at || '').slice(0, 10) || '未知日期'
    if (!groups[day]) {
      groups[day] = { day, items: [] }
    }
    groups[day].items.push(item)
  }
  return Object.values(groups).sort((a, b) => b.day.localeCompare(a.day))
})

const currentDetailGroup = computed(() => {
  if (!selectedPublishGroup.value) return null
  return publishableGroupedByDay.value.find(g => g.day === selectedPublishGroup.value) || null
})

const currentGeneralGroup = computed(() => {
  if (!selectedGeneralGroupKey.value) return null
  const matchingGroups = flatCopyGroups.value.filter(g => g.key === selectedGeneralGroupKey.value)
  if (matchingGroups.length === 0) return null
  const mergedItems = matchingGroups.flatMap(g => g.items)
  return {
    key: matchingGroups[0].key,
    poster_copy: matchingGroups[0].poster_copy,
    copy_title: matchingGroups.find(g => g.copy_title)?.copy_title || '',
    items: mergedItems
  }
})

const isCurrentFilterEmpty = computed(() => {
  if (filterMode.value === 'publishable') {
    return publishableGroupedByDay.value.length === 0
  }
  return flatCopyGroups.value.length === 0
})

function toggleGroup(date) {
  expandedGroups.value[date] = !expandedGroups.value[date]
}

function togglePublishableGroup(day) {
  expandedPublishableGroups.value[day] = !expandedPublishableGroups.value[day]
}

function selectGeneralGroup(key) {
  if (activeGeneralView.value === 'detail' && selectedGeneralGroupKey.value === key) {
    backToGeneralCardsView()
    return
  }
  selectedGeneralGroupKey.value = key
  activeGeneralView.value = 'detail'
}

function backToGeneralCardsView() {
  activeGeneralView.value = 'cards'
  selectedGeneralGroupKey.value = ''
}

function selectPublishGroup(day) {
  if (activePublishableView.value === 'detail' && selectedPublishGroup.value === day) {
    backToCardsView()
    return
  }
  selectedPublishGroup.value = day
  activePublishableView.value = 'detail'
}

function backToCardsView() {
  activePublishableView.value = 'cards'
  selectedPublishGroup.value = ''
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) {
    selectedIds.value.push(id)
  } else {
    selectedIds.value.splice(idx, 1)
  }
}

function clearSelection() {
  selectedIds.value = []
}

function clampScore(val) {
  const num = parseInt(val)
  if (isNaN(num)) return 0
  return Math.max(0, Math.min(100, num))
}

function startEditGroupTitle(group, index) {
  editingGroupTitle.value = index
  groupTitleEditValue.value = group.copy_title || ''
  nextTick(() => {
    const input = document.querySelector('.publishable-main__title-input, .group-section__title-input')
    if (input) input.focus()
  })
}

function cancelEditGroupTitle(index) {
  if (editingGroupTitle.value !== index) return
  editingGroupTitle.value = -1
}

async function saveGroupTitle(group, index) {
  if (editingGroupTitle.value !== index) return
  editingGroupTitle.value = -1
  const newTitle = groupTitleEditValue.value.trim()
  if (!newTitle) return
  if (newTitle === group.copy_title) return
  try {
    const ids = group.items.map(item => item.id)
    const res = await batchUpdatePreparationItems(ids, { copy_title: newTitle })
    if (res && res.success === false) {
      console.error('更新标题失败:', res.error)
      return
    }
    for (const item of group.items) {
      item.copy_title = newTitle
    }
    group.copy_title = newTitle
  } catch (e) {
    console.error('更新标题失败:', e)
  }
}

async function toggleUsable(item) {
  const newVal = item.is_usable === 1 ? 0 : 1
  const previous = { ...item }
  item.is_usable = newVal
  if (newVal === 0) {
    item.is_publishable = 0
  }
  try {
    const payload = newVal === 0 ? { is_usable: 0, is_publishable: 0 } : { is_usable: 1 }
    const res = await updatePreparationItem(item.id, payload)
    if (res?.item) Object.assign(item, normalizePreparationImage(res.item))
  } catch (e) {
    Object.assign(item, previous)
    console.error('更新可用状态失败:', e)
  }
}

async function togglePublishable(item) {
  const newVal = item.is_publishable === 1 ? 0 : 1
  const previous = { ...item }
  item.is_publishable = newVal
  if (newVal === 1) {
    item.is_usable = 1
  }
  try {
    const payload = newVal === 1
      ? { is_publishable: 1, is_usable: 1 }
      : { is_publishable: 0 }
    const res = await updatePreparationItem(item.id, payload)
    if (res?.item) {
      Object.assign(item, normalizePreparationImage(res.item))
      if (item.publish_date && !publishGroups.value.includes(item.publish_date)) {
        publishGroups.value.push(item.publish_date)
        publishGroups.value.sort((a, b) => b.localeCompare(a))
      }
      ensurePublishGroupExpanded()
    }
  } catch (e) {
    Object.assign(item, previous)
    showNotification('更新失败', '更新可发布状态失败：' + (e.message || '未知错误'), true)
  }
}

async function batchMarkUsable(value) {
  if (selectedIds.value.length === 0) return
  try {
    const updates = value === 0 ? { is_usable: 0, is_publishable: 0 } : { is_usable: 1 }
    await batchUpdatePreparationItems(selectedIds.value, updates)
    await loadImages()
  } catch (e) {
    showNotification('批量更新失败', '批量更新可用状态失败：' + (e.message || '未知错误'), true)
  }
}

async function batchMarkPublishable(value) {
  if (selectedIds.value.length === 0) return
  try {
    const updates = value === 1
      ? { is_usable: 1, is_publishable: 1 }
      : { is_publishable: 0 }
    await batchUpdatePreparationItems(selectedIds.value, updates)
    await loadImages()
  } catch (e) {
    showNotification('批量更新失败', '批量更新可发布状态失败：' + (e.message || '未知错误'), true)
  }
}

function showNotification(title, message, danger = false) {
  notificationDialogTitle.value = title
  notificationDialogMessage.value = message
  notificationDialogDanger.value = danger
  showNotificationDialog.value = true
}

function normalizePreparationImage(img) {
  return {
    ...img,
    folder_path: img.folder_path || '',
    relative_path: img.relative_path || img.filename,
    publish_date: img.publish_date || '',
    is_publishable: img.is_publishable || 0,
    social_copy: img.social_copy || '',
    publish_code: img.publish_code || '',
    poster_copy: img.poster_copy || '',
    copy_text: img.copy_text || '',
    _saving: {}
  }
}

function ensurePublishGroupExpanded() {
  for (const group of publishableGroupedByDay.value) {
    if (expandedPublishableGroups.value[group.day] === undefined) {
      expandedPublishableGroups.value[group.day] = true
    }
  }
}

async function refreshPublishGroups() {
  const res = await getPublishGroups()
  publishGroups.value = res.groups || []
  ensurePublishGroupExpanded()
}

async function handleCreatePublishGroup() {
  if (!newPublishDate.value || creatingPublishGroup.value) return
  creatingPublishGroup.value = true
  try {
    const res = await createPublishGroup(newPublishDate.value)
    const day = res.publish_date || newPublishDate.value
    if (!publishGroups.value.includes(day)) {
      publishGroups.value.push(day)
      publishGroups.value.sort((a, b) => b.localeCompare(a))
    }
    expandedPublishableGroups.value[day] = true
    closePublishDateDialog()
    selectPublishGroup(day)
  } catch (e) {
    showNotification('创建失败', '创建日期分组失败：' + (e.message || '未知错误'), true)
  } finally {
    creatingPublishGroup.value = false
  }
}

function openPublishDateDialog() {
  newPublishDate.value = new Date().toISOString().slice(0, 10)
  showPublishDateDialog.value = true
}

function closePublishDateDialog() {
  showPublishDateDialog.value = false
}

function handlePublishDragStart(item, event) {
  draggingPublishItemId.value = item.id
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', item.id)
}

function handlePublishDragEnd() {
  draggingPublishItemId.value = null
  dragOverPublishDate.value = ''
}

function handlePublishDragOver(day) {
  if (draggingPublishItemId.value) {
    dragOverPublishDate.value = day
  }
}

function handlePublishDragLeave(day) {
  if (dragOverPublishDate.value === day) {
    dragOverPublishDate.value = ''
  }
}

async function handlePublishDrop(day) {
  const itemId = draggingPublishItemId.value
  draggingPublishItemId.value = null
  dragOverPublishDate.value = ''
  if (!itemId) return
  const item = images.value.find(i => i.id === itemId)
  if (!item || item.publish_date === day) return
  const previous = { ...item }
  item.publish_date = day
  item.folder_path = `可发布/${day}`
  try {
    const res = await movePublishGroup(itemId, day)
    if (res?.item) {
      Object.assign(item, normalizePreparationImage(res.item))
    }
    if (!publishGroups.value.includes(day)) {
      publishGroups.value.push(day)
      publishGroups.value.sort((a, b) => b.localeCompare(a))
    }
    expandedPublishableGroups.value[day] = true
    selectPublishGroup(day)
  } catch (e) {
    Object.assign(item, previous)
    showNotification('移动失败', '移动到日期分组失败：' + (e.message || '未知错误'), true)
  }
}

async function compressCurrentPublishGroup() {
  const group = currentDetailGroup.value
  if (!group || !group.day || compressingPublishGroup.value) return
  compressingPublishGroup.value = group.day
  try {
    const res = await compressPublishGroup(group.day)
    for (const updatedItem of res.items || []) {
      const index = images.value.findIndex(item => item.id === updatedItem.id)
      if (index !== -1) {
        images.value[index] = {
          ...images.value[index],
          ...normalizePreparationImage(updatedItem)
        }
      }
    }
    const failedCount = res.failed_count || 0
    const compressedCount = res.compressed_count || 0
    if (failedCount > 0) {
      showNotification('压缩完成', `成功压缩 ${compressedCount} 张，失败 ${failedCount} 张`, true)
    } else {
      showNotification('压缩完成', `已压缩 ${compressedCount} 张图片到 1MB 以内`)
    }
  } catch (e) {
    showNotification('压缩失败', '压缩当前分组失败：' + (e.message || '未知错误'), true)
  } finally {
    compressingPublishGroup.value = ''
  }
}

async function confirmDelete(item) {
  deleteTargetItem.value = item
  deleteDialogMessage.value = `确定删除"${item.display_name}"？\n将同时删除实际文件。`
  showDeleteDialog.value = true
}

async function handleDeleteConfirm() {
  const item = deleteTargetItem.value
  if (!item) return
  try {
    await deletePreparationItem(item.id)
    const idx = images.value.findIndex(i => i.id === item.id)
    if (idx !== -1) images.value.splice(idx, 1)
  } catch (e) {
    console.error('删除失败:', e)
  } finally {
    deleteTargetItem.value = null
  }
}

function getItemGroup(item) {
  return flatCopyGroups.value.find(g => g.items.includes(item)) || null
}

function getGeneralGroupTitle(group) {
  if (!group) return ''
  if (!group.poster_copy) return '未分组'
  return group.copy_title || getCopyPreview(group.poster_copy) || '未命名'
}

function getCopyPreview(text) {
  if (!text) return '无文案'
  const firstLine = text.split('\n')[0]
  return firstLine.length > 30 ? firstLine.substring(0, 30) + '...' : firstLine
}

// 统计时间分组内的文案组数量和图片总数
function getTimeGroupStats(timeGroup) {
  const groupCount = timeGroup.copyGroups.length
  const imageCount = timeGroup.copyGroups.reduce((sum, g) => sum + g.items.length, 0)
  return `${groupCount} 个文案组 · ${imageCount} 张图片`
}

// 统计时间分组内的图片总数
function getTimeGroupItemCount(timeGroup) {
  return timeGroup.copyGroups.reduce((sum, g) => sum + g.items.length, 0)
}

function viewGroupCopy(group) {
  if (!group) return
  groupCopyTargetGroup.value = group
  groupCopyTargetItem.value = null
  groupCopyEditText.value = group.poster_copy
  showGroupCopyDialog.value = true
}

function copyGroupCopy(group) {
  copyText(group.poster_copy, '海报文案')
}

function editGroupCopy(group) {
  groupCopyTargetGroup.value = group
  groupCopyTargetItem.value = null
  groupCopyEditText.value = group.poster_copy
  showGroupCopyDialog.value = true
}

function viewItemPrompt(item) {
  if (!item) return
  groupCopyTargetItem.value = item
  groupCopyTargetGroup.value = null
  groupCopyEditText.value = item.copy_text || ''
  showGroupCopyDialog.value = true
}

function closeGroupCopyDialog() {
  showGroupCopyDialog.value = false
  groupCopyTargetGroup.value = null
  groupCopyTargetItem.value = null
}

async function saveGroupCopyEdit() {
  if (savingCopyText.value) return
  const newText = groupCopyEditText.value
  const group = groupCopyTargetGroup.value
  const item = groupCopyTargetItem.value
  if (!group && !item) return
  savingCopyText.value = true
  try {
    if (item) {
      if (newText !== (item.copy_text || '')) {
        const res = await updatePreparationItem(item.id, { copy_text: newText })
        if (res && res.success === false) {
          showNotification('保存失败', '保存失败：' + (res.error || '未知错误'), true)
          return
        }
        if (res?.item) {
          Object.assign(item, normalizePreparationImage(res.item))
        } else {
          item.copy_text = newText
        }
      }
    } else if (newText !== group.poster_copy) {
      const ids = group.items.map(item => item.id)
      const res = await batchUpdatePreparationItems(ids, { poster_copy: newText })
      if (res && res.success === false) {
        showNotification('保存失败', '保存失败：' + (res.error || '未知错误'), true)
        return
      }
      for (const item of group.items) {
        item.poster_copy = newText
      }
      if (selectedGeneralGroupKey.value === group.key) {
        selectedGeneralGroupKey.value = `poster:${newText || ''}`
      }
      group.poster_copy = newText
      group.key = `poster:${newText || ''}`
    }
    showGroupCopyDialog.value = false
    groupCopyTargetGroup.value = null
    groupCopyTargetItem.value = null
  } catch (e) {
    showNotification('保存失败', '保存失败：' + (e.message || '未知错误'), true)
  } finally {
    savingCopyText.value = false
  }
}

function viewPosterCopy(item) {
  if (!item) return
  posterCopyTargetItem.value = item
  posterCopyEditText.value = item.poster_copy || ''
  showPosterCopyDialog.value = true
}

function closePosterCopyDialog() {
  showPosterCopyDialog.value = false
  posterCopyTargetItem.value = null
  posterCopyEditText.value = ''
}

async function savePosterCopy() {
  if (savingPosterCopy.value) return
  const item = posterCopyTargetItem.value
  if (!item) return
  const newText = posterCopyEditText.value
  if (newText === (item.poster_copy || '')) {
    closePosterCopyDialog()
    return
  }
  savingPosterCopy.value = true
  try {
    const res = await updatePreparationItem(item.id, { poster_copy: newText })
    if (res && res.success === false) {
      showNotification('保存失败', '保存失败：' + (res.error || '未知错误'), true)
      return
    }
    if (res && res.item) {
      item.poster_copy = res.item.poster_copy
      item.person_in_charge = res.item.person_in_charge
    } else {
      item.poster_copy = newText
    }
    closePosterCopyDialog()
  } catch (e) {
    showNotification('保存失败', '保存失败：' + (e.message || '未知错误'), true)
  } finally {
    savingPosterCopy.value = false
  }
}

function copyText(text, label = '内容') {
  if (!text) {
    showNotification('复制失败', `没有可复制的${label}`, true)
    console.warn(`[复制功能] ${label}为空，无法复制`)
    return
  }
  
  console.log(`[复制功能] 准备复制${label}，长度: ${text.length}`)
  
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      console.log(`[复制功能] 使用 Clipboard API 复制成功`)
      showNotification('复制成功', `${label}已复制到剪贴板`)
    }).catch((err) => {
      console.error(`[复制功能] Clipboard API 失败:`, err, '尝试降级方案')
      fallbackCopyToClipboard(text, label)
    })
  } else {
    console.warn(`[复制功能] Clipboard API 不可用，使用降级方案`)
    fallbackCopyToClipboard(text, label)
  }
}

function fallbackCopyToClipboard(text, label) {
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    
    const success = document.execCommand('copy')
    document.body.removeChild(textarea)
    
    if (success) {
      console.log(`[复制功能] 使用 execCommand 复制成功`)
      showNotification('复制成功', `${label}已复制到剪贴板`)
    } else {
      console.error(`[复制功能] execCommand 返回失败`)
      showNotification('复制失败', '复制功能不可用，请手动复制', true)
    }
  } catch (err) {
    console.error(`[复制功能] 降级复制方案失败:`, err)
    showNotification('复制失败', '浏览器不支持复制功能', true)
  }
}

async function openImageFolder(item) {
  try {
    await openPreparationFolder(item.id)
  } catch (e) {
    showNotification('打开失败', '无法打开图片所在文件夹：' + (e.message || '未知错误'), true)
  }
}

function isGeneratingSocialCopy(id) {
  return generatingSocialCopyIds.value.includes(id)
}

async function generateSocialCopyForItem(item, force = false) {
  if (!item.poster_copy || !item.poster_copy.trim()) {
    showNotification('无法生成', '海报文案为空，请先填写文案。', true)
    return
  }
  if (item.social_copy && !force) {
    regenerateSocialCopyTarget.value = item
    showRegenerateSocialCopyDialog.value = true
    return
  }
  if (isGeneratingSocialCopy(item.id)) return
  generatingSocialCopyIds.value.push(item.id)
  try {
    const res = await generateSocialCopy(item.id)
    if (res?.success === false) {
      throw new Error(res.error || '生成失败')
    }
    item.social_copy = res.social_copy || res.item?.social_copy || ''
    if (res.item) Object.assign(item, res.item)
  } catch (e) {
    showNotification('生成失败', '生成朋友圈文案失败：' + (e.message || '未知错误'), true)
  } finally {
    generatingSocialCopyIds.value = generatingSocialCopyIds.value.filter(id => id !== item.id)
  }
}

function handleRegenerateSocialCopyConfirm() {
  const item = regenerateSocialCopyTarget.value
  regenerateSocialCopyTarget.value = null
  if (item) {
    generateSocialCopyForItem(item, true)
  }
}

function openSocialCopyEdit(item) {
  socialCopyTargetItem.value = item
  socialCopyEditText.value = item.social_copy || ''
  showSocialCopyDialog.value = true
}

function closeSocialCopyDialog() {
  showSocialCopyDialog.value = false
  socialCopyTargetItem.value = null
  socialCopyEditText.value = ''
}

function openMomentsPreview(item) {
  if (!item || !item.social_copy) return
  momentsPreviewTargetItem.value = item
  showMomentsPreviewDialog.value = true
}

function closeMomentsPreview() {
  showMomentsPreviewDialog.value = false
  momentsPreviewTargetItem.value = null
}

async function saveSocialCopyEdit() {
  const item = socialCopyTargetItem.value
  if (!item || savingSocialCopy.value) return
  savingSocialCopy.value = true
  const nextValue = socialCopyEditText.value
  const previousValue = item.social_copy
  item.social_copy = nextValue
  try {
    const res = await updatePreparationItem(item.id, { social_copy: nextValue })
    if (res?.item) Object.assign(item, res.item)
    closeSocialCopyDialog()
  } catch (e) {
    item.social_copy = previousValue
    showNotification('保存失败', '保存朋友圈文案失败：' + (e.message || '未知错误'), true)
  } finally {
    savingSocialCopy.value = false
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>')
  return html
}

async function loadImages() {
  loading.value = true
  error.value = null
  try {
    const [res] = await Promise.all([
      getPreparationList(),
      refreshPublishGroups()
    ])
    images.value = (res.images || []).map(normalizePreparationImage)
    for (const timeGroup of groupedImages.value) {
      expandedGroups.value[timeGroup.date] = true
    }
    ensurePublishGroupExpanded()
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function updateField(item, field, value) {
  if (item[field] === value) return
  item[field] = value
  try {
    await updatePreparationItem(item.id, { [field]: value })
  } catch (e) {
    console.error(`更新 ${field} 失败:`, e)
  }
}

async function updateScore(item, value) {
  const clamped = clampScore(value)
  if (item.score === clamped) return
  item.score = clamped
  try {
    await updatePreparationItem(item.id, { score: clamped })
  } catch (e) {
    console.error('更新评分失败:', e)
  }
}

function showRenameDialog(item) {
  showRenameItem.value = item
  renameNewName.value = item.filename
}

// 可发布tab页面中，直接编辑文件名时的内联重命名处理
async function renameInline(item, newFilename, event) {
  const trimmed = newFilename.trim()
  if (!trimmed || trimmed === item.filename) {
    event.target.value = item.filename
    return
  }
  try {
    const res = await renamePreparationItem(item.id, trimmed)
    if (res && res.item) {
      const idx = images.value.findIndex(i => i.id === item.id)
      if (idx !== -1) {
        images.value[idx] = { ...images.value[idx], ...normalizePreparationImage(res.item) }
      }
    }
    showNotification('重命名成功', `文件已重命名为: ${trimmed}`)
  } catch (e) {
    event.target.value = item.filename
    showNotification('重命名失败', '重命名失败：' + (e.message || '未知错误'), true)
  }
}

async function confirmRename() {
  if (!showRenameItem.value || !renameNewName.value.trim()) return
  renaming.value = true
  try {
    const res = await renamePreparationItem(showRenameItem.value.id, renameNewName.value.trim())
    if (res && res.item) {
      const idx = images.value.findIndex(i => i.id === showRenameItem.value.id)
      if (idx !== -1) {
        images.value[idx] = { ...images.value[idx], ...normalizePreparationImage(res.item) }
      }
    }
    showRenameItem.value = null
  } catch (e) {
    showNotification('重命名失败', '重命名失败：' + (e.message || '未知错误'), true)
  } finally {
    renaming.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const res = await syncPreparation()
    images.value = (res.images || []).map(normalizePreparationImage)
    await refreshPublishGroups()
    if (res.added > 0 || res.removed > 0) {
      for (const timeGroup of groupedImages.value) {
        expandedGroups.value[timeGroup.date] = true
      }
      ensurePublishGroupExpanded()
    }
  } catch (e) {
    showNotification('同步失败', '同步失败：' + (e.message || '未知错误'), true)
  } finally {
    syncing.value = false
  }
}

async function confirmBatchPlatform() {
  if (!batchPlatformValue.value.trim()) return
  batchUpdating.value = true
  try {
    await batchUpdatePreparationItems(selectedIds.value, { platform: batchPlatformValue.value.trim() })
    for (const id of selectedIds.value) {
      const item = images.value.find(i => i.id === id)
      if (item) item.platform = batchPlatformValue.value.trim()
    }
    showBatchPlatform.value = false
    batchPlatformValue.value = ''
  } catch (e) {
    showNotification('批量更新失败', '批量更新失败：' + (e.message || '未知错误'), true)
  } finally {
    batchUpdating.value = false
  }
}

async function confirmBatchScore() {
  batchUpdating.value = true
  try {
    await batchUpdatePreparationItems(selectedIds.value, { score: clampScore(batchScoreValue.value) })
    const score = clampScore(batchScoreValue.value)
    for (const id of selectedIds.value) {
      const item = images.value.find(i => i.id === id)
      if (item) item.score = score
    }
    showBatchScore.value = false
  } catch (e) {
    showNotification('批量更新失败', '批量更新失败：' + (e.message || '未知错误'), true)
  } finally {
    batchUpdating.value = false
  }
}

async function confirmBatchCopyText() {
  batchUpdating.value = true
  try {
    await batchUpdatePreparationItems(selectedIds.value, { poster_copy: batchCopyTextValue.value })
    for (const id of selectedIds.value) {
      const item = images.value.find(i => i.id === id)
      if (item) item.poster_copy = batchCopyTextValue.value
    }
    showBatchCopyText.value = false
    batchCopyTextValue.value = ''
    clearSelection()
  } catch (e) {
    showNotification('批量更新失败', '批量更新失败：' + (e.message || '未知错误'), true)
  } finally {
    batchUpdating.value = false
  }
}

onMounted(() => {
  loadImages()
})
</script>

<style lang="scss" scoped>
@import '@/styles/PreparationView.scss';

.preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

.preview-modal {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: $color-bg-card;
  border-radius: $radius-xl;
  padding: $spacing-lg;
  box-shadow: $shadow-xl;

  &__close {
    position: absolute;
    top: $spacing-sm;
    right: $spacing-md;
    font-size: 28px;
    color: $color-text-secondary;
    background: none;
    border: none;
    cursor: pointer;
    line-height: 1;
    z-index: 1;

    &:hover {
      color: $color-text-primary;
    }
  }

  &__image {
    max-width: 100%;
    max-height: 70vh;
    object-fit: contain;
    border-radius: $radius-md;
  }

  &__info {
    margin-top: $spacing-md;
    font-size: $font-size-sm;
    color: $color-text-secondary;
  }
}

.rename-dialog,
.batch-dialog {
  background: $color-bg-card;
  border-radius: $radius-xl;
  padding: $spacing-xl;
  min-width: 360px;
  max-width: 90vw;
  box-shadow: $shadow-xl;

  &__title {
    font-size: $font-size-lg;
    font-weight: $font-weight-semibold;
    margin-bottom: $spacing-md;
  }

  &__old-name {
    font-size: $font-size-sm;
    color: $color-text-tertiary;
    margin-bottom: $spacing-md;
  }

  &__input {
    width: 100%;
    padding: $spacing-sm $spacing-md;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    font-size: $font-size-sm;
    outline: none;
    margin-bottom: $spacing-lg;

    &:focus {
      border-color: $color-border-focus;
    }
  }

  &__score-row {
    display: flex;
    align-items: center;
    gap: $spacing-md;
    margin-bottom: $spacing-lg;
  }

  &__slider {
    flex: 1;
    height: 4px;
    -webkit-appearance: none;
    appearance: none;
    background: $color-bg-tertiary;
    border-radius: 2px;
    outline: none;
    cursor: pointer;

    &::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: $color-primary;
      cursor: pointer;
    }
  }

  &__score-input {
    width: 64px;
    text-align: center;
    padding: $spacing-xs $spacing-sm;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    font-size: $font-size-lg;
    font-weight: $font-weight-semibold;
    color: $color-primary;
    outline: none;

    &:focus {
      border-color: $color-border-focus;
    }
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
    gap: $spacing-sm;
  }

  &__btn {
    padding: $spacing-sm $spacing-lg;
    border-radius: $radius-md;
    font-size: $font-size-sm;
    font-weight: $font-weight-medium;
    cursor: pointer;
    border: none;
    transition: all $transition-fast;

    &--cancel {
      background: $color-bg-secondary;
      color: $color-text-secondary;

      &:hover {
        background: $color-bg-tertiary;
      }
    }

    &--confirm {
      background: $color-primary;
      color: white;

      &:hover {
        background: $color-primary-hover;
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
}
</style>
