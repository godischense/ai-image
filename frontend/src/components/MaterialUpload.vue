<template>
  <div v-if="show" class="material-upload-overlay" @click="handleClose">
    <div class="material-upload" @click.stop>
      <div class="material-upload__header">
        <h3 class="material-upload__title">上传素材</h3>
        <button class="material-upload__close" @click="handleClose">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="material-upload__body">
        <div class="material-upload__dropzone" :class="{ 'material-upload__dropzone--dragover': isDragOver }" @dragover.prevent="handleDragOver" @dragleave.prevent="handleDragLeave" @drop.prevent="handleDrop" @click="triggerFileInput">
          <div class="material-upload__dropzone-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
          </div>
          <p class="material-upload__dropzone-text">点击或拖拽上传素材图片</p>
          <span class="material-upload__dropzone-hint">支持 JPG、PNG、WebP，单个文件不超过 10MB</span>
          <input ref="fileInputRef" type="file" class="material-upload__input" accept="image/jpeg,image/png,image/webp" multiple @change="handleFileSelect" />
        </div>

        <div v-if="selectedFiles.length > 0" class="material-upload__file-list">
          <div v-for="(file, index) in selectedFiles" :key="index" class="material-upload__file-item">
            <img :src="file.preview" class="material-upload__file-thumb" />
            <div class="material-upload__file-info">
              <span class="material-upload__file-name">{{ file.name }}</span>
              <span class="material-upload__file-size">{{ formatFileSize(file.size) }}</span>
            </div>
            <button class="material-upload__file-remove" @click="removeFile(index)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>

        <div class="material-upload__folder">
          <label class="material-upload__folder-label">上传到文件夹</label>
          <div class="material-upload__folder-select">
            <select v-model="selectedFolder" class="material-upload__select">
              <option value="">根目录</option>
              <option v-for="folder in folders" :key="folder.name" :value="folder.name">
                {{ folder.name }} ({{ folder.file_count }})
              </option>
            </select>
            <svg class="material-upload__select-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>
        </div>
      </div>

      <div class="material-upload__footer">
        <button class="material-upload__btn material-upload__btn--secondary" @click="handleClose">
          取消
        </button>
        <button class="material-upload__btn material-upload__btn--primary" :disabled="selectedFiles.length === 0 || uploading" @click="handleUpload">
          <span v-if="uploading">上传中... {{ uploadProgress }}%</span>
          <span v-else>上传 {{ selectedFiles.length }} 个文件</span>
        </button>
      </div>

      <div v-if="uploading" class="material-upload__progress">
        <div class="material-upload__progress-bar">
          <div class="material-upload__progress-fill" :style="{ width: uploadProgress + '%' }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'upload-success'])

const fileInputRef = ref(null)
const selectedFiles = ref([])
const selectedFolder = ref('')
const folders = ref([])
const isDragOver = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

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
  processFiles(files)
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  processFiles(files)
  event.target.value = ''
}

const processFiles = (files) => {
  const validTypes = ['image/jpeg', 'image/png', 'image/webp']
  const maxSize = 10 * 1024 * 1024

  files.forEach(file => {
    if (!validTypes.includes(file.type)) {
      console.error('Unsupported file type:', file.type)
      return
    }
    if (file.size > maxSize) {
      console.error('File too large:', file.size)
      return
    }

    const reader = new FileReader()
    reader.onload = (e) => {
      selectedFiles.value.push({
        name: file.name,
        size: file.size,
        type: file.type,
        file: file,
        preview: e.target.result
      })
    }
    reader.readAsDataURL(file)
  })
}

const removeFile = (index) => {
  selectedFiles.value.splice(index, 1)
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

const handleUpload = async () => {
  if (selectedFiles.value.length === 0) return

  uploading.value = true
  uploadProgress.value = 0

  let uploadedCount = 0
  const totalFiles = selectedFiles.value.length

  for (const fileData of selectedFiles.value) {
    try {
      const formData = new FormData()
      formData.append('file', fileData.file)
      if (selectedFolder.value) {
        formData.append('folder', selectedFolder.value)
      }

      const response = await fetch('/api/material/upload', {
        method: 'POST',
        body: formData
      })

      const result = await response.json()

      if (result.success) {
        uploadedCount++
        uploadProgress.value = Math.round((uploadedCount / totalFiles) * 100)
      } else {
        console.error('Upload failed:', result.message)
      }
    } catch (error) {
      console.error('Upload error:', error)
    }
  }

  uploading.value = false

  if (uploadedCount === totalFiles) {
    emit('upload-success', uploadedCount)
    handleClose()
  } else {
    alert(`成功上传 ${uploadedCount}/${totalFiles} 个文件`)
  }
}

const handleClose = () => {
  selectedFiles.value = []
  selectedFolder.value = ''
  uploadProgress.value = 0
  isDragOver.value = false
  emit('close')
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchFolders()
  }
})

onMounted(() => {
  if (props.show) {
    fetchFolders()
  }
})
</script>

<style lang="scss" scoped>
.material-upload-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.material-upload {
  width: 90%;
  max-width: 500px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  overflow: hidden;
  position: relative;
}

.material-upload__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.material-upload__title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.material-upload__close {
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

.material-upload__body {
  padding: 20px;
}

.material-upload__dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  border: 2px dashed #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: #6366f1;
    background: rgba(99, 102, 241, 0.05);
  }

  &--dragover {
    border-color: #6366f1;
    background: rgba(99, 102, 241, 0.1);
  }
}

.material-upload__dropzone-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 12px;
  color: #6366f1;
}

.material-upload__dropzone-text {
  font-size: 14px;
  font-weight: 500;
  color: #0f172a;
  margin: 0 0 4px;
}

.material-upload__dropzone-hint {
  font-size: 12px;
  color: #94a3b8;
}

.material-upload__input {
  display: none;
}

.material-upload__file-list {
  margin-top: 16px;
  max-height: 200px;
  overflow-y: auto;
}

.material-upload__file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 8px;

  &:last-child {
    margin-bottom: 0;
  }
}

.material-upload__file-thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
}

.material-upload__file-info {
  flex: 1;
  min-width: 0;
}

.material-upload__file-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.material-upload__file-size {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.material-upload__file-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: #94a3b8;
  transition: all 0.2s;

  &:hover {
    background: #fee2e2;
    color: #ef4444;
  }

  svg {
    width: 14px;
    height: 14px;
  }
}

.material-upload__folder {
  margin-top: 16px;
}

.material-upload__folder-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  margin-bottom: 6px;
}

.material-upload__folder-select {
  position: relative;
}

.material-upload__select {
  width: 100%;
  padding: 10px 36px 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  color: #0f172a;
  appearance: none;
  cursor: pointer;
  transition: all 0.2s;

  &:focus {
    outline: none;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
  }
}

.material-upload__select-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 14px;
  height: 14px;
  color: #94a3b8;
  pointer-events: none;
}

.material-upload__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
}

.material-upload__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 20px;
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
}

.material-upload__progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: #e2e8f0;
}

.material-upload__progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%);
  transition: width 0.3s ease;
}
</style>