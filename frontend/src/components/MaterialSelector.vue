<template>
  <div v-if="show" class="material-selector-overlay" @click.self="handleClose">
    <div class="material-selector" @click="handleMaterialSelectorClick">
      <div class="material-selector__header">
        <h3 class="material-selector__title">选择素材</h3>
        <button class="material-selector__close" @click="handleClose">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="material-selector__toolbar">
        <div class="material-selector__search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <path d="m21 21-4.35-4.35"></path>
          </svg>
          <input v-model="searchKeyword" type="text" placeholder="搜索素材..." class="material-selector__search-input" @input="handleSearch" />
        </div>

        <div class="material-selector__folders">
          <button class="material-selector__folder-btn" :class="{ 'material-selector__folder-btn--active': activeFolder === '' }" @click="handleSelectFolder('')">
            全部
          </button>
          <button v-for="folder in folders" :key="folder.name" class="material-selector__folder-btn" :class="{ 'material-selector__folder-btn--active': activeFolder === folder.name }" @click="handleSelectFolder(folder.name)">
            {{ folder.name }}
            <span v-if="folder.file_count > 0" class="material-selector__folder-count">{{ folder.file_count }}</span>
          </button>
          <button class="material-selector__folder-btn material-selector__folder-btn--add" @click="showNewFolderInput = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 4v16m8-8H4"></path>
            </svg>
          </button>
        </div>

        <div v-if="showNewFolderInput" class="material-selector__new-folder">
          <input ref="newFolderInputRef" v-model="newFolderName" type="text" placeholder="输入文件夹名称" class="material-selector__new-folder-input" @keyup.enter="handleCreateFolder" @keyup.escape="showNewFolderInput = false" />
          <button class="material-selector__new-folder-confirm" @click="handleCreateFolder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </button>
          <button class="material-selector__new-folder-cancel" @click="showNewFolderInput = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      <div class="material-selector__actions">
        <button class="material-selector__action-btn" @click="showUploadModal = true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
          添加素材
        </button>
        <button v-if="activeFolder && getFolderFileCount(activeFolder) === 0" class="material-selector__action-btn material-selector__action-btn--danger" @click="handleDeleteFolder">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          删除文件夹
        </button>
      </div>

      <div class="material-selector__content">
        <div v-if="loading" class="material-selector__loading">
          <div class="material-selector__spinner"></div>
          <span>加载中...</span>
        </div>

        <div v-else-if="filteredMaterials.length === 0" class="material-selector__empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
          </svg>
          <p>暂无素材</p>
          <span>点击"添加素材"上传图片</span>
        </div>

        <div v-else class="material-selector__grid">
          <div v-for="material in filteredMaterials" :key="material.id" class="material-selector__item" :class="{ 'material-selector__item--selected': isSelected(material) }" @click="handleSelect(material)" @contextmenu.prevent="showContextMenu($event, material)">
            <img :src="getMaterialDisplayUrl(material)" :alt="material.name" class="material-selector__item-image" loading="lazy" />
            <div class="material-selector__item-overlay">
              <span class="material-selector__item-name">{{ material.name }}</span>
              <span class="material-selector__item-size">{{ material.size_mb }} MB</span>
            </div>
            <div v-if="isSelected(material)" class="material-selector__item-check">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>
            <div v-if="material.manual_url" class="material-selector__item-manual-url" title="已设置手动 URL">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
              </svg>
            </div>
          </div>
        </div>
      </div>

      <div class="material-selector__footer">
        <div class="material-selector__footer-info">
          <span>已选择 {{ selectedMaterials.length }} 个素材</span>
          <span class="material-selector__footer-hint">（可多选）</span>
        </div>
        <div class="material-selector__footer-actions">
          <button v-if="selectedMaterials.length > 1" class="material-selector__btn material-selector__btn--danger" @click="handleBatchDeleteMaterials">批量删除</button>
          <button v-if="selectedMaterials.length > 1" class="material-selector__btn material-selector__btn--secondary" @click="handleBatchMoveMaterials">批量移动</button>
          <button class="material-selector__btn material-selector__btn--secondary" @click="handleClose">取消</button>
          <button class="material-selector__btn material-selector__btn--primary" :disabled="selectedMaterials.length === 0" @click="handleConfirm">确认选择</button>
        </div>
      </div>

      <div v-if="contextMenu.show" class="material-selector__context-menu" :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }" @click.stop>
        <button class="material-selector__context-menu-item" @click="handleMoveMaterial">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 19V5m0 0l7 7-7 7"></path>
          </svg>
          移动到...
        </button>
        <button class="material-selector__context-menu-item" @click="handleRenameMaterial">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
          </svg>
          重命名
        </button>
        <button class="material-selector__context-menu-item" @click="handleSetManualUrl">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
          </svg>
          设置URL
        </button>
        <button class="material-selector__context-menu-item material-selector__context-menu-item--danger" @click="handleDeleteMaterial">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          删除
        </button>
      </div>

      <div v-if="showMoveModal" class="material-selector__modal-overlay" @click.self="showMoveModal = false">
        <div class="material-selector__modal" @click.stop>
          <div class="material-selector__modal-header">
            <span>移动到文件夹</span>
            <button class="material-selector__modal-close" @click="showMoveModal = false">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div class="material-selector__modal-body">
            <div class="material-selector__modal-folder-list">
              <button class="material-selector__modal-folder-item" :class="{ 'material-selector__modal-folder-item--active': moveTargetFolder === '' }" @click="moveTargetFolder = ''">
                根目录
              </button>
              <button v-for="folder in folders" :key="folder.name" class="material-selector__modal-folder-item" :class="{ 'material-selector__modal-folder-item--active': moveTargetFolder === folder.name, 'material-selector__modal-folder-item--disabled': folder.name === contextMenu.material?.folder }" :disabled="folder.name === contextMenu.material?.folder" @click="moveTargetFolder = folder.name">
                {{ folder.name }}
              </button>
            </div>
          </div>
          <div class="material-selector__modal-footer">
            <button class="material-selector__modal-btn material-selector__modal-btn--secondary" @click="showMoveModal = false">取消</button>
            <button class="material-selector__modal-btn material-selector__modal-btn--primary" @click="confirmMove">确认移动</button>
          </div>
        </div>
      </div>

      <div v-if="showRenameModal" class="material-selector__modal-overlay" @click.self="showRenameModal = false">
        <div class="material-selector__modal" @click.stop>
          <div class="material-selector__modal-header">
            <span>重命名</span>
            <button class="material-selector__modal-close" @click="showRenameModal = false">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div class="material-selector__modal-body">
            <input
              v-model="newMaterialName"
              ref="renameInputRef"
              type="text"
              class="material-selector__modal-input"
              placeholder="输入新名称"
              @keyup.enter="confirmRename"
            />
          </div>
          <div class="material-selector__modal-footer">
            <button class="material-selector__modal-btn material-selector__modal-btn--secondary" @click="showRenameModal = false">取消</button>
            <button class="material-selector__modal-btn material-selector__modal-btn--primary" :disabled="!newMaterialName.trim()" @click="confirmRename">确认</button>
          </div>
        </div>
      </div>

      <div v-if="showManualUrlModal" class="material-selector__modal-overlay" @click.self="showManualUrlModal = false">
        <div class="material-selector__modal" @click.stop>
          <div class="material-selector__modal-header">
            <span>手动设置图片 URL</span>
            <button class="material-selector__modal-close" @click="showManualUrlModal = false">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div class="material-selector__modal-body">
            <p class="material-selector__modal-desc">设置后使用此素材作为参考图时，将直接使用该 URL，无需上传。</p>
            <input
              v-model="manualUrlValue"
              type="url"
              class="material-selector__modal-input"
              placeholder="输入图片 URL（留空可清除已有 URL）"
              @keyup.enter="confirmSetManualUrl"
            />
          </div>
          <div class="material-selector__modal-footer">
            <button class="material-selector__modal-btn material-selector__modal-btn--secondary" @click="showManualUrlModal = false">取消</button>
            <button class="material-selector__modal-btn material-selector__modal-btn--primary" @click="confirmSetManualUrl">保存</button>
          </div>
        </div>
      </div>

      <MaterialUpload :show="showUploadModal" @close="showUploadModal = false" @upload-success="handleUploadSuccess" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import MaterialUpload from './MaterialUpload.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  multiple: {
    type: Boolean,
    default: true
  },
  maxCount: {
    type: Number,
    default: 16
  }
})

const emit = defineEmits(['close', 'select'])

const materials = ref([])
const folders = ref([])
const selectedMaterials = ref([])
const activeFolder = ref('')
const searchKeyword = ref('')
const loading = ref(false)
const showNewFolderInput = ref(false)
const newFolderName = ref('')
const newFolderInputRef = ref(null)
const showUploadModal = ref(false)
const showMoveModal = ref(false)
const moveTargetFolder = ref('')
const movingMaterial = ref(null)
const isBatchMaterialMove = ref(false)
const showRenameModal = ref(false)
const newMaterialName = ref('')
const renameInputRef = ref(null)
const showManualUrlModal = ref(false)
const manualUrlValue = ref('')
const contextMenu = ref({
  show: false,
  x: 0,
  y: 0,
  material: null
})

const filteredMaterials = computed(() => {
  let result = materials.value

  if (activeFolder.value) {
    result = result.filter(m => m.folder === activeFolder.value)
  }

  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(m => m.name.toLowerCase().includes(keyword))
  }

  return result
})

const getMaterialUrl = (material) => {
  if (material.folder) {
    return `/api/static/material/${encodeURIComponent(material.folder)}/${encodeURIComponent(material.filename)}`
  }
  return `/api/static/material/${encodeURIComponent(material.filename)}`
}

const getMaterialDisplayUrl = (material) => {
  if (material.thumbnail_url) {
    return material.thumbnail_url
  }
  return getMaterialUrl(material)
}

const getFolderFileCount = (folderName) => {
  const folder = folders.value.find(f => f.name === folderName)
  return folder ? folder.file_count : 0
}

const isSelected = (material) => {
  return selectedMaterials.value.some(m => m.id === material.id)
}

const handleSelectFolder = (folder) => {
  activeFolder.value = folder
}

const handleSearch = () => {
  // 搜索会在 computed 中自动处理
}

const handleSelect = (material) => {
  if (!props.multiple) {
    selectedMaterials.value = [material]
    return
  }

  const index = selectedMaterials.value.findIndex(m => m.id === material.id)

  if (index === -1) {
    if (selectedMaterials.value.length >= props.maxCount) {
      alert(`最多只能选择 ${props.maxCount} 个素材`)
      return
    }
    selectedMaterials.value.push(material)
  } else {
    selectedMaterials.value.splice(index, 1)
  }
}

const showContextMenu = (event, material) => {
  contextMenu.value = {
    show: true,
    x: event.clientX,
    y: event.clientY,
    material: material
  }
}

const hideContextMenu = () => {
  contextMenu.value.show = false
  contextMenu.value.material = null
}

// 点击 material-selector 内部区域（不在 context menu 中）时关闭 context menu
const handleMaterialSelectorClick = () => {
  if (contextMenu.value.show) {
    hideContextMenu()
  }
}

const handleMoveMaterial = () => {
  if (!contextMenu.value.material) return
  movingMaterial.value = contextMenu.value.material
  isBatchMaterialMove.value = false
  moveTargetFolder.value = ''
  showMoveModal.value = true
  nextTick(() => {
    hideContextMenu()
  })
}

const confirmMove = async () => {
  if (isBatchMaterialMove.value) {
    if (selectedMaterials.value.length === 0) return
    for (const mat of [...selectedMaterials.value]) {
      try {
        await fetch('/api/material/move', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: mat.filename,
            source_folder: mat.folder || '',
            target_folder: moveTargetFolder.value
          })
        })
      } catch (e) {
        console.error('批量移动失败:', e)
      }
    }
    selectedMaterials.value = []
    await fetchMaterials()
    await fetchFolders()
    isBatchMaterialMove.value = false
  } else {
    if (!movingMaterial.value) return
    try {
      const response = await fetch('/api/material/move', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: movingMaterial.value.filename,
          source_folder: movingMaterial.value.folder || '',
          target_folder: moveTargetFolder.value
        })
      })
      const result = await response.json()
      if (result.success) {
        await fetchMaterials()
        await fetchFolders()
      } else {
        alert(`移动失败: ${result.message}`)
      }
    } catch (error) {
      console.error('Move error:', error)
      alert('移动失败，请重试')
    }
  }

  showMoveModal.value = false
  movingMaterial.value = null
}

const handleRenameMaterial = () => {
  if (!contextMenu.value.material) return
  movingMaterial.value = contextMenu.value.material
  const nameWithoutExt = contextMenu.value.material.name || ''
  newMaterialName.value = nameWithoutExt
  showRenameModal.value = true
  nextTick(() => {
    hideContextMenu()
    renameInputRef.value?.focus()
    renameInputRef.value?.select()
  })
}

const confirmRename = async () => {
  if (!movingMaterial.value) return
  const newName = newMaterialName.value.trim()
  if (!newName) {
    alert('请输入新名称')
    return
  }

  try {
    const response = await fetch('/api/material/rename', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: movingMaterial.value.filename,
        new_name: newName,
        folder: movingMaterial.value.folder || ''
      })
    })

    const result = await response.json()

    if (result.success) {
      await fetchMaterials()
      await fetchFolders()
    } else {
      alert(`重命名失败: ${result.message}`)
    }
  } catch (error) {
    console.error('Rename error:', error)
    alert('重命名失败，请重试')
  }

  showRenameModal.value = false
  movingMaterial.value = null
}

const handleSetManualUrl = () => {
  if (!contextMenu.value.material) return
  const mat = contextMenu.value.material
  manualUrlValue.value = mat.manual_url || ''
  movingMaterial.value = mat
  showManualUrlModal.value = true
  nextTick(() => {
    hideContextMenu()
  })
}

const confirmSetManualUrl = async () => {
  if (!movingMaterial.value) return
  const url = manualUrlValue.value.trim()
  try {
    const response = await fetch('/api/material/manual-url', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        relative_path: movingMaterial.value.relative_path,
        url: url
      })
    })
    const result = await response.json()
    if (result.success) {
      // 刷新素材列表以获取最新的 manual_url
      await fetchMaterials()
      await fetchFolders()
      showManualUrlModal.value = false
      movingMaterial.value = null
    } else {
      alert(`设置 URL 失败: ${result.message}`)
    }
  } catch (error) {
    console.error('Set manual URL error:', error)
    alert('设置 URL 失败，请重试')
  }
}

const handleDeleteMaterial = async () => {
  if (!contextMenu.value.material) return
  const targetMaterial = contextMenu.value.material

  if (!confirm(`确定要删除素材"${targetMaterial.name}"吗？`)) {
    hideContextMenu()
    return
  }

  try {
    const response = await fetch(`/api/material/${encodeURIComponent(targetMaterial.filename)}?folder=${targetMaterial.folder || ''}`, {
      method: 'DELETE'
    })

    const result = await response.json()

    if (result.success) {
      await fetchMaterials()
      await fetchFolders()
      selectedMaterials.value = selectedMaterials.value.filter(m => m.id !== targetMaterial.id)
    } else {
      alert(`删除失败: ${result.message}`)
    }
  } catch (error) {
    console.error('Delete error:', error)
    alert('删除失败，请重试')
  }

  hideContextMenu()
}

const handleBatchDeleteMaterials = async () => {
  if (selectedMaterials.value.length === 0) return
  if (!confirm(`确定要删除选中的 ${selectedMaterials.value.length} 个素材吗？`)) return

  for (const mat of [...selectedMaterials.value]) {
    try {
      await fetch(`/api/material/${encodeURIComponent(mat.filename)}?folder=${mat.folder || ''}`, {
        method: 'DELETE'
      })
    } catch (e) {
      console.error('批量删除失败:', e)
    }
  }
  selectedMaterials.value = []
  await fetchMaterials()
  await fetchFolders()
}

const handleBatchMoveMaterials = () => {
  if (selectedMaterials.value.length === 0) return
  movingMaterial.value = null
  isBatchMaterialMove.value = true
  moveTargetFolder.value = ''
  showMoveModal.value = true
}

const handleCreateFolder = async () => {
  const name = newFolderName.value.trim()
  if (!name) return

  try {
    const response = await fetch('/api/material/folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })

    const result = await response.json()

    if (result.success) {
      newFolderName.value = ''
      showNewFolderInput.value = false
      await fetchFolders()
      activeFolder.value = result.data.name
    } else {
      alert(`创建失败: ${result.message}`)
    }
  } catch (error) {
    console.error('Create folder error:', error)
    alert('创建失败，请重试')
  }
}

const handleDeleteFolder = async () => {
  if (!activeFolder.value) return

  if (!confirm(`确定要删除文件夹"${activeFolder.value}"吗？`)) return

  try {
    const response = await fetch(`/api/material/folder/${encodeURIComponent(activeFolder.value)}`, {
      method: 'DELETE'
    })

    const result = await response.json()

    if (result.success) {
      activeFolder.value = ''
      await fetchFolders()
    } else {
      alert(`删除失败: ${result.message}`)
    }
  } catch (error) {
    console.error('Delete folder error:', error)
    alert('删除失败，请重试')
  }
}

const handleUploadSuccess = async (count) => {
  await fetchMaterials()
  await fetchFolders()
}

const handleConfirm = () => {
  emit('select', [...selectedMaterials.value])
  handleClose()
}

const handleClose = () => {
  selectedMaterials.value = []
  searchKeyword.value = ''
  activeFolder.value = ''
  hideContextMenu()
  emit('close')
}

const fetchMaterials = async () => {
  try {
    const response = await fetch('/api/material/list')
    const result = await response.json()

    if (result.success) {
      materials.value = result.data || []
    }
  } catch (error) {
    console.error('Failed to fetch materials:', error)
  }
}

const fetchFolders = async () => {
  try {
    const response = await fetch('/api/material/info')
    const result = await response.json()

    if (result.success) {
      folders.value = result.data.folders || []
    }
  } catch (error) {
    console.error('Failed to fetch folders:', error)
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchMaterials()
    fetchFolders()
  }
})

watch(showNewFolderInput, (newVal) => {
  if (newVal) {
    nextTick(() => {
      newFolderInputRef.value?.focus()
    })
  }
})

// context menu 的关闭已由 handleMaterialSelectorClick 通过 .material-selector@click 处理
// 不再需要 document 级的事件监听（与 @click.stop 冲突）


onMounted(() => {
  if (props.show) {
    fetchMaterials()
    fetchFolders()
  }
})
</script>

<style lang="scss" scoped>
.material-selector-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.material-selector {
  width: 90%;
  max-width: 900px;
  max-height: 80vh;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.material-selector__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.material-selector__title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.material-selector__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #f1f5f9;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: #e2e8f0;
  }

  svg {
    width: 16px;
    height: 16px;
    color: #475569;
  }
}

.material-selector__toolbar {
  padding: 12px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.material-selector__search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f1f5f9;
  border-radius: 8px;
  margin-bottom: 12px;

  svg {
    width: 16px;
    height: 16px;
    color: #94a3b8;
    flex-shrink: 0;
  }
}

.material-selector__search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  color: #0f172a;
  outline: none;

  &::placeholder {
    color: #94a3b8;
  }
}

.material-selector__folders {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.material-selector__folder-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: #e2e8f0;
    border-color: #cbd5e1;
  }

  &--active {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border-color: transparent;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
  }

  &--add {
    padding: 6px 8px;

    svg {
      width: 14px;
      height: 14px;
    }
  }
}

.material-selector__folder-count {
  font-size: 10px;
  opacity: 0.7;
}

.material-selector__new-folder {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.material-selector__new-folder-input {
  flex: 1;
  padding: 8px 12px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  color: #0f172a;
  outline: none;

  &:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
  }
}

.material-selector__new-folder-confirm,
.material-selector__new-folder-cancel {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #f1f5f9;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;

  svg {
    width: 14px;
    height: 14px;
    color: #64748b;
  }
}

.material-selector__new-folder-confirm:hover {
  background: #dcfce7;

  svg {
    color: #22c55e;
  }
}

.material-selector__new-folder-cancel:hover {
  background: #fee2e2;

  svg {
    color: #ef4444;
  }
}

.material-selector__actions {
  display: flex;
  gap: 8px;
  padding: 8px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.material-selector__action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(99, 102, 241, 0.05) 100%);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: #6366f1;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(99, 102, 241, 0.1) 100%);
    border-color: rgba(99, 102, 241, 0.3);
  }

  svg {
    width: 14px;
    height: 14px;
  }

  &--danger {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
    border-color: rgba(239, 68, 68, 0.2);
    color: #ef4444;

    &:hover {
      background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.1) 100%);
      border-color: rgba(239, 68, 68, 0.3);
    }
  }
}

.material-selector__content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.material-selector__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #64748b;
  gap: 12px;
}

.material-selector__spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.material-selector__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #64748b;

  svg {
    width: 64px;
    height: 64px;
    margin-bottom: 16px;
    opacity: 0.4;
  }

  p {
    font-size: 14px;
    font-weight: 500;
    margin: 0 0 4px;
  }

  span {
    font-size: 12px;
    color: #94a3b8;
  }
}

.material-selector__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.material-selector__item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  background: #f1f5f9;
  transition: all 0.2s;

  &:hover {
    transform: scale(1.02);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);

    .material-selector__item-overlay {
      opacity: 1;
    }
  }

  &--selected {
    outline: 2px solid #6366f1;
    outline-offset: 2px;
  }
}

.material-selector__item-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.material-selector__item-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.8), transparent);
  opacity: 0;
  transition: opacity 0.2s;
}

.material-selector__item-name {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: #ffffff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.material-selector__item-size {
  display: block;
  font-size: 9px;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 2px;
}

.material-selector__item-check {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 22px;
  height: 22px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    width: 12px;
    height: 12px;
    color: #ffffff;
  }
}

.material-selector__item-manual-url {
  position: absolute;
  top: 6px;
  left: 6px;
  width: 22px;
  height: 22px;
  background: rgba(16, 185, 129, 0.9);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    width: 12px;
    height: 12px;
    color: #ffffff;
  }
}

.material-selector__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
}

.material-selector__footer-info {
  font-size: 12px;
  color: #64748b;
}

.material-selector__footer-hint {
  color: #94a3b8;
  margin-left: 4px;
}

.material-selector__footer-actions {
  display: flex;
  gap: 8px;
}

.material-selector__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;

  &--primary {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border: none;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);

    &:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  &--secondary {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    color: #64748b;

    &:hover {
      background: #f1f5f9;
      border-color: #cbd5e1;
    }
  }

  &--danger {
    background: #ffffff;
    border: 1px solid rgba(239, 68, 68, 0.2);
    color: #ef4444;

    &:hover {
      background: #fee2e2;
      border-color: rgba(239, 68, 68, 0.3);
    }
  }
}

.material-selector__context-menu {
  position: fixed;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
  padding: 4px;
  z-index: 2000;
  min-width: 140px;
}

.material-selector__context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  color: #0f172a;
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    background: #f1f5f9;
  }

  svg {
    width: 14px;
    height: 14px;
    color: #64748b;
  }

  &--danger:hover {
    background: #fee2e2;
    color: #ef4444;

    svg {
      color: #ef4444;
    }
  }
}

.material-selector__modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2500;
}

.material-selector__modal {
  width: 90%;
  max-width: 400px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.material-selector__modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.material-selector__modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: #f1f5f9;
  border: none;
  border-radius: 6px;
  cursor: pointer;

  svg {
    width: 14px;
    height: 14px;
    color: #64748b;
  }
}

.material-selector__modal-body {
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.material-selector__modal-input {
  width: 100%;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  transition: all 0.2s;

  &:focus {
    outline: none;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
  }

  &::placeholder {
    color: #94a3b8;
  }
}

.material-selector__modal-desc {
  font-size: 12px;
  color: #64748b;
  margin: 0 0 12px;
  line-height: 1.5;
}

.material-selector__modal-folder-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.material-selector__modal-folder-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  color: #0f172a;
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
  }

  &--active {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(99, 102, 241, 0.05) 100%);
    border-color: #6366f1;
    color: #6366f1;
    font-weight: 500;
  }

  &--disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.material-selector__modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
}

.material-selector__modal-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;

  &--primary {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border: none;
    color: #ffffff;

    &:hover {
      transform: translateY(-1px);
    }
  }

  &--secondary {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    color: #64748b;

    &:hover {
      background: #f1f5f9;
    }
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>