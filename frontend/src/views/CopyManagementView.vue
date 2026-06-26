<script setup>
import { ref, nextTick, onUnmounted, watch, computed } from 'vue'
import {
  createCopyBoard,
  deleteCopyBoard,
  getCopyBoardContent,
  getCopyContent,
  getCopyFiles,
  getLockedFiles,
  renameCopyBoard,
  saveCopyCountryNote,
  saveCopyBoardContent,
  saveCopyContent,
  uploadCopyHtml,
  confirmUploadCopyHtml
} from '@/services/api'
import collab, { generateToken } from '@/services/copyCollaboration'
import ConfirmDialog from '@/components/common/ConfirmDialog/ConfirmDialog.vue'

const countries = ref([])
const loading = ref(false)
const contentLoading = ref(false)
const saving = ref(false)
const error = ref('')
const selectedCountry = ref('')
const selectedFile = ref(null)

const htmlContent = ref('')
const originalHtmlContent = ref('')
const boardCards = ref([])
const originalBoardCards = ref([])
const iframeRef = ref(null)
const iframeVersion = ref(0)
const editMode = ref(true)
const hasUnsavedChanges = ref(false)
const activeEditSpan = ref(null)
const editDraft = ref('')
const editDialogVisible = ref(false)
const confirmDialogVisible = ref(false)
const confirmDialogTitle = ref('')
const confirmDialogMessage = ref('')
const confirmDialogConfirmText = ref('确定')
let pendingConfirmResolve = null
const renameDialogVisible = ref(false)
const renameTargetFile = ref(null)
const renameDraft = ref('')

const uploading = ref(false)
const uploadInputRef = ref(null)

const cardEditDialogVisible = ref(false)
const activeEditCardElement = ref(null)
const cardEditDraft = ref('')
const cardEditError = ref('')

const codeLineNumbersRef = ref(null)
const codeTextareaRef = ref(null)

const codeLines = computed(() => {
  const text = cardEditDraft.value || ''
  return text.split('\n').length
})

const toastVisible = ref(false)
const toastMessage = ref('')
let toastTimer = null
const countryNoteTimers = new Map()

// 协作相关状态：文件级锁、只读模式、同房间订阅者数量（已移除块级锁，仅保留文件锁）
const fileLockToken = ref('')            // 当前文件锁的 owner token
const fileLockHeldByMe = ref(false)      // 当前文件锁是否由本人持有
const readOnlyMode = ref(false)          // 只读模式（拿不到锁时为 true）
const presenceCount = ref(0)             // 同房间订阅者数量
let unsubscribeCollab = null             // 取消协作订阅的回调
// 编辑权限移交轮询
let handoffPollTimer = null              // A 端的轮询定时器
// 被锁文件 key 集合：用于在侧边栏文件项上显示"正在编辑"徽章
const lockedFileKeys = ref(new Set())
// 锁状态轮询定时器
let lockStatusPollTimer = null
// 锁状态轮询间隔：10 秒（侧边栏"正在编辑"徽章的刷新粒度）
const LOCK_STATUS_POLL_MS = 10000
// 公共 ConfirmDialog 的显示状态
const publicConfirmVisible = ref(false)
const publicConfirmTitle = ref('')
const publicConfirmMessage = ref('')
const publicConfirmConfirmText = ref('确定')
const publicConfirmCancelText = ref('取消')
let pendingPublicConfirmResolve = null
// iframe 待恢复的滚动位置：保存后 iframeVersion += 1 会销毁并重建 iframe，导致滚动位置丢失；
// 在重建前把当前 scrollTop/scrollLeft 暂存起来，在 onIframeLoad 中恢复，避免页面跳到顶部
let pendingIframeScrollRestore = null

const RUNTIME_STYLE_ID = 'copy-management-runtime-style'
const EDITABLE_CLASS = 'copy-editable-text'
const EDITED_CLASS = 'copy-edited-text'
const EDITED_ATTR = 'data-copy-edited'
const MADE_TAG_CLASS = 'copy-made-tag'
const REVIEWED_TAG_CLASS = 'copy-reviewed-tag'
const PUBLISHED_TAG_CLASS = 'copy-published-tag'
const MADE_TAG_ATTR = 'data-copy-made'
const REVIEWED_TAG_ATTR = 'data-copy-reviewed'
const PUBLISHED_TAG_ATTR = 'data-copy-published'
const ROOT_BOARD_COUNTRY = '__root__'
const ROOT_BOARD_GROUP_NAME = '原生卡片'

function showToast(msg) {
  toastMessage.value = msg
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastVisible.value = false
  }, 1800)
}

// 公共 ConfirmDialog 的 Promise 封装，便于在需要时使用公共组件而不是页面内嵌的 confirmDialogVisible
function requestPublicConfirmation({ title, message, confirmText = '确定', cancelText = '取消' }) {
  publicConfirmTitle.value = title
  publicConfirmMessage.value = message
  publicConfirmConfirmText.value = confirmText
  publicConfirmCancelText.value = cancelText
  publicConfirmVisible.value = true
  return new Promise((resolve) => {
    pendingPublicConfirmResolve = resolve
  })
}

function resolvePublicConfirm(result) {
  publicConfirmVisible.value = false
  if (pendingPublicConfirmResolve) {
    pendingPublicConfirmResolve(result)
    pendingPublicConfirmResolve = null
  }
}

// 释放当前打开文件的协作会话（锁、心跳、订阅），在切换/关闭文件时调用
async function releaseCollabSession() {
  // 停掉心跳
  collab.stopHeartbeat()
  stopHandoffPolling()
  // 先取消订阅（从服务端移除该客户端，让其他请求方可立即检测到无活跃用户）
  if (unsubscribeCollab) {
    try {
      unsubscribeCollab()
    } catch (e) {
      // ignore
    }
    unsubscribeCollab = null
  }
  // 再释放文件级锁（仅当本人持有时）
  const fileKey = selectedFile.value?.relative_path
  if (fileKey && fileLockHeldByMe.value && fileLockToken.value) {
    try {
      await collab.releaseFileLock(fileKey, fileLockToken.value)
    } catch (e) {
      // ignore
    }
  }
  fileLockToken.value = ''
  fileLockHeldByMe.value = false
  readOnlyMode.value = false
  presenceCount.value = 0
}

// 拉取并刷新被锁文件 key 集合
// 实现逻辑：调用 getLockedFiles 拿到数组后，用新 Set 整体替换原 Set；失败时静默忽略，保持上一次状态
async function refreshLockedFiles() {
  try {
    const res = await getLockedFiles()
    if (res && res.success && Array.isArray(res.locked_files)) {
      lockedFileKeys.value = new Set(res.locked_files)
    }
  } catch (e) {
    // 轮询失败时静默忽略，不打扰用户；保留上一次的状态
  }
}

// 启动锁状态轮询（进入文案管理视图时调用）
// 实现逻辑：先停掉旧定时器，立即拉一次，再每 10 秒拉一次
function startLockStatusPoll() {
  stopLockStatusPoll()
  // 立即拉一次，避免刚进入页面时徽章缺失
  refreshLockedFiles()
  lockStatusPollTimer = setInterval(refreshLockedFiles, LOCK_STATUS_POLL_MS)
}

// 停止锁状态轮询（离开文案管理视图时调用）
function stopLockStatusPoll() {
  if (lockStatusPollTimer) {
    clearInterval(lockStatusPollTimer)
    lockStatusPollTimer = null
  }
}

// 判断指定文件是否被"我"持有（用于决定徽章显示"您正在编辑"还是"正在编辑"）
// 实现逻辑：与现有 saveCurrentFile 校验一致，必须同时满足本人持有标志 + token 非空 + 当前打开的就是该文件
function isFileLockedByMine(file) {
  if (!file || !fileLockHeldByMe.value || !fileLockToken.value) return false
  return selectedFile.value?.relative_path === file.relative_path
}

// 通过 navigator.sendBeacon 触发"页面关闭前"的最后一次保存
// 实现逻辑：sendBeacon 是浏览器在 unload 时仍能发出的非阻塞请求，适合在 beforeunload 中使用；
//          失败也无所谓（最多丢失当前未保存内容），不影响页面关闭流程
function sendBeaconSave() {
  if (!selectedFile.value || !fileLockHeldByMe.value || !fileLockToken.value) return
  if (!hasUnsavedChanges.value) return
  const fileKey = selectedFile.value.relative_path
  const token = fileLockToken.value
  try {
    if (isBoardFile()) {
      const payload = JSON.stringify({ path: fileKey, cards: boardCards.value, token })
      const blob = new Blob([payload], { type: 'application/json' })
      navigator.sendBeacon('/api/copy/boards/content', blob)
    } else {
      const content = getCleanHtmlForSave()
      if (!content.trim()) return
      const payload = JSON.stringify({ path: fileKey, content, token })
      const blob = new Blob([payload], { type: 'application/json' })
      navigator.sendBeacon('/api/copy/content', blob)
    }
  } catch (e) {
    // sendBeacon 失败时静默忽略，不阻塞页面关闭
  }
}

// 通过 navigator.sendBeacon 触发"页面关闭前"的最后一次锁释放
// 实现逻辑：sendBeacon 在 unload 时仍能保证请求被发送到服务端，适合释放文件锁这种
//          "发出即可、不需要看响应"的场景；onUnmounted 里的 await fetch 在刷新时
//          经常被浏览器丢弃，导致服务端锁残留 30s。失败时降级为同步 XHR，再不行就静默
//          兜底（最坏情况由后端 LOCK_TTL_SECONDS 30s 自动回收）
function sendBeaconLockRelease() {
  if (!selectedFile.value || !fileLockHeldByMe.value || !fileLockToken.value) return
  const fileKey = selectedFile.value.relative_path
  const token = fileLockToken.value
  const payload = JSON.stringify({ file_key: fileKey, owner_token: token })
  try {
    const blob = new Blob([payload], { type: 'application/json' })
    const sent = navigator.sendBeacon && navigator.sendBeacon('/api/copy/lock/release', blob)
    if (sent) return
    // 极少数浏览器（极旧内核）不支持 sendBeacon，降级为同步 XHR
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/copy/lock/release', false) // false = 同步，unload 阶段也能发出
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.send(payload)
  } catch (e) {
    // 兜底：失败也无所谓，最坏情况由后端 30s TTL 回收
  }
}

// 页面关闭/刷新前的事件处理
// 实现逻辑：
//   1) 关键修复：只要本人持有锁，就在 unload 阶段用 sendBeacon 同步释放文件锁，
//      否则服务端锁会残留 30s 导致"刷新后无法立即重入"且多个文件连锁卡死
//   2) 当有未保存改动时，再发送一次保存请求并弹出浏览器原生确认框
function handleBeforeUnload(event) {
  // 第一步：先释放文件锁（与是否有未保存改动无关，本人都必须把锁还回去）
  if (fileLockHeldByMe.value && fileLockToken.value) {
    sendBeaconLockRelease()
  }
  if (hasUnsavedChanges.value && fileLockHeldByMe.value) {
    sendBeaconSave()
    event.preventDefault()
    event.returnValue = '有未保存的修改，确定要离开吗？'
    return event.returnValue
  }
}

// 补充监听 pagehide：移动端 / 关闭标签时比 beforeunload 更可靠
// 实现逻辑：与 beforeunload 共用 sendBeaconLockRelease，保证各种退出路径下锁都能释放；
//          pagehide 在 iOS Safari、被冻结的后台标签等场景下会触发，而 beforeunload 不一定
function handlePageHide() {
  if (fileLockHeldByMe.value && fileLockToken.value) {
    sendBeaconLockRelease()
  }
}

function getCountryKey(country) {
  return country.country || country.name
}

function saveCountryNoteDebounced(country) {
  const countryKey = getCountryKey(country)
  if (!countryKey) return

  if (countryNoteTimers.has(countryKey)) {
    clearTimeout(countryNoteTimers.get(countryKey))
  }

  const timer = setTimeout(async () => {
    countryNoteTimers.delete(countryKey)
    try {
      const res = await saveCopyCountryNote(countryKey, country.note || '')
      if (!res.success) {
        throw new Error(res.error || '保存备注失败')
      }
    } catch (e) {
      showToast(e.message || '保存备注失败')
    }
  }, 500)

  countryNoteTimers.set(countryKey, timer)
}

// 注册 beforeunload 监听：页面关闭/刷新时尝试保存未提交的内容
window.addEventListener('beforeunload', handleBeforeUnload)
// 注册 pagehide 监听：补充移动端 / 关闭标签等 beforeunload 不一定触发的场景
// 实现逻辑：与 beforeunload 共用 sendBeaconLockRelease，确保锁一定能在退出时还掉
window.addEventListener('pagehide', handlePageHide)

onUnmounted(async () => {
  // 移除 beforeunload / pagehide 监听，避免组件卸载后继续拦截其他页面的关闭事件
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('pagehide', handlePageHide)
  // 停止锁状态轮询，避免组件卸载后定时器仍在跑
  stopLockStatusPoll()
  countryNoteTimers.forEach((timer) => clearTimeout(timer))
  countryNoteTimers.clear()
  // 离开文案管理页面时释放协作会话
  await releaseCollabSession()
})

watch(cardEditDialogVisible, (visible) => {
  if (visible) {
    nextTick(() => {
      codeTextareaRef.value?.focus()
    })
  }
})

function isBoardFile(file = selectedFile.value) {
  return file?.type === 'copy_board'
}

function cloneCards(cards) {
  return JSON.parse(JSON.stringify(cards || []))
}

// 创建一个新的文案卡片（草稿状态）
// 实现逻辑：生成唯一的卡片 id，默认未做/未审核/未发；时间戳使用 ISO 格式便于序列化
function makeBoardCard(content = '') {
  const now = new Date().toISOString()
  return {
    id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    content,
    created_at: now,
    updated_at: now,
    made: false,
    reviewed: false,
    published: false
  }
}

function touchBoardCard(card, updates = {}) {
  Object.assign(card, updates, { updated_at: new Date().toISOString() })
  hasUnsavedChanges.value = true
}

function addBlankBoardCard() {
  boardCards.value.push(makeBoardCard(''))
  hasUnsavedChanges.value = true
  nextTick(() => {
    document.querySelector('.copy-board-card:last-child textarea')?.focus()
  })
}

function handleBoardPaste(event) {
  // 检查是否在输入元素中粘贴，如果是则执行默认行为
  const activeElement = document.activeElement
  const isInInputElement = 
    activeElement.tagName === 'TEXTAREA' || 
    activeElement.tagName === 'INPUT' ||
    activeElement.isContentEditable
  
  if (isInInputElement) {
    return // 让浏览器执行默认粘贴行为
  }

  const text = event.clipboardData?.getData('text/plain') || ''
  if (!text.trim()) return

  event.preventDefault()
  boardCards.value.push(makeBoardCard(text.replace(/\r\n/g, '\n')))
  hasUnsavedChanges.value = true
  showToast('已新增一张文案卡片')
}

async function copyBoardCard(card) {
  const ok = await copyToClipboard(card.content || '')
  showToast(ok ? '已复制到剪贴板' : '复制失败')
}

async function deleteBoardCard(index) {
  const confirmed = await requestConfirmation({
    title: '删除文案卡片',
    message: '确定要删除这张文案卡片吗？此操作无法撤销。',
    confirmText: '删除'
  })
  if (!confirmed) return

  boardCards.value.splice(index, 1)
  hasUnsavedChanges.value = true
  showToast('已删除文案卡片')
}

function moveBoardCard(index, direction) {
  const nextIndex = index + direction
  if (nextIndex < 0 || nextIndex >= boardCards.value.length) return

  const cards = boardCards.value
  const [card] = cards.splice(index, 1)
  cards.splice(nextIndex, 0, card)
  hasUnsavedChanges.value = true
}

async function createBoardForCountry(countryName, displayCountryName = countryName) {
  if (hasUnsavedChanges.value) {
    const confirmed = await requestConfirmation({
      title: '新建空白页',
      message: '当前文件有未保存修改，新建并打开空白页会切换当前页面。',
      confirmText: '继续新建'
    })
    if (!confirmed) return
  }

  saving.value = true
  try {
    const res = await createCopyBoard(countryName)
    if (!res.success) {
      throw new Error(res.error || '创建空白页失败')
    }

    await refreshFileList()
    await openFile(displayCountryName, res.file, true)
    showToast('已创建空白文案页')
  } catch (e) {
    showToast(e.message || '创建空白页失败')
  } finally {
    saving.value = false
  }
}

function createRootBoard() {
  return createBoardForCountry(ROOT_BOARD_COUNTRY, ROOT_BOARD_GROUP_NAME)
}

function triggerUpload() {
  uploadInputRef.value?.click()
}

async function handleFileUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return

  const lower = file.name.toLowerCase()
  if (!lower.endsWith('.html') && !lower.endsWith('.htm')) {
    showToast('只支持上传 .html 或 .htm 文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)

    const res = await uploadCopyHtml(formData)
    if (!res.success) {
      throw new Error(res.error || '上传失败')
    }

    if (res.exists) {
      uploadInputRef.value.value = ''
      const confirmed = await requestConfirmation({
        title: '文件已存在',
        message: `"${res.filename}" 在"${res.country}"中已存在，是否覆盖？`,
        confirmText: '覆盖'
      })
      if (confirmed) {
        const formData2 = new FormData()
        formData2.append('file', file)
        formData2.append('country', res.country)
        const confirmRes = await confirmUploadCopyHtml(formData2)
        if (!confirmRes.success) {
          throw new Error(confirmRes.error || '覆盖失败')
        }
        await refreshFileList()
        const targetCountry = countries.value.find(c => c.name === confirmRes.country)
        if (targetCountry && confirmRes.file) {
          await openFile(targetCountry.name, confirmRes.file, true)
        }
        showToast('文件已覆盖上传')
      }
    } else {
      await refreshFileList()
      const targetCountry = countries.value.find(c => c.name === res.country)
      if (targetCountry && res.file) {
        await openFile(targetCountry.name, res.file, true)
      }
      showToast('上传成功')
    }
  } catch (e) {
    showToast(e.message || '上传失败')
  } finally {
    uploading.value = false
    uploadInputRef.value.value = ''
  }
}

function getCardCleanHtml(cardElement) {
  const clone = cardElement.cloneNode(true)
  clone.querySelectorAll('.copy-poster-btn, .copy-made-btn, .copy-reviewed-btn, .copy-published-btn, .copy-edit-code-btn').forEach(n => n.remove())
  return clone.outerHTML
}

function handleCodeEditorKeydown(event) {
  if (event.key === 'Tab') {
    event.preventDefault()
    const textarea = event.target
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const value = textarea.value
    textarea.value = value.substring(0, start) + '  ' + value.substring(end)
    textarea.selectionStart = textarea.selectionEnd = start + 2
    cardEditDraft.value = textarea.value
  }
}

function syncLineNumbersScroll() {
  const textarea = codeTextareaRef.value
  const lineNumbers = codeLineNumbersRef.value
  if (!textarea || !lineNumbers) return
  lineNumbers.scrollTop = textarea.scrollTop
}

function openCardCodeEditor(cardElement) {
  activeEditCardElement.value = cardElement
  cardEditDraft.value = getCardCleanHtml(cardElement)
  cardEditError.value = ''
  cardEditDialogVisible.value = true
}

function closeCardCodeEditor() {
  cardEditDialogVisible.value = false
  activeEditCardElement.value = null
  cardEditDraft.value = ''
  cardEditError.value = ''
}

function confirmCardCodeEdit() {
  const oldCard = activeEditCardElement.value
  if (!oldCard) {
    closeCardCodeEditor()
    return
  }

  const code = (cardEditDraft.value || '').trim()
  if (!code) {
    cardEditError.value = '代码不能为空'
    return
  }

  const doc = getIframeDoc()
  if (!doc) {
    cardEditError.value = '无法获取文档对象'
    return
  }

  try {
    const parser = new DOMParser()
    const parsedDoc = parser.parseFromString(`<div>${code}</div>`, 'text/html')
    const wrapper = parsedDoc.body.firstElementChild
    if (!wrapper || !wrapper.firstElementChild) {
      cardEditError.value = '代码无效，必须包含至少一个HTML元素'
      return
    }

    const newCard = wrapper.firstElementChild

    if (newCard.querySelector('script')) {
      cardEditError.value = '代码中不能包含 script 标签'
      return
    }

    if (oldCard.parentNode) {
      oldCard.parentNode.replaceChild(newCard, oldCard)
    } else {
      cardEditError.value = '无法替换卡片，找不到父节点'
      return
    }

    const computedStyle = doc.defaultView.getComputedStyle(newCard)
    if (computedStyle.position === 'static') {
      newCard.style.position = 'relative'
    }

    const btn = doc.createElement('button')
    btn.type = 'button'
    btn.className = 'copy-poster-btn'
    btn.textContent = '复制'
    btn.title = '复制此海报文案'
    btn.onclick = (e) => {
      e.stopPropagation()
      handleCopyCard(newCard)
    }
    newCard.appendChild(btn)

    createMadeButton(newCard, doc)
    createReviewedButton(newCard, doc)
    createPublishedButton(newCard, doc)
    createEditCodeButton(newCard, doc)

    hasUnsavedChanges.value = true
    closeCardCodeEditor()
    showToast('卡片代码已更新')
  } catch (e) {
    cardEditError.value = `代码解析失败: ${e.message}`
  }
}

function createEditCodeButton(card, doc) {
  if (card.querySelector('.copy-edit-code-btn')) return

  const btn = doc.createElement('button')
  btn.type = 'button'
  btn.className = 'copy-edit-code-btn'
  btn.textContent = '编辑代码'
  btn.title = '编辑此卡片的HTML代码'
  btn.onclick = (e) => {
    e.stopPropagation()
    openCardCodeEditor(card)
  }
  card.appendChild(btn)
}

async function deleteBoardFile(file) {
  if (!file || file.type !== 'copy_board' || saving.value) return

  const confirmed = await requestConfirmation({
    title: '删除原生卡片页',
    message: `确定要删除“${file.name}”吗？此操作无法撤销。`,
    confirmText: '删除'
  })
  if (!confirmed) return

  saving.value = true
  try {
    const res = await deleteCopyBoard(file.relative_path)
    if (!res.success) {
      throw new Error(res.error || '删除原生卡片页失败')
    }

    if (selectedFile.value?.relative_path === file.relative_path) {
      selectedCountry.value = ''
      selectedFile.value = null
      htmlContent.value = ''
      originalHtmlContent.value = ''
      boardCards.value = []
      originalBoardCards.value = []
      hasUnsavedChanges.value = false
      closeEditDialog()
    }

    await refreshFileList()
    showToast('已删除原生卡片页')
  } catch (e) {
    showToast(e.message || '删除原生卡片页失败')
  } finally {
    saving.value = false
  }
}

function getBoardDisplayName(file) {
  return (file?.name || '').replace(/\.copy\.json$/i, '')
}

function openRenameBoardDialog(file) {
  if (!file || file.type !== 'copy_board' || saving.value) return
  renameTargetFile.value = file
  renameDraft.value = getBoardDisplayName(file)
  renameDialogVisible.value = true
  nextTick(() => {
    document.querySelector('.copy-rename-dialog__input')?.focus()
    document.querySelector('.copy-rename-dialog__input')?.select()
  })
}

function closeRenameBoardDialog() {
  renameDialogVisible.value = false
  renameTargetFile.value = null
  renameDraft.value = ''
}

async function confirmRenameBoardFile() {
  const file = renameTargetFile.value
  const nextName = renameDraft.value.trim()
  if (!file || file.type !== 'copy_board' || saving.value) return
  if (!nextName) {
    showToast('请输入新的页面名称')
    return
  }
  if (nextName === getBoardDisplayName(file) || nextName === file.name) {
    closeRenameBoardDialog()
    return
  }

  saving.value = true
  try {
    const res = await renameCopyBoard(file.relative_path, nextName)
    if (!res.success) {
      throw new Error(res.error || '重命名原生卡片页失败')
    }

    if (selectedFile.value?.relative_path === file.relative_path) {
      selectedFile.value = res.file
    }

    await refreshFileList()
    closeRenameBoardDialog()
    showToast('已重命名原生卡片页')
  } catch (e) {
    showToast(e.message || '重命名原生卡片页失败')
  } finally {
    saving.value = false
  }
}

function createMadeButton(card, doc) {
  if (card.hasAttribute(MADE_TAG_ATTR)) return
  if (card.querySelector('.copy-made-btn')) return

  const madeBtn = doc.createElement('button')
  madeBtn.type = 'button'
  madeBtn.className = 'copy-made-btn'
  madeBtn.textContent = '未做'
  madeBtn.title = '标记此卡片为已做'
  madeBtn.onclick = (e) => {
    e.stopPropagation()
    markCardAsMade(card, doc)
  }
  card.appendChild(madeBtn)
}

function createReviewedButton(card, doc) {
  if (card.hasAttribute(REVIEWED_TAG_ATTR)) return
  if (card.querySelector('.copy-reviewed-btn')) return

  const reviewedBtn = doc.createElement('button')
  reviewedBtn.type = 'button'
  reviewedBtn.className = 'copy-reviewed-btn'
  reviewedBtn.textContent = '未审核'
  reviewedBtn.title = '标记此卡片为已审核'
  reviewedBtn.onclick = (e) => {
    e.stopPropagation()
    markCardAsReviewed(card, doc)
  }
  card.appendChild(reviewedBtn)
}

function markCardAsMade(card, doc) {
  if (card.hasAttribute(MADE_TAG_ATTR)) return

  const computedStyle = doc.defaultView.getComputedStyle(card)
  if (computedStyle.position === 'static') {
    card.style.position = 'relative'
  }

  const tag = doc.createElement('div')
  tag.className = MADE_TAG_CLASS
  tag.textContent = '已做'
  tag.style.cssText = 'position:absolute;top:12px;left:12px;z-index:50;padding:4px 10px;border-radius:20px;background:linear-gradient(135deg,#10b981 0%,#059669 100%);color:#fff;font-size:11px;font-weight:700;box-shadow:0 2px 8px rgba(16,185,129,0.4);cursor:pointer;'
  tag.title = '点击取消标记'
  tag.onclick = (e) => {
    e.stopPropagation()
    tag.remove()
    card.removeAttribute(MADE_TAG_ATTR)
    hasUnsavedChanges.value = true
    createMadeButton(card, doc)
    showToast('已取消“已做”标记')
  }
  card.appendChild(tag)
  card.setAttribute(MADE_TAG_ATTR, 'true')
  hasUnsavedChanges.value = true

  const btn = card.querySelector('.copy-made-btn')
  if (btn) btn.remove()
  showToast('已标记为“已做”')
}

function markCardAsReviewed(card, doc) {
  if (card.hasAttribute(REVIEWED_TAG_ATTR)) return

  const computedStyle = doc.defaultView.getComputedStyle(card)
  if (computedStyle.position === 'static') {
    card.style.position = 'relative'
  }

  const tag = doc.createElement('div')
  tag.className = REVIEWED_TAG_CLASS
  tag.textContent = '已审核'
  tag.style.cssText = 'position:absolute;top:12px;left:70px;z-index:50;padding:4px 10px;border-radius:20px;background:linear-gradient(135deg,#8b5cf6 0%,#7c3aed 100%);color:#fff;font-size:11px;font-weight:700;box-shadow:0 2px 8px rgba(139,92,246,0.4);cursor:pointer;'
  tag.title = '点击取消标记'
  tag.onclick = (e) => {
    e.stopPropagation()
    tag.remove()
    card.removeAttribute(REVIEWED_TAG_ATTR)
    hasUnsavedChanges.value = true
    createReviewedButton(card, doc)
    showToast('已取消“已审核”标记')
  }
  card.appendChild(tag)
  card.setAttribute(REVIEWED_TAG_ATTR, 'true')
  hasUnsavedChanges.value = true

  const btn = card.querySelector('.copy-reviewed-btn')
  if (btn) btn.remove()
  showToast('已标记为“已审核”')
}

// 在 iframe 海报卡片上注入"未发/已发"按钮（与 made/reviewed 同款竖排徽章）
// 实现逻辑：仅在卡片未标记 PUBLISHED_TAG_ATTR 且不存在 published 按钮时创建，避免重复注入
function createPublishedButton(card, doc) {
  if (card.hasAttribute(PUBLISHED_TAG_ATTR)) return
  if (card.querySelector('.copy-published-btn')) return

  const publishedBtn = doc.createElement('button')
  publishedBtn.type = 'button'
  publishedBtn.className = 'copy-published-btn'
  publishedBtn.textContent = '未发'
  publishedBtn.title = '标记此卡片为已发'
  publishedBtn.onclick = (e) => {
    e.stopPropagation()
    markCardAsPublished(card, doc)
  }
  card.appendChild(publishedBtn)
}

// 将 iframe 海报卡片标记为"已发"，并在卡片左上角追加蓝色"已发"徽章
// 实现逻辑：
//   1) 幂等：已标记直接 return，避免重复
//   2) 卡片 position 不是 relative/absolute 时强制设为 relative，徽章定位才生效
//   3) 点击徽章可取消标记，复原未发按钮
function markCardAsPublished(card, doc) {
  if (card.hasAttribute(PUBLISHED_TAG_ATTR)) return

  const computedStyle = doc.defaultView.getComputedStyle(card)
  if (computedStyle.position === 'static') {
    card.style.position = 'relative'
  }

  const tag = doc.createElement('div')
  tag.className = PUBLISHED_TAG_CLASS
  tag.textContent = '已发'
  tag.style.cssText = 'position:absolute;top:12px;left:128px;z-index:50;padding:4px 10px;border-radius:20px;background:linear-gradient(135deg,#3b82f6 0%,#2563eb 100%);color:#fff;font-size:11px;font-weight:700;box-shadow:0 2px 8px rgba(59,130,246,0.4);cursor:pointer;'
  tag.title = '点击取消标记'
  tag.onclick = (e) => {
    e.stopPropagation()
    tag.remove()
    card.removeAttribute(PUBLISHED_TAG_ATTR)
    hasUnsavedChanges.value = true
    createPublishedButton(card, doc)
    showToast('已取消“已发”标记')
  }
  card.appendChild(tag)
  card.setAttribute(PUBLISHED_TAG_ATTR, 'true')
  hasUnsavedChanges.value = true

  const btn = card.querySelector('.copy-published-btn')
  if (btn) btn.remove()
  showToast('已标记为“已发”')
}

async function refreshFileList() {
  loading.value = true
  error.value = ''
  try {
    const res = await getCopyFiles()
    if (res.success) {
      countries.value = res.countries || []
    } else {
      error.value = res.error || '获取文件列表失败'
    }
  } catch (e) {
    error.value = e.message || '获取文件列表失败'
  } finally {
    loading.value = false
  }
}

async function openFile(countryName, file, force = false) {
  if (!force && hasUnsavedChanges.value) {
    const confirmed = await requestConfirmation({
      title: '切换文件',
      message: '当前文件有未保存修改，切换后会丢失这些内容。',
      confirmText: '继续切换'
    })
    if (!confirmed) return
  }

  // 先释放上一个文件的协作会话
  await releaseCollabSession()

  // 切换文件时清空待恢复的滚动位置，防止上一个文件的 scrollTop/scrollLeft 被恢复到新打开的文件
  pendingIframeScrollRestore = null

  selectedCountry.value = countryName
  selectedFile.value = file
  contentLoading.value = true
  error.value = ''
  htmlContent.value = ''
  originalHtmlContent.value = ''
  boardCards.value = []
  originalBoardCards.value = []
  hasUnsavedChanges.value = false
  closeEditDialog()

  // 协作：先申请文件级锁
  // 实现逻辑：调用 acquireFileLock；若 conflict=true 表示文件已被他人编辑，弹公共 ConfirmDialog 询问用户是否以只读模式查看
  try {
    const fileKey = file?.relative_path || ''
    const myToken = generateToken()
    const lockResult = await collab.acquireFileLock(fileKey, myToken)
    if (lockResult.ok) {
      // 首次尝试即拿到锁
      fileLockToken.value = lockResult.token || myToken
      fileLockHeldByMe.value = true
      readOnlyMode.value = false
      collab.startHeartbeat(fileKey, fileLockToken.value)
      startHandoffPolling(fileKey)
      subscribeCollabToFile(fileKey, true)
    } else if (lockResult.locked && lockResult.conflict) {
      // 可能是页面刷新导致的竞态（旧会话的释放尚未完成），等待 2 秒后重试一次
      await new Promise(r => setTimeout(r, 2000))
      const retryResult = await collab.acquireFileLock(fileKey, myToken)
      if (retryResult.ok) {
        fileLockToken.value = retryResult.token || myToken
        fileLockHeldByMe.value = true
        readOnlyMode.value = false
        collab.startHeartbeat(fileKey, fileLockToken.value)
        startHandoffPolling(fileKey)
        subscribeCollabToFile(fileKey, true)
      } else if (retryResult.locked && retryResult.conflict) {
        // 重试仍冲突 → 确实有其他用户
        const choice = await requestConfirmation({
          title: '该海报正在被其他用户编辑中',
          message: '请先编辑其他海报。如需查看此文件，可以以只读模式打开。',
          confirmText: '以只读模式查看'
        })
        if (!choice) {
          selectedFile.value = null
          contentLoading.value = false
          return
        }
        readOnlyMode.value = true
        fileLockHeldByMe.value = false
        fileLockToken.value = ''
        subscribeCollabToFile(fileKey, false)
      } else {
        showToast(retryResult.error || '申请编辑权限失败')
        selectedFile.value = null
        contentLoading.value = false
        return
      }
    } else {
      showToast(lockResult.error || '申请编辑权限失败')
      selectedFile.value = null
      contentLoading.value = false
      return
    }
  } catch (e) {
    showToast(e.message || '申请编辑权限失败')
    selectedFile.value = null
    contentLoading.value = false
    return
  }

  try {
    const res = isBoardFile(file)
      ? await getCopyBoardContent(file.relative_path)
      : await getCopyContent(file.relative_path)
    if (res.success) {
      if (isBoardFile(file)) {
        boardCards.value = cloneCards(res.cards || [])
        originalBoardCards.value = cloneCards(res.cards || [])
        // 给每个 card 注入 data-block-id（若已有则保留）
        for (const card of boardCards.value) {
          if (!card.id) {
            card.id = generateToken()
          }
        }
      } else {
        htmlContent.value = res.content
        originalHtmlContent.value = res.content
        iframeVersion.value += 1
      }
      await nextTick()
    } else {
      error.value = res.error || '读取文件失败'
    }
  } catch (e) {
    error.value = e.message || '读取文件失败'
  } finally {
    contentLoading.value = false
  }
}

// 订阅协作事件到指定 file_key；isHolder 表示本人是否持有文件锁
function subscribeCollabToFile(fileKey, isHolder) {
  // 先把上一份订阅清掉
  if (unsubscribeCollab) {
    try { unsubscribeCollab() } catch (e) { /* ignore */ }
    unsubscribeCollab = null
  }
  unsubscribeCollab = collab.subscribeFile(fileKey, {
    onFileLocked(data) {
      if (!isHolder) {
        readOnlyMode.value = true
      }
    },
    onFileUnlocked() {
      // 文件被解锁；若当前是只读用户则无需额外提示
    },
    onContentUpdate(data) {
      // 文件级别的内容同步：持有文件锁的用户保存后，服务端广播完整内容，只读客户端直接更新 iframe
      if (!data || !data.content) return
      if (selectedFile.value?.relative_path !== fileKey) return
      // 仅只读用户接受远程内容同步（编辑中的用户不需要，因为他们自己的保存已经更新了本地 iframe）
      if (!readOnlyMode.value) return
      // 在 iframe 重建（iframeVersion += 1）之前暂存当前滚动位置，
      // 只读用户收到远端同步时不希望页面跳到顶部
      const currentIframe = iframeRef.value
      if (currentIframe?.contentWindow) {
        const win = currentIframe.contentWindow
        const docEl = currentIframe.contentDocument?.documentElement
        pendingIframeScrollRestore = {
          scrollTop: win.scrollY || docEl?.scrollTop || 0,
          scrollLeft: win.scrollX || docEl?.scrollLeft || 0
        }
      }
      // 以新内容刷新 iframe
      htmlContent.value = data.content
      originalHtmlContent.value = data.content
      iframeVersion.value += 1
      showToast('内容已自动更新（其他用户保存了修改）')
    },
    onPresenceCount(data) {
      presenceCount.value = data.count || 0
    }
  })
}

function getIframeDoc() {
  const iframe = iframeRef.value
  if (!iframe) return null
  return iframe.contentDocument || iframe.contentWindow?.document || null
}

function onIframeLoad() {
  injectRuntimeTools()
  // 恢复保存前暂存的滚动位置，避免保存后页面跳到顶部
  // 实现逻辑：使用 requestAnimationFrame 等到 iframe 内 DOM 渲染完再 scrollTo，
  //          否则在某些内容高度尚未稳定时调用会被后续布局覆盖
  if (pendingIframeScrollRestore) {
    const { scrollTop, scrollLeft } = pendingIframeScrollRestore
    pendingIframeScrollRestore = null
    const iframe = iframeRef.value
    if (iframe?.contentWindow) {
      requestAnimationFrame(() => {
        iframe.contentWindow.scrollTo(scrollLeft, scrollTop)
      })
    }
  }
}

function injectRuntimeTools() {
  const doc = getIframeDoc()
  if (!doc?.body) return
  injectRuntimeStyle(doc)
  injectCopyButtons(doc)
  attachInlineCopyButtonHandler(doc)
  if (editMode.value) {
    wrapEditableTextNodes(doc)
    attachEditorClickHandler(doc)
  }
}

function injectRuntimeStyle(doc) {
  if (doc.getElementById(RUNTIME_STYLE_ID)) return

  const style = doc.createElement('style')
  style.id = RUNTIME_STYLE_ID
  style.textContent = `
    .poster-card, .poster, .vertical-poster {
      position: relative;
      overflow: visible !important;
    }
    .copy-poster-btn {
      position: absolute; top: 12px; right: 40px; z-index: 50;
      padding: 6px 14px; border-radius: 20px;
      border: 1px solid rgba(255, 215, 0, 0.4);
      background: rgba(0, 0, 0, 0.65); color: #FFD700;
      font-size: 12px; font-weight: 600; cursor: pointer;
      backdrop-filter: blur(6px); transition: all 0.2s;
      white-space: nowrap; font-family: inherit;
    }
    .copy-poster-btn:hover {
      background: rgba(255, 215, 0, 0.2); border-color: #FFD700;
      transform: scale(1.05);
    }
    .copy-poster-btn:active { transform: scale(0.95); }
    .copy-edit-code-btn {
      position: absolute; top: 12px; right: 108px; z-index: 50;
      padding: 6px 14px; border-radius: 20px;
      border: 1px solid rgba(74, 158, 255, 0.4);
      background: rgba(0, 0, 0, 0.65); color: #4a9eff;
      font-size: 12px; font-weight: 600; cursor: pointer;
      backdrop-filter: blur(6px); transition: all 0.2s;
      white-space: nowrap; font-family: inherit;
    }
    .copy-edit-code-btn:hover {
      background: rgba(74, 158, 255, 0.2); border-color: #4a9eff;
      transform: scale(1.05);
    }
    .copy-edit-code-btn:active { transform: scale(0.95); }
    .copy-made-btn {
      position: absolute; top: 12px; right: -28px; z-index: 50;
      width: 24px; min-height: 64px; padding: 8px 4px; border-radius: 0 8px 8px 0;
      border: 1px solid rgba(16, 185, 129, 0.5);
      background: rgba(16, 185, 129, 0.15); color: #10b981;
      font-size: 12px; font-weight: 700; cursor: pointer;
      writing-mode: vertical-rl; text-orientation: mixed;
      letter-spacing: 4px; font-family: inherit;
      display: flex; align-items: center; justify-content: center;
      line-height: 1;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .copy-made-btn:hover {
      background: rgba(16, 185, 129, 0.3); border-color: #10b981;
    }
    .copy-made-btn:active { opacity: 0.7; }
    .copy-reviewed-btn {
      position: absolute; top: 84px; right: -28px; z-index: 50;
      width: 24px; min-height: 76px; padding: 8px 4px; border-radius: 0 8px 8px 0;
      border: 1px solid rgba(139, 92, 246, 0.5);
      background: rgba(139, 92, 246, 0.15); color: #8b5cf6;
      font-size: 12px; font-weight: 700; cursor: pointer;
      writing-mode: vertical-rl; text-orientation: mixed;
      letter-spacing: 4px; font-family: inherit;
      display: flex; align-items: center; justify-content: center;
      line-height: 1;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .copy-reviewed-btn:hover {
      background: rgba(139, 92, 246, 0.3); border-color: #8b5cf6;
    }
    .copy-reviewed-btn:active { opacity: 0.7; }
    .copy-published-btn {
      position: absolute; top: 168px; right: -28px; z-index: 50;
      width: 24px; min-height: 64px; padding: 8px 4px; border-radius: 0 8px 8px 0;
      border: 1px solid rgba(59, 130, 246, 0.5);
      background: rgba(59, 130, 246, 0.15); color: #3b82f6;
      font-size: 12px; font-weight: 700; cursor: pointer;
      writing-mode: vertical-rl; text-orientation: mixed;
      letter-spacing: 4px; font-family: inherit;
      display: flex; align-items: center; justify-content: center;
      line-height: 1;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .copy-published-btn:hover {
      background: rgba(59, 130, 246, 0.3); border-color: #3b82f6;
    }
    .copy-published-btn:active { opacity: 0.7; }
    .${MADE_TAG_CLASS}:hover { filter: brightness(1.15); }
    .${REVIEWED_TAG_CLASS}:hover { filter: brightness(1.15); }
    .${PUBLISHED_TAG_CLASS}:hover { filter: brightness(1.15); }
    .${EDITABLE_CLASS} {
      cursor: text;
      border-radius: 4px;
      transition: background 0.15s, box-shadow 0.15s;
    }
    .${EDITABLE_CLASS}:hover {
      background: rgba(255, 236, 153, 0.42);
      box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2);
    }
    .${EDITED_CLASS} {
      background: #b91c1c !important;
      color: #ffffff !important;
      box-shadow: 0 0 0 2px rgba(127, 29, 29, 0.35);
      border-radius: 4px;
      padding: 0 3px;
    }
  `
  doc.head.appendChild(style)
}

function injectCopyButtons(doc) {
  const foundCards = new Set()

  // 通过已知的网格容器获取所有直接子元素（最通用的方式）
  const containers = doc.querySelectorAll('.posters-grid, .posters-container, [class*="posters-"]')
  for (const container of containers) {
    for (const child of container.children) {
      foundCards.add(child)
    }
  }

  // 兜底：通过已知的卡片类名查找（兼容不在容器内的卡片）
  for (const card of doc.querySelectorAll('.poster-card, .poster, .vertical-poster')) {
    foundCards.add(card)
  }

  foundCards.forEach((card) => {
    const computedStyle = doc.defaultView.getComputedStyle(card)
    if (computedStyle.position === 'static') {
      card.style.position = 'relative'
    }

    if (!card.querySelector('.copy-poster-btn')) {
      const btn = doc.createElement('button')
      btn.type = 'button'
      btn.className = 'copy-poster-btn'
      btn.textContent = '复制'
      btn.title = '复制此海报文案'
      btn.onclick = (e) => {
        e.stopPropagation()
        handleCopyCard(card)
      }
      card.appendChild(btn)
    }

    if (!card.hasAttribute(MADE_TAG_ATTR) && !card.querySelector('.copy-made-btn')) {
      createMadeButton(card, doc)
    }

    if (!card.hasAttribute(REVIEWED_TAG_ATTR) && !card.querySelector('.copy-reviewed-btn')) {
      createReviewedButton(card, doc)
    }

    if (!card.hasAttribute(PUBLISHED_TAG_ATTR) && !card.querySelector('.copy-published-btn')) {
      createPublishedButton(card, doc)
    }

    createEditCodeButton(card, doc)
  })
}

function attachInlineCopyButtonHandler(doc) {
  if (doc.__copyInlineCopyButtonHandler) return

  doc.__copyInlineCopyButtonHandler = async (event) => {
    const button = event.target.closest?.('.copy-btn')
    if (!button) return

    const copyText = button.getAttribute('data-copy-text') || button.closest('.tags-cell')?.querySelector('.tags-text')?.textContent || ''
    if (!copyText.trim()) return

    event.preventDefault()
    event.stopPropagation()

    const copyType = button.getAttribute('data-copy-type')
    const ok = await copyToClipboard(copyText.trim())
    showToast(ok ? `已复制${copyType ? `${copyType}标签` : '到剪贴板'}` : '复制失败')
  }

  doc.addEventListener('click', doc.__copyInlineCopyButtonHandler, true)
}

function isEditableTextNode(node) {
  if (!node.nodeValue || !node.nodeValue.trim()) return false

  const parent = node.parentElement
  if (!parent) return false

  const ignoredTags = new Set(['SCRIPT', 'STYLE', 'META', 'TITLE', 'NOSCRIPT', 'TEXTAREA', 'INPUT', 'BUTTON'])
  if (ignoredTags.has(parent.tagName)) return false
  if (parent.closest('.copy-poster-btn')) return false
  if (parent.closest('.copy-made-btn')) return false
  if (parent.closest('.copy-reviewed-btn')) return false
  if (parent.closest('.copy-published-btn')) return false
  if (parent.closest('.copy-edit-code-btn')) return false
  if (parent.closest('script')) return false
  if (parent.classList.contains(EDITABLE_CLASS)) return false

  return Boolean(parent.closest('body'))
}

function wrapEditableTextNodes(doc) {
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      return isEditableTextNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
    }
  })

  const nodes = []
  while (walker.nextNode()) {
    nodes.push(walker.currentNode)
  }

  nodes.forEach((node) => {
    const parent = node.parentElement
    if (!parent) return
    // 若该文本节点已位于一个被标记的 span 中（已被 wrap 过），则跳过
    if (parent.classList && parent.classList.contains(EDITABLE_CLASS)) return
    const span = doc.createElement('span')
    span.className = EDITABLE_CLASS
    span.textContent = node.nodeValue
    node.parentNode.replaceChild(span, node)
  })
}

function attachEditorClickHandler(doc) {
  if (doc.__copyEditorClickHandler) return

  doc.__copyEditorClickHandler = (event) => {
    if (!editMode.value) return
    const target = event.target.closest?.(`.${EDITABLE_CLASS}`)
    if (!target || target.closest('.copy-poster-btn')) return
    event.preventDefault()
    event.stopPropagation()
    openEditDialog(target)
  }

  doc.addEventListener('click', doc.__copyEditorClickHandler, true)
}

function openEditDialog(span) {
  // 只读模式禁止进入编辑
  if (readOnlyMode.value) {
    showToast('当前为只读模式，无法编辑')
    return
  }
  // 若没有文件锁，也无法进入编辑
  if (!fileLockHeldByMe.value || !fileLockToken.value) {
    showToast('没有编辑权限，请重新打开文件')
    return
  }
  activeEditSpan.value = span
  editDraft.value = span.textContent
  editDialogVisible.value = true
  nextTick(() => {
    document.querySelector('.copy-edit-dialog__textarea')?.focus()
  })
}

function closeEditDialog() {
  activeEditSpan.value = null
  editDraft.value = ''
  editDialogVisible.value = false
}

function requestConfirmation({ title, message, confirmText = '确定' }) {
  confirmDialogTitle.value = title
  confirmDialogMessage.value = message
  confirmDialogConfirmText.value = confirmText
  confirmDialogVisible.value = true

  return new Promise((resolve) => {
    pendingConfirmResolve = resolve
  })
}

function closeConfirmDialog(result) {
  confirmDialogVisible.value = false
  if (pendingConfirmResolve) {
    pendingConfirmResolve(result)
    pendingConfirmResolve = null
  }
}

function confirmTextEdit() {
  const span = activeEditSpan.value
  if (!span) {
    closeEditDialog()
    return
  }

  const nextText = editDraft.value
  if (nextText !== span.textContent) {
    span.textContent = nextText
    span.classList.add(EDITED_CLASS)
    span.setAttribute(EDITED_ATTR, 'true')
    hasUnsavedChanges.value = true
  }

  closeEditDialog()
}

function toggleEditMode() {
  editMode.value = !editMode.value
  if (editMode.value) {
    injectRuntimeTools()
    showToast('文字编辑已开启')
  } else {
    closeEditDialog()
    showToast('文字编辑已关闭')
  }
}

function getCleanText(el) {
  const clone = el.cloneNode(true)
  clone.querySelectorAll('i, .scheme-number, .copy-poster-btn, .copy-made-btn, .copy-reviewed-btn, .copy-published-btn').forEach(n => n.remove())
  return (clone.innerText || clone.textContent || '').trim()
}

function pushUniqueText(target, text) {
  const clean = cleanCopyText(text || '')
  if (clean && !target.includes(clean)) target.push(clean)
}

// 兜底解析：扫描 .poster-content 内使用内联 style 而无 class 的直接子元素
// 实现逻辑：现有 mainSelectors / subSelectors / parseModuleTitleSections 只覆盖带特定 class 的容器，
//          但部分海报（如瑙鲁2026年5月13日第5张"申请条件·主申请人"中的红框条件列表、
//          爱尔兰 5.13 中的"核心优势"内联容器、迪拜 5.13 中的"主申/附属申请人"块等）
//          全部使用纯内联 style 而无 class，这些内容会被遗漏导致复制缺失。
//          此函数遍历 .poster-content 的直接子元素，跳过已被已知选择器覆盖的元素，
//          收集剩余内联容器的文本并去重后追加到主内容区。
function parseInlineStyleContent(cardElement) {
  const content = cardElement.querySelector('.poster-content') || cardElement
  if (!content) return []

  // 已知选择器（与 parsePosterCard 内部 mainSelectors / subSelectors 保持一致），
  // 用于标记"已被前面流程覆盖"的元素，避免兜底逻辑产生重复文本。
  const knownSelectors = [
    '.module-title', '.module-box', '.two-cols', '.data-table', '.price-block',
    '.bullet-list', '.grid-2col', '.section', '.content-section', '.info-box',
    '.info-card', '.project-law', '.investment-threshold', '.threshold-card',
    '.condition-list', '.conditions-list', '.process-flow', '.process-steps',
    '.advantage-list', '.advantage-card', '.tag-list', '.highlight-strip',
    '.step-list', '.tag-group', '.stat-row', '.col',
    '.main-title', '.subtitle', '.bottom-quote', '.footer-note',
    '.visual-mock', '.gold-edge', '.gold-bar', '.divider-light',
    '.highlight-box', '.feature-list', '.grid-layout', '.comparison-layout',
    '.big-number', '.stats-container', '.asymmetric-layout', '.icon-container',
    '.centered-layout', '.project-badge', '.price-tag', '.scheme-description',
    '.timeline-layout', '.timeline-item', '.poster-footer', '.poster-title',
    '.poster-subtitle'
  ]
  const handled = new Set()
  for (const sel of knownSelectors) {
    for (const el of content.querySelectorAll(sel)) {
      handled.add(el)
    }
  }

  const texts = []
  for (const child of content.children) {
    if (handled.has(child)) continue
    if (child.tagName === 'SCRIPT' || child.tagName === 'STYLE') continue
    const text = getCleanText(child)
    if (text) texts.push(text)
  }
  return texts
}

function getFallbackCardText(cardElement, knownTexts = []) {
  const text = cleanCopyText(getCleanText(cardElement))
  if (!text) return ''

  let fallback = text
  for (const known of knownTexts) {
    const cleanKnown = cleanCopyText(known || '')
    if (!cleanKnown) continue
    fallback = fallback.replace(cleanKnown, '').trim()
  }
  return cleanCopyText(fallback)
}

function parseModuleTitleSections(cardElement) {
  const content = cardElement.querySelector('.poster-content') || cardElement
  const sections = []
  const children = Array.from(content.children)

  for (let index = 0; index < children.length; index += 1) {
    const titleElement = children[index]
    if (!titleElement.classList?.contains('module-title')) continue

    const moduleTitle = getCleanText(titleElement)
    const bodyParts = []

    for (let nextIndex = index + 1; nextIndex < children.length; nextIndex += 1) {
      const nextElement = children[nextIndex]
      if (nextElement.classList?.contains('module-title')) break
      if (nextElement.classList?.contains('divider-light')) continue
      if (nextElement.classList?.contains('footer-note')) break

      pushUniqueText(bodyParts, getCleanText(nextElement))
    }

    if (moduleTitle) {
      sections.push(bodyParts.length > 0 ? `${moduleTitle}\n${bodyParts.join('\n')}` : moduleTitle)
    }
  }

  const footerNote = content.querySelector('.footer-note')
  return {
    sections,
    footer: footerNote ? getCleanText(footerNote) : ''
  }
}

function parsePosterCard(cardElement) {
  const isDarkTheme = (cardElement.classList.contains('poster') || cardElement.classList.contains('vertical-poster')) && !cardElement.classList.contains('poster-card')

  let title = ''
  let subtitle = ''
  const mainContentParts = []
  const subContentParts = []
  let bottom = ''

  if (isDarkTheme) {
    title = cardElement.querySelector('.poster-title')?.textContent?.trim() || ''
    subtitle = cardElement.querySelector('.poster-subtitle')?.textContent?.trim() || ''

    const mainSelectors = [
      '.highlight-box',
      '.feature-list',
      '.grid-layout',
      '.comparison-layout',
      '.big-number',
      '.stats-container',
      '.asymmetric-layout',
      '.icon-container',
      '.centered-layout',
      '.project-badge',
      '.price-tag',
      '.scheme-description'
    ]
    for (const sel of mainSelectors) {
      for (const el of cardElement.querySelectorAll(sel)) {
        pushUniqueText(mainContentParts, getCleanText(el))
      }
    }

    const subSelectors = ['.timeline-layout', '.timeline-item']
    for (const sel of subSelectors) {
      for (const el of cardElement.querySelectorAll(sel)) {
        pushUniqueText(subContentParts, getCleanText(el))
      }
    }

    const footer = cardElement.querySelector('.poster-footer')
    if (footer) {
      const tagTexts = []
      for (const tag of footer.querySelectorAll('.tag')) {
        const text = getCleanText(tag)
        if (text) tagTexts.push(text)
      }
      if (tagTexts.length > 0) subContentParts.push(tagTexts.join(' | '))
    }

    // 兜底：补抓深色主题中使用内联 style 而无 class 的容器
    for (const t of parseInlineStyleContent(cardElement)) {
      pushUniqueText(mainContentParts, t)
    }
  } else {
    title = cardElement.querySelector('.main-title')?.textContent?.trim() || ''
    subtitle = cardElement.querySelector('.subtitle')?.textContent?.trim() || ''

    const moduleParseResult = parseModuleTitleSections(cardElement)
    moduleParseResult.sections.forEach(section => pushUniqueText(mainContentParts, section))
    bottom = moduleParseResult.footer

    const mainSelectors = [
      '.module-box',
      '.two-cols',
      '.data-table',
      '.price-block',
      '.bullet-list',
      '.grid-2col',
      '.section',
      '.content-section',
      '.info-box',
      '.info-card',
      '.project-law',
      '.investment-threshold',
      '.threshold-card',
      '.condition-list',
      '.conditions-list',
      '.process-flow',
      '.process-steps',
      '.advantage-list',
      '.advantage-card',
      '.tag-list',
      '.highlight-strip'
    ]
    if (mainContentParts.length === 0) {
      for (const sel of mainSelectors) {
        for (const el of cardElement.querySelectorAll(sel)) {
          pushUniqueText(mainContentParts, getCleanText(el))
        }
      }
    }

    const subSelectors = ['.step-list', '.tag-group', '.stat-row']
    for (const sel of subSelectors) {
      for (const el of cardElement.querySelectorAll(sel)) {
        pushUniqueText(subContentParts, getCleanText(el))
      }
    }

    const bottomQuote = cardElement.querySelector('.bottom-quote')
    if (!bottom && bottomQuote) bottom = getCleanText(bottomQuote)

    // 兜底：补抓浅色主题（poster-card）中使用内联 style 而无 class 的容器
    // 例：瑙鲁 5.13 第5张"申请条件·主申请人"红框（<div style="margin: 16px 0;"> 内的 ✔/❌ 条件列表）、
    //     爱尔兰 5.13 中"核心优势"内联容器、迪拜 5.13 中"主申/附属申请人"块等。
    for (const t of parseInlineStyleContent(cardElement)) {
      pushUniqueText(mainContentParts, t)
    }
  }

  const lines = []
  if (title) lines.push('【大标题】', title, '')
  if (subtitle) lines.push('【副标题】', subtitle, '')
  if (mainContentParts.length > 0) lines.push('【主要突出内容】', mainContentParts.join('\n'), '')
  if (subContentParts.length > 0) lines.push('【次要内容】', subContentParts.join('\n'), '')
  if (bottom) lines.push('【底部内容】', bottom, '')

  return lines.join('\n').trim()
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (e) {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    return true
  }
}

function cleanCopyText(text) {
  return text
    .split('\n')
    .map(line => line.replace(/\s+/g, ' ').trim())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

async function handleCopyCard(cardElement) {
  const text = parsePosterCard(cardElement)
  if (!text) {
    showToast('未识别到文案内容')
    return
  }
  const cleaned = cleanCopyText(text)
  const ok = await copyToClipboard(cleaned)
  showToast(ok ? '已复制到剪贴板' : '复制失败')
}

function unwrapRuntimeEditableSpans(root) {
  root.querySelectorAll(`.${EDITABLE_CLASS}`).forEach((span) => {
    if (span.getAttribute(EDITED_ATTR) === 'true') {
      const editedParent = span.parentElement?.closest(`.${EDITED_CLASS}`)
      if (editedParent) {
        span.replaceWith(root.ownerDocument.createTextNode(span.textContent))
      } else {
        span.className = EDITED_CLASS
        span.removeAttribute(EDITED_ATTR)
        span.removeAttribute('contenteditable')
      }
      return
    }

    span.replaceWith(root.ownerDocument.createTextNode(span.textContent))
  })
}

function removeScriptGeneratedRows(root) {
  root.querySelectorAll('script').forEach((script) => {
    const scriptText = script.textContent || ''
    const containerMatch = scriptText.match(/getElementById\(['"]([^'"]+)['"]\)/)
    if (!containerMatch || !/appendChild\s*\(/.test(scriptText)) return

    const container = root.querySelector(`#${CSS.escape(containerMatch[1])}`)
    if (!container) return

    const generatedCount = (scriptText.match(/name\s*:/g) || []).length
    if (generatedCount <= 0) return

    const rows = Array.from(container.children).filter(child => child.classList?.contains('table-row'))
    if (rows.length > generatedCount) {
      rows.slice(generatedCount).forEach(row => row.remove())
    }
  })
}

function getCleanHtmlForSave() {
  const doc = getIframeDoc()
  if (!doc?.documentElement) return ''

  const cloneDoc = document.implementation.createHTMLDocument('')
  cloneDoc.documentElement.replaceWith(doc.documentElement.cloneNode(true))
  const root = cloneDoc.documentElement

  root.querySelector(`#${RUNTIME_STYLE_ID}`)?.remove()
  root.querySelectorAll('.copy-poster-btn').forEach(node => node.remove())
  root.querySelectorAll('.copy-made-btn').forEach(node => node.remove())
  root.querySelectorAll('.copy-reviewed-btn').forEach(node => node.remove())
  root.querySelectorAll('.copy-published-btn').forEach(node => node.remove())
  root.querySelectorAll('.copy-edit-code-btn').forEach(node => node.remove())
  unwrapRuntimeEditableSpans(root)
  removeScriptGeneratedRows(root)

  const doctype = doc.doctype
    ? `<!DOCTYPE ${doc.doctype.name}>`
    : '<!DOCTYPE html>'

  return `${doctype}\n${root.outerHTML}`
}

async function saveCurrentFile() {
  if (!selectedFile.value || saving.value) return
  // 只读模式禁止保存
  if (readOnlyMode.value) {
    showToast('当前为只读模式，无法保存')
    return
  }
  if (!fileLockHeldByMe.value || !fileLockToken.value) {
    showToast('编辑权限已失效，请重新打开文件')
    return
  }

  if (isBoardFile()) {
    saving.value = true
    try {
      const res = await saveCopyBoardContent(selectedFile.value.relative_path, boardCards.value, fileLockToken.value)
      if (!res.success) {
        if (res.code === 'LOCK_EXPIRED') {
          // 文件锁已失效 → 释放本地状态并提示
          showToast(res.error || '编辑权限已过期')
          fileLockToken.value = ''
          fileLockHeldByMe.value = false
          readOnlyMode.value = true
          return
        }
        throw new Error(res.error || '保存失败')
      }

      boardCards.value = cloneCards(res.cards || boardCards.value)
      originalBoardCards.value = cloneCards(boardCards.value)
      hasUnsavedChanges.value = false
      showToast('已保存修改')
      await refreshFileList()
    } catch (e) {
      showToast(e.message || '保存失败')
    } finally {
      saving.value = false
    }
    return
  }

  const content = getCleanHtmlForSave()
  if (!content.trim()) {
    showToast('没有可保存的HTML内容')
    return
  }

  // 在 iframe 重建（iframeVersion += 1）之前暂存当前滚动位置，
  // 这样在 onIframeLoad 完成后能恢复到保存前用户所在的位置，避免页面跳到顶部
  const currentIframe = iframeRef.value
  if (currentIframe?.contentWindow) {
    const win = currentIframe.contentWindow
    const docEl = currentIframe.contentDocument?.documentElement
    pendingIframeScrollRestore = {
      scrollTop: win.scrollY || docEl?.scrollTop || 0,
      scrollLeft: win.scrollX || docEl?.scrollLeft || 0
    }
  }

  saving.value = true
  try {
    const res = await saveCopyContent(selectedFile.value.relative_path, content, fileLockToken.value)
    if (!res.success) {
      if (res.code === 'LOCK_EXPIRED') {
        showToast(res.error || '编辑权限已过期')
        fileLockToken.value = ''
        fileLockHeldByMe.value = false
        readOnlyMode.value = true
        return
      }
      throw new Error(res.error || '保存失败')
    }

    htmlContent.value = content
    originalHtmlContent.value = content
    iframeVersion.value += 1
    hasUnsavedChanges.value = false
    showToast('已保存修改')
    await nextTick()
    injectRuntimeTools()
    await refreshFileList()
  } catch (e) {
    showToast(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function reloadCurrentFile() {
  if (!selectedCountry.value || !selectedFile.value) return
  if (hasUnsavedChanges.value) {
    const confirmed = await requestConfirmation({
      title: '重新载入文件',
      message: '当前文件有未保存修改，重新载入会丢失这些内容。',
      confirmText: '重新载入'
    })
    if (!confirmed) return
  }
  await openFile(selectedCountry.value, selectedFile.value, true)
}

async function discardCurrentChanges() {
  if (!hasUnsavedChanges.value) return
  const confirmed = await requestConfirmation({
    title: '撤销修改',
    message: '确定撤销当前文件未保存的文字修改吗？',
    confirmText: '撤销修改'
  })
  if (!confirmed) return
  if (isBoardFile()) {
    boardCards.value = cloneCards(originalBoardCards.value)
    hasUnsavedChanges.value = false
    return
  }
  htmlContent.value = originalHtmlContent.value
  iframeVersion.value += 1
  hasUnsavedChanges.value = false
  closeEditDialog()
  await nextTick()
  injectRuntimeTools()
}

// 在只读模式下，用户请求移交编辑权限（HTTP 轮询方案）
async function retryAcquireEditLock() {
  if (!selectedFile.value) return
  const fileKey = selectedFile.value.relative_path
  const myToken = generateToken()

  const lockResult = await collab.acquireFileLock(fileKey, myToken)
  if (lockResult.ok) {
    fileLockToken.value = lockResult.token || myToken
    fileLockHeldByMe.value = true
    readOnlyMode.value = false
    collab.startHeartbeat(fileKey, fileLockToken.value)
    startHandoffPolling(fileKey)
    subscribeCollabToFile(fileKey, true)
    showToast('已获得编辑权限')
    return
  }

  if (lockResult.conflict) {
    const confirmed = await requestConfirmation({
      title: '请求移交编辑权限',
      message: '是否向当前编辑者发送权限移交请求？',
      confirmText: '发送请求'
    })
    if (!confirmed) return

    await collab.sendHandoffRequest(fileKey, myToken)
    showToast('已发送移交请求，等待对方响应（15秒）...')

    // 轮询等待响应，每 1.5 秒一次，最多 10 次
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 1500))
      const status = await collab.pollHandoffResponse(fileKey)
      if (status === 'accepted') {
        const retryResult = await collab.acquireFileLock(fileKey, myToken)
        if (retryResult.ok) {
          fileLockToken.value = retryResult.token || myToken
          fileLockHeldByMe.value = true
          readOnlyMode.value = false
          collab.startHeartbeat(fileKey, fileLockToken.value)
          startHandoffPolling(fileKey)
          subscribeCollabToFile(fileKey, true)
          showToast('已获得编辑权限（对方已移交）')
        } else {
          showToast('获取编辑权限失败，请重试')
        }
        return
      } else if (status === 'rejected') {
        showToast('对方拒绝了编辑权限移交')
        return
      }
      // 'pending' 或 'none' → 继续轮询
    }
    showToast('移交请求超时，对方未响应')
    return
  }

  showToast(lockResult.error || '获取编辑权限失败')
}

// 收到移交请求 → 弹出确认框，确认后自动保存并移交
async function handleIncomingHandoffRequest() {
  if (!selectedFile.value || !fileLockHeldByMe.value) return

  let confirmMessage = '有用户想接管此文件的编辑权限。'
  if (hasUnsavedChanges.value) {
    confirmMessage += '\n\n您当前有未保存的修改，移交前会自动保存。'
  } else {
    confirmMessage += '\n\n是否移交编辑权限？'
  }

  const confirmed = await requestConfirmation({
    title: '编辑权限移交请求',
    message: confirmMessage,
    confirmText: '保存并移交'
  })
  if (!confirmed) {
    await collab.sendHandoffRejected(selectedFile.value.relative_path)
    return
  }

  if (hasUnsavedChanges.value) {
    showToast('正在保存并移交...')
    await saveCurrentFileSilent()
  }

  const fileKey = selectedFile.value.relative_path
  await collab.sendHandoffAccepted(fileKey)
  await releaseCollabSession()
  readOnlyMode.value = true
  subscribeCollabToFile(fileKey, false)
  showToast('编辑权限已移交，当前为只读模式')
}

// A 端轮询：持有锁时每 2 秒检查是否有移交请求
function startHandoffPolling(fileKey) {
  stopHandoffPolling()
  handoffPollTimer = setInterval(async () => {
    if (!fileLockHeldByMe.value) return
    const result = await collab.pollHandoffIncoming(fileKey)
    if (result && result.has_request) {
      handleIncomingHandoffRequest()
    }
  }, 2000)
}

function stopHandoffPolling() {
  if (handoffPollTimer) {
    clearInterval(handoffPollTimer)
    handoffPollTimer = null
  }
}

// 静默保存（不释放锁、不显示 toast）
async function saveCurrentFileSilent() {
  if (!selectedFile.value || saving.value) return

  if (isBoardFile()) {
    saving.value = true
    try {
      const res = await saveCopyBoardContent(selectedFile.value.relative_path, boardCards.value, fileLockToken.value)
      if (res.success) {
        boardCards.value = cloneCards(res.cards || boardCards.value)
        originalBoardCards.value = cloneCards(boardCards.value)
        hasUnsavedChanges.value = false
      }
    } catch (e) { /* ignore */ }
    finally { saving.value = false }
    return
  }

  const content = getCleanHtmlForSave()
  if (!content.trim()) return

  saving.value = true
  try {
    const res = await saveCopyContent(selectedFile.value.relative_path, content, fileLockToken.value)
    if (res.success) {
      htmlContent.value = content
      originalHtmlContent.value = content
      hasUnsavedChanges.value = false
    }
  } catch (e) { /* ignore */ }
  finally { saving.value = false }
}

// 视图挂载后立即拉取文件列表，并启动锁状态轮询（让侧边栏文件项"正在编辑"徽章尽快显示）
refreshFileList()
startLockStatusPoll()
</script>

<template>
  <div class="copy-management">
    <div class="copy-management__sidebar">
      <div class="copy-management__sidebar-header">
        <h3>文案文件</h3>
        <button class="copy-management__refresh-btn" @click="refreshFileList" :disabled="loading" title="刷新文件列表">
          ↻
        </button>
      </div>

      <div class="copy-management__quick-actions">
        <button
          class="copy-management__root-board-btn"
          :disabled="saving"
          title="新建不属于任何国家的原生卡片页"
          @click="createRootBoard"
        >
          <span class="copy-management__root-board-icon">+</span>
          <span>新建独立原生卡片</span>
        </button>
        <input
          ref="uploadInputRef"
          type="file"
          accept=".html,.htm"
          style="display:none"
          @change="handleFileUpload"
        />
        <button
          class="copy-management__upload-btn"
          :disabled="uploading"
          title="上传HTML文件，自动按文件名分配到国家文件夹"
          @click="triggerUpload"
        >
          <span v-if="uploading" class="copy-management__btn-spinner"></span>
          <span v-else class="copy-management__upload-icon">↑</span>
          <span>{{ uploading ? '上传中...' : '上传HTML' }}</span>
        </button>
      </div>

      <div v-if="loading && countries.length === 0" class="copy-management__loading">加载中...</div>
      <div v-if="error && !loading && countries.length === 0" class="copy-management__error">{{ error }}</div>

      <div v-if="!loading && countries.length === 0" class="copy-management__empty">
        暂未发现文案文件
      </div>

      <div v-if="countries.length > 0" class="copy-management__country-list">
        <div v-for="country in countries" :key="country.name" class="copy-management__country-group">
          <div
            class="copy-management__country-name"
              :class="{ 'copy-management__country-name--active': selectedCountry === country.name }"
          >
            {{ country.name }}
            <span class="copy-management__file-count">({{ country.files.length }})</span>
            <input
              class="copy-management__country-note"
              v-model="country.note"
              placeholder="添加备注..."
              @input="saveCountryNoteDebounced(country)"
            />
            <button
              class="copy-management__new-board-btn"
              :disabled="saving"
              title="新建原生空白文案页"
              @click.stop="createBoardForCountry(getCountryKey(country), country.name)"
            >
              +
            </button>
          </div>
          <div class="copy-management__file-list">
            <div
              v-for="file in country.files"
              :key="file.relative_path"
              class="copy-management__file-item"
              :class="{ 'copy-management__file-item--active': selectedFile?.relative_path === file.relative_path }"
              @click="openFile(country.name, file)"
            >
              <span class="copy-management__file-icon">▣</span>
              <div class="copy-management__file-info">
                <div class="copy-management__file-name">{{ file.name }}</div>
                <div class="copy-management__file-time">{{ file.modified_at.slice(0, 10) }}</div>
                <div v-if="file.type === 'copy_board'" class="copy-management__file-type copy-management__file-type--board">原生卡片</div>
                <div v-else-if="file.type === 'html'" class="copy-management__file-type copy-management__file-type--html">HTML海报</div>
                <div
                  v-if="lockedFileKeys.has(file.relative_path)"
                  class="copy-management__file-lock-badge"
                  :class="{ 'copy-management__file-lock-badge--mine': isFileLockedByMine(file) }"
                  :title="isFileLockedByMine(file) ? '您正在编辑此文件' : '此文件正在被其他用户编辑'"
                >
                  {{ isFileLockedByMine(file) ? '您正在编辑' : '正在编辑' }}
                </div>
              </div>
              <div v-if="file.type === 'copy_board'" class="copy-management__file-actions">
                <button
                  class="copy-management__file-action-btn"
                  :disabled="saving"
                  title="重命名原生卡片页"
                  @click.stop="openRenameBoardDialog(file)"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 20h9"></path>
                    <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
                  </svg>
                </button>
                <button
                  class="copy-management__file-action-btn copy-management__file-action-btn--danger"
                  :disabled="saving"
                  title="删除原生卡片页"
                  @click.stop="deleteBoardFile(file)"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6l-1 14H6L5 6"></path>
                    <path d="M10 11v6"></path>
                    <path d="M14 11v6"></path>
                    <path d="M9 6V4h6v2"></path>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="copy-management__main">
      <div v-if="!selectedFile" class="copy-management__placeholder">
        <div class="copy-management__placeholder-icon">□</div>
        <div class="copy-management__placeholder-text">请从左侧选择文案文件查看</div>
      </div>

      <div v-else class="copy-management__content">
        <div class="copy-management__toolbar">
          <div class="copy-management__toolbar-info">
            <span class="copy-management__toolbar-country">{{ selectedCountry }}</span>
            <span class="copy-management__toolbar-separator">></span>
            <span class="copy-management__toolbar-file">{{ selectedFile.name }}</span>
            <span v-if="readOnlyMode" class="copy-management__readonly-badge" title="其他用户正在编辑，您处于只读模式">只读 · 正在被其他用户编辑</span>
            <span v-else-if="fileLockHeldByMe" class="copy-management__lock-badge" title="您已获得该文件的编辑权限">编辑中 · 您已上锁</span>
            <span v-if="hasUnsavedChanges" class="copy-management__dirty">未保存</span>
            <span v-if="presenceCount > 1" class="copy-management__presence-badge" :title="`当前共 ${presenceCount} 人在查看此文件`">👥 {{ presenceCount }} 人在编辑</span>
          </div>

          <div class="copy-management__toolbar-actions">
            <button
              v-if="!isBoardFile()"
              class="copy-management__toolbar-btn"
              :class="{ 'copy-management__toolbar-btn--active': editMode }"
              @click="toggleEditMode"
              :disabled="readOnlyMode"
              :title="readOnlyMode ? '只读模式不可切换编辑状态' : '开启或关闭点击文字编辑'"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 20h9"></path>
                <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"></path>
              </svg>
              <span>{{ editMode ? '编辑开启' : '编辑关闭' }}</span>
            </button>
            <button
              v-if="readOnlyMode && selectedFile"
              class="copy-management__toolbar-btn copy-management__toolbar-btn--primary"
              @click="retryAcquireEditLock"
              :disabled="contentLoading || saving"
              title="其他用户已保存并释放锁后，可以重新尝试获取编辑权限"
            >
              尝试获取编辑权限
            </button>
            <button class="copy-management__toolbar-btn" @click="reloadCurrentFile" :disabled="contentLoading || saving">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 4 23 10 17 10"></polyline>
                <polyline points="1 20 1 14 7 14"></polyline>
                <path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10"></path>
                <path d="M20.5 15a9 9 0 0 1-14.9 3.4L1 14"></path>
              </svg>
              重新载入
            </button>
            <button class="copy-management__toolbar-btn" @click="discardCurrentChanges" :disabled="!hasUnsavedChanges || saving || readOnlyMode">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="1 4 1 10 7 10"></polyline>
                <path d="M3.5 15a9 9 0 1 0 2.1-9.4L1 10"></path>
              </svg>
              撤销
            </button>
            <button
              class="copy-management__toolbar-btn copy-management__toolbar-btn--primary"
              @click="saveCurrentFile"
              :disabled="!hasUnsavedChanges || saving || readOnlyMode"
            >
              <span v-if="saving" class="copy-management__btn-spinner"></span>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                <polyline points="17 21 17 13 7 13 7 21"></polyline>
                <polyline points="7 3 7 8 15 8"></polyline>
              </svg>
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>

        <div v-if="contentLoading" class="copy-management__content-loading">
          正在加载文件内容...
        </div>

        <div
          v-if="!contentLoading && isBoardFile()"
          class="copy-board"
          @paste="handleBoardPaste"
        >
          <div class="copy-board__paste-zone" tabindex="0">
            <div class="copy-board__paste-title">{{ readOnlyMode ? '只读模式' : '粘贴文案即可新增卡片' }}</div>
            <button v-if="!readOnlyMode" class="copy-board__add-btn" @click="addBlankBoardCard">新增空白卡片</button>
            <div v-else class="copy-board__readonly-hint">当前为只读模式，无法编辑</div>
          </div>

          <div v-if="boardCards.length === 0" class="copy-board__empty">
            当前还没有文案卡片。点击这里后直接粘贴，一次粘贴会生成一张卡片。
          </div>

          <div v-else class="copy-board__grid">
            <div
              v-for="(card, index) in boardCards"
              :key="card.id"
              class="copy-board-card"
              :class="{
                'copy-board-card--made': card.made,
                'copy-board-card--reviewed': card.reviewed,
                'copy-board-card--published': card.published,
                'copy-board-card--readonly': readOnlyMode
              }"
            >
              <div class="copy-board-card__status-rail">
                <button
                  class="copy-board-card__status-btn copy-board-card__status-btn--made"
                  :class="{ 'copy-board-card__status-btn--active': card.made }"
                  :title="card.made ? '取消已做标记' : '标记为已做'"
                  :disabled="readOnlyMode"
                  @click="touchBoardCard(card, { made: !card.made })"
                >
                  {{ card.made ? '已做' : '未做' }}
                </button>
                <button
                  class="copy-board-card__status-btn copy-board-card__status-btn--reviewed"
                  :class="{ 'copy-board-card__status-btn--active': card.reviewed }"
                  :title="card.reviewed ? '取消已审核标记' : '标记为已审核'"
                  :disabled="readOnlyMode"
                  @click="touchBoardCard(card, { reviewed: !card.reviewed })"
                >
                  {{ card.reviewed ? '已审核' : '未审核' }}
                </button>
                <button
                  class="copy-board-card__status-btn copy-board-card__status-btn--published"
                  :class="{ 'copy-board-card__status-btn--active': card.published }"
                  :title="card.published ? '取消已发标记' : '标记为已发'"
                  :disabled="readOnlyMode"
                  @click="touchBoardCard(card, { published: !card.published })"
                >
                  {{ card.published ? '已发' : '未发' }}
                </button>
              </div>
              <div class="copy-board-card__header">
                <span class="copy-board-card__index">#{{ index + 1 }}</span>
                <div class="copy-board-card__actions">
                  <button @click="copyBoardCard(card)">复制</button>
                  <button :disabled="index === 0 || readOnlyMode" @click="moveBoardCard(index, -1)">上移</button>
                  <button :disabled="index === boardCards.length - 1 || readOnlyMode" @click="moveBoardCard(index, 1)">下移</button>
                  <button class="copy-board-card__danger" :disabled="readOnlyMode" @click="deleteBoardCard(index)">删除</button>
                </div>
              </div>
              <textarea
                v-model="card.content"
                class="copy-board-card__textarea"
                placeholder="直接输入或粘贴文案"
                :readonly="readOnlyMode"
                @input="touchBoardCard(card)"
              ></textarea>
            </div>
          </div>
        </div>

        <iframe
          v-if="!contentLoading && !isBoardFile() && htmlContent"
          :key="iframeVersion"
          ref="iframeRef"
          class="copy-management__render-area"
          :srcdoc="htmlContent"
          sandbox="allow-same-origin allow-scripts"
          @load="onIframeLoad"
        ></iframe>

        <div v-if="!contentLoading && !isBoardFile() && !htmlContent && !error" class="copy-management__empty-content">
          文件内容为空
        </div>
      </div>
    </div>

    <div v-if="editDialogVisible" class="copy-edit-dialog">
      <div class="copy-edit-dialog__panel">
        <div class="copy-edit-dialog__header">
          <div>
            <div class="copy-edit-dialog__eyebrow">Text Edit</div>
            <div class="copy-edit-dialog__title">修改文字</div>
          </div>
          <button class="copy-edit-dialog__close" @click="closeEditDialog" title="关闭">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="copy-edit-dialog__hint">只会修改文字内容，确认后该处会自动加红色背景。</div>
        <textarea v-model="editDraft" class="copy-edit-dialog__textarea"></textarea>
        <div class="copy-edit-dialog__actions">
          <button class="copy-edit-dialog__btn" @click="closeEditDialog">取消</button>
          <button class="copy-edit-dialog__btn copy-edit-dialog__btn--primary" @click="confirmTextEdit">确认</button>
        </div>
      </div>
    </div>

    <div v-if="renameDialogVisible" class="copy-rename-dialog" @click.self="closeRenameBoardDialog">
      <div class="copy-rename-dialog__panel">
        <div class="copy-rename-dialog__title">重命名原生卡片页</div>
        <input
          v-model="renameDraft"
          class="copy-rename-dialog__input"
          type="text"
          @keydown.enter.prevent="confirmRenameBoardFile"
          @keydown.esc.prevent="closeRenameBoardDialog"
        />
        <div class="copy-rename-dialog__actions">
          <button class="copy-rename-dialog__btn" @click="closeRenameBoardDialog">取消</button>
          <button class="copy-rename-dialog__btn copy-rename-dialog__btn--primary" :disabled="saving" @click="confirmRenameBoardFile">确认</button>
        </div>
      </div>
    </div>

    <div v-if="cardEditDialogVisible" class="copy-card-code-dialog" @click.self="closeCardCodeEditor">
      <div class="copy-card-code-dialog__panel">
        <div class="copy-card-code-dialog__header">
          <div>
            <div class="copy-card-code-dialog__eyebrow">Card Code Editor</div>
            <div class="copy-card-code-dialog__title">编辑卡片代码</div>
          </div>
          <button class="copy-card-code-dialog__close" @click="closeCardCodeEditor" title="关闭">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="copy-card-code-dialog__hint">粘贴新的HTML代码来替换当前卡片的全部内容，保存后会自动注入工具按钮。</div>
        <div class="copy-card-code-dialog__editor">
          <div
            ref="codeLineNumbersRef"
            class="copy-card-code-dialog__line-numbers"
          >
            <div v-for="i in codeLines" :key="i">{{ i }}</div>
          </div>
          <textarea
            ref="codeTextareaRef"
            v-model="cardEditDraft"
            class="copy-card-code-dialog__code-input"
            spellcheck="false"
            @scroll="syncLineNumbersScroll"
            @keydown="handleCodeEditorKeydown"
          ></textarea>
        </div>
        <div v-if="cardEditError" class="copy-card-code-dialog__error">{{ cardEditError }}</div>
        <div class="copy-card-code-dialog__actions">
          <button class="copy-card-code-dialog__btn" @click="closeCardCodeEditor">取消</button>
          <button class="copy-card-code-dialog__btn copy-card-code-dialog__btn--primary" @click="confirmCardCodeEdit">确认替换</button>
        </div>
      </div>
    </div>

    <div v-if="confirmDialogVisible" class="copy-confirm-dialog" @click.self="closeConfirmDialog(false)">
      <div class="copy-confirm-dialog__panel">
        <div class="copy-confirm-dialog__icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M12 8v4"></path>
            <path d="M12 16h.01"></path>
          </svg>
        </div>
        <div class="copy-confirm-dialog__body">
          <div class="copy-confirm-dialog__title">{{ confirmDialogTitle }}</div>
          <div class="copy-confirm-dialog__message">{{ confirmDialogMessage }}</div>
        </div>
        <div class="copy-confirm-dialog__actions">
          <button class="copy-confirm-dialog__btn" @click="closeConfirmDialog(false)">取消</button>
          <button class="copy-confirm-dialog__btn copy-confirm-dialog__btn--primary" @click="closeConfirmDialog(true)">
            {{ confirmDialogConfirmText }}
          </button>
        </div>
      </div>
    </div>

    <!-- 协作场景的公共 ConfirmDialog（按工作区规则使用公共组件） -->
    <ConfirmDialog
      :visible="publicConfirmVisible"
      :title="publicConfirmTitle"
      :message="publicConfirmMessage"
      :confirm-text="publicConfirmConfirmText"
      :cancel-text="publicConfirmCancelText"
      @confirm="resolvePublicConfirm(true)"
      @cancel="resolvePublicConfirm(false)"
    />

    <Transition name="toast">
      <div v-if="toastVisible" class="copy-toast">{{ toastMessage }}</div>
    </Transition>
  </div>
</template>

<style lang="scss" scoped>
@use '@/styles/variables' as *;

.copy-management {
  display: flex;
  height: calc(100vh - 72px);
  background: #ffffff;
  color: #1a1a2e;
}

.copy-management__sidebar {
  width: 320px;
  min-width: 320px;
  background: #f0f2f5;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.copy-management__sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 20px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #1a1a2e;
  }
}

.copy-management__refresh-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  background: rgba(0, 0, 0, 0.05);
  color: #666;
  cursor: pointer;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;

  &:hover:not(:disabled) {
    background: rgba(0, 0, 0, 0.1);
    color: #FFD700;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.copy-management__readonly-badge {
  margin-left: 8px;
  padding: 3px 10px;
  border-radius: 12px;
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #b91c1c;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(185, 28, 28, 0.2);
}

.copy-management__lock-badge {
  margin-left: 8px;
  padding: 3px 10px;
  border-radius: 12px;
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  color: #047857;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(4, 120, 87, 0.2);
}

.copy-management__presence-badge {
  margin-left: 8px;
  padding: 3px 10px;
  border-radius: 12px;
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(29, 78, 216, 0.2);
}

.copy-board-card--readonly {
  opacity: 0.85;
  cursor: default;
}

.copy-board-card--readonly .copy-board-card__textarea {
  background: #f3f4f6;
  cursor: not-allowed;
}

.copy-board__readonly-hint {
  margin-top: 8px;
  color: #b91c1c;
  font-size: 13px;
  font-weight: 600;
}

.copy-management__quick-actions {
  padding: 12px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.copy-management__root-board-btn {
  width: 100%;
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid rgba(74, 158, 255, 0.28);
  border-radius: 8px;
  background: #ffffff;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;

  &:hover:not(:disabled) {
    border-color: #4a9eff;
    background: rgba(74, 158, 255, 0.08);
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.copy-management__root-board-icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: rgba(74, 158, 255, 0.12);
  font-size: 16px;
  line-height: 1;
}

.copy-management__upload-btn {
  width: 100%;
  min-height: 36px;
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid rgba(16, 185, 129, 0.28);
  border-radius: 8px;
  background: #ffffff;
  color: #059669;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;

  &:hover:not(:disabled) {
    border-color: #10b981;
    background: rgba(16, 185, 129, 0.08);
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.copy-management__upload-icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: rgba(16, 185, 129, 0.12);
  font-size: 14px;
  line-height: 1;
}

.copy-management__loading,
.copy-management__error,
.copy-management__empty {
  padding: 20px;
  text-align: center;
  color: #666;
  font-size: 14px;
}

.copy-management__error {
  color: #ff6b6b;
}

.copy-management__country-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.copy-management__country-group {
  margin-bottom: 4px;
}

.copy-management__country-name {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
  cursor: default;
  display: flex;
  align-items: center;
  gap: 6px;
  border-left: 3px solid transparent;
  transition: all 0.15s;

  &--active {
    border-left-color: #FFD700;
    background: rgba(255, 215, 0, 0.08);
  }
}

.copy-management__new-board-btn {
  margin-left: auto;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.14);
  background: #ffffff;
  color: #1a1a2e;
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  transition: all 0.15s;

  &:hover:not(:disabled) {
    border-color: #4a9eff;
    color: #4a9eff;
    background: rgba(74, 158, 255, 0.08);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.copy-management__country-note {
  flex: 1;
  min-width: 0;
  height: 26px;
  margin-left: 4px;
  padding: 3px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.48);
  color: #4b5563;
  font-size: 12px;
  line-height: 18px;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;

  &::placeholder {
    color: #a0a7b2;
  }

  &:focus {
    border-color: #4a9eff;
    background: #ffffff;
    box-shadow: 0 0 0 2px rgba(74, 158, 255, 0.12);
  }
}

.copy-management__file-count {
  font-size: 12px;
  color: #999;
  font-weight: 400;
}

.copy-management__file-list {
  padding: 2px 0;
}

.copy-management__file-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 72px 8px 36px;
  cursor: pointer;
  transition: all 0.15s;
  border-left: 3px solid transparent;

  &:hover {
    background: rgba(0, 0, 0, 0.04);
  }

  &--active {
    background: rgba(74, 158, 255, 0.12);
    border-left-color: #4a9eff;
  }

  &:hover .copy-management__file-actions,
  &:focus-within .copy-management__file-actions {
    opacity: 1;
    transform: translateY(-50%) scale(1);
    pointer-events: auto;
  }
}

.copy-management__file-icon {
  width: 16px;
  flex-shrink: 0;
  color: #666;
  text-align: center;
}

.copy-management__file-info {
  flex: 1;
  min-width: 0;
}

// 侧边栏文件项的"正在编辑"徽章：橙色代表他人编辑，绿色代表本人编辑
.copy-management__file-lock-badge {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 8px;
  font-size: 11px;
  line-height: 16px;
  border-radius: 10px;
  background: #fff4e5;
  color: #d97706;
  border: 1px solid #fde0a8;
  font-weight: 500;
  white-space: nowrap;
}

.copy-management__file-lock-badge--mine {
  background: #e6f7ee;
  color: #16a34a;
  border-color: #b7e6c8;
}

.copy-management__file-actions {
  position: absolute;
  top: 50%;
  right: 10px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-50%) scale(0.92);
  transition: all 0.15s;
}

.copy-management__file-action-btn {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(220, 38, 38, 0.2);
  border-radius: 7px;
  background: #ffffff;
  color: #2563eb;
  cursor: pointer;
  transition: all 0.15s;

  svg {
    width: 14px;
    height: 14px;
  }

  &:hover:not(:disabled) {
    background: rgba(37, 99, 235, 0.08);
    border-color: rgba(37, 99, 235, 0.36);
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  &--danger {
    border-color: rgba(220, 38, 38, 0.2);
    color: #dc2626;

    &:hover:not(:disabled) {
      background: rgba(220, 38, 38, 0.08);
      border-color: rgba(220, 38, 38, 0.36);
    }
  }
}

.copy-management__file-name {
  font-size: 13px;
  color: #1a1a2e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.copy-management__file-time {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.copy-management__file-type {
  display: inline-flex;
  width: fit-content;
  margin-top: 4px;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  font-size: 10px;
  font-weight: 700;

  &--html {
    background: rgba(74, 158, 255, 0.12);
    color: #2563eb;
  }
}

.copy-management__main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #f8f9fa;
}

.copy-management__placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
}

.copy-management__placeholder-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.copy-management__placeholder-text {
  font-size: 16px;
}

.copy-management__content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.copy-management__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 54px;
  padding: 10px 20px;
  background: #ffffff;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.copy-management__toolbar-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 14px;
}

.copy-management__toolbar-country {
  color: #FFD700;
  font-weight: 600;
}

.copy-management__toolbar-separator {
  color: #999;
}

.copy-management__toolbar-file {
  color: #1a1a2e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: min(38vw, 520px);
}

.copy-management__dirty {
  flex-shrink: 0;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.14);
  color: #fbbf24;
  font-size: 12px;
}

.copy-management__toolbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding: 4px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.03);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.copy-management__toolbar-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: #666;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;

  svg {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
  }

  &:hover:not(:disabled) {
    background: rgba(0, 0, 0, 0.06);
    border-color: rgba(0, 0, 0, 0.08);
    color: #1a1a2e;
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  &--active {
    border-color: rgba($primary-color, 0.28);
    color: $primary-color;
    background: linear-gradient(135deg, rgba($primary-color, 0.16) 0%, rgba($primary-color, 0.08) 100%);
    box-shadow: 0 2px 8px rgba($primary-color, 0.12);
  }

  &--primary {
    border-color: transparent;
    background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
    color: #fff;

    &:hover:not(:disabled) {
      box-shadow: 0 4px 12px rgba($primary-color, 0.28);
    }
  }
}

.copy-management__btn-spinner {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  animation: copy-spin 0.7s linear infinite;
}

.copy-management__content-loading {
  padding: 40px;
  text-align: center;
  color: #666;
  font-size: 14px;
}

.copy-management__render-area {
  flex: 1;
  width: 100%;
  border: none;
  background: #fff;
}

.copy-management__empty-content {
  padding: 40px;
  text-align: center;
  color: #999;
  font-size: 14px;
}

.copy-board {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  background: #f6f7f9;
}

.copy-board__paste-zone {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 58px;
  padding: 12px 16px;
  border: 1px dashed rgba(74, 158, 255, 0.45);
  border-radius: 8px;
  background: #ffffff;
  outline: none;

  &:focus {
    border-color: #4a9eff;
    box-shadow: 0 0 0 3px rgba(74, 158, 255, 0.12);
  }
}

.copy-board__paste-title {
  color: #1a1a2e;
  font-size: 14px;
  font-weight: 700;
}

.copy-board__add-btn {
  height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(74, 158, 255, 0.32);
  border-radius: 8px;
  background: rgba(74, 158, 255, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.copy-board__empty {
  margin-top: 18px;
  padding: 36px;
  border-radius: 8px;
  background: #ffffff;
  color: #666;
  text-align: center;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.copy-board__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  column-gap: 46px;
  row-gap: 20px;
  margin-top: 18px;
  padding-right: 28px;
}

.copy-board-card {
  position: relative;
  min-height: 260px;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  overflow: visible;

  &--made {
    border-color: #059669;
    background: linear-gradient(90deg, rgba(16, 185, 129, 0.12) 0, rgba(16, 185, 129, 0.05) 68px, #ffffff 150px);
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2), 0 12px 28px rgba(16, 185, 129, 0.14);
  }

  &--reviewed {
    border-color: #7c3aed;
    background: linear-gradient(90deg, rgba(139, 92, 246, 0.12) 0, rgba(139, 92, 246, 0.04) 68px, #ffffff 150px);
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.22), 0 12px 28px rgba(139, 92, 246, 0.14);
  }

  &--published {
    border-color: #2563eb;
    background: linear-gradient(90deg, rgba(59, 130, 246, 0.12) 0, rgba(59, 130, 246, 0.05) 68px, #ffffff 150px);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.22), 0 12px 28px rgba(59, 130, 246, 0.14);
  }

  &--made.copy-board-card--reviewed {
    border-color: #7c3aed;
    background:
      linear-gradient(90deg, rgba(16, 185, 129, 0.14) 0 50%, rgba(139, 92, 246, 0.14) 50% 100%),
      #ffffff;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.18), 0 0 0 4px rgba(139, 92, 246, 0.16), 0 12px 30px rgba(15, 23, 42, 0.12);
  }

  &--made.copy-board-card--published {
    border-color: #2563eb;
    background:
      linear-gradient(90deg, rgba(16, 185, 129, 0.14) 0 50%, rgba(59, 130, 246, 0.14) 50% 100%),
      #ffffff;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.18), 0 0 0 4px rgba(59, 130, 246, 0.16), 0 12px 30px rgba(15, 23, 42, 0.12);
  }

  &--reviewed.copy-board-card--published {
    border-color: #2563eb;
    background:
      linear-gradient(90deg, rgba(139, 92, 246, 0.14) 0 50%, rgba(59, 130, 246, 0.14) 50% 100%),
      #ffffff;
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.18), 0 0 0 4px rgba(59, 130, 246, 0.16), 0 12px 30px rgba(15, 23, 42, 0.12);
  }

  &--made.copy-board-card--reviewed.copy-board-card--published {
    border-color: #2563eb;
    background:
      linear-gradient(90deg, rgba(16, 185, 129, 0.14) 0 33.33%, rgba(139, 92, 246, 0.14) 33.33% 66.66%, rgba(59, 130, 246, 0.14) 66.66% 100%),
      #ffffff;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.18), 0 0 0 4px rgba(139, 92, 246, 0.16), 0 0 0 6px rgba(59, 130, 246, 0.14), 0 12px 30px rgba(15, 23, 42, 0.12);
  }
}

.copy-board-card__status-rail {
  position: absolute;
  top: 46px;
  right: -27px;
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.copy-board-card__status-btn {
  width: 26px;
  min-height: 70px;
  padding: 8px 4px;
  border: 1px solid rgba(100, 116, 139, 0.26);
  border-left: 0;
  border-radius: 0 8px 8px 0;
  background: rgba(248, 250, 252, 0.96);
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.15;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  letter-spacing: 2px;
  cursor: pointer;
  pointer-events: auto;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
  transition: all 0.15s;

  &:hover {
    transform: translateX(2px);
  }

  &--made.copy-board-card__status-btn--active {
    border-color: #059669;
    background: linear-gradient(180deg, #10b981 0%, #059669 100%);
    color: #ffffff;
    box-shadow: 0 6px 16px rgba(16, 185, 129, 0.28);
  }

  &--reviewed.copy-board-card__status-btn--active {
    border-color: #7c3aed;
    background: linear-gradient(180deg, #8b5cf6 0%, #7c3aed 100%);
    color: #ffffff;
    box-shadow: 0 6px 16px rgba(139, 92, 246, 0.28);
  }

  &--published.copy-board-card__status-btn--active {
    border-color: #2563eb;
    background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
    color: #ffffff;
    box-shadow: 0 6px 16px rgba(59, 130, 246, 0.28);
  }
}

.copy-board-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.copy-board-card--made .copy-board-card__header {
  background: rgba(16, 185, 129, 0.12);
  border-bottom-color: rgba(5, 150, 105, 0.22);
}

.copy-board-card--reviewed .copy-board-card__header {
  background: rgba(139, 92, 246, 0.12);
  border-bottom-color: rgba(124, 58, 237, 0.22);
}

.copy-board-card--published .copy-board-card__header {
  background: rgba(59, 130, 246, 0.12);
  border-bottom-color: rgba(37, 99, 235, 0.22);
}

.copy-board-card--made.copy-board-card--reviewed .copy-board-card__header {
  background: linear-gradient(90deg, rgba(16, 185, 129, 0.16) 0 50%, rgba(139, 92, 246, 0.16) 50% 100%);
}

.copy-board-card--made.copy-board-card--published .copy-board-card__header {
  background: linear-gradient(90deg, rgba(16, 185, 129, 0.16) 0 50%, rgba(59, 130, 246, 0.16) 50% 100%);
}

.copy-board-card--reviewed.copy-board-card--published .copy-board-card__header {
  background: linear-gradient(90deg, rgba(139, 92, 246, 0.16) 0 50%, rgba(59, 130, 246, 0.16) 50% 100%);
}

.copy-board-card--made.copy-board-card--reviewed.copy-board-card--published .copy-board-card__header {
  background: linear-gradient(90deg, rgba(16, 185, 129, 0.16) 0 33.33%, rgba(139, 92, 246, 0.16) 33.33% 66.66%, rgba(59, 130, 246, 0.16) 66.66% 100%);
}

.copy-board-card__index {
  flex-shrink: 0;
  color: #4a9eff;
  font-size: 12px;
  font-weight: 800;
}

.copy-board-card__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;

  button {
    height: 24px;
    padding: 0 8px;
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 6px;
    background: #f8fafc;
    color: #334155;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;

    &:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
  }
}

.copy-board-card__danger {
  color: #dc2626 !important;
  background: rgba(220, 38, 38, 0.06) !important;
}

.copy-board-card__textarea {
  flex: 1;
  width: 100%;
  min-height: 420px;
  border: 0;
  resize: vertical;
  padding: 14px;
  color: #111827;
  font-size: 14px;
  line-height: 1.7;
  outline: none;
  white-space: pre-wrap;
  background: #ffffff;
}

.copy-edit-dialog {
  position: fixed;
  inset: 0;
  z-index: 9000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(6px);
}

.copy-rename-dialog {
  position: fixed;
  inset: 0;
  z-index: 9050;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(6px);
}

.copy-rename-dialog__panel {
  width: min(420px, calc(100vw - 40px));
  padding: 22px;
  border-radius: $radius-xl;
  border: 1px solid rgba($color-border, 0.75);
  background: $color-bg-card;
  box-shadow: $shadow-xl;
}

.copy-rename-dialog__title {
  margin-bottom: 14px;
  color: $color-text-primary;
  font-size: $font-size-base;
  font-weight: 700;
}

.copy-rename-dialog__input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  background: $color-bg-secondary;
  color: $color-text-primary;
  font-size: 14px;
  outline: none;

  &:focus {
    border-color: $color-border-focus;
    box-shadow: 0 0 0 3px rgba($primary-color, 0.08);
  }
}

.copy-rename-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.copy-rename-dialog__btn {
  height: 36px;
  padding: 0 16px;
  border-radius: $radius-md;
  border: 1px solid $color-border;
  background: $color-bg-secondary;
  color: $color-text-secondary;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover:not(:disabled) {
    background: $color-bg-tertiary;
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  &--primary {
    border-color: transparent;
    color: $color-text-inverse;
    background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
  }
}

.copy-card-code-dialog {
  position: fixed;
  inset: 0;
  z-index: 9080;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(6px);
}

.copy-card-code-dialog__panel {
  width: min(720px, calc(100vw - 40px));
  max-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  background: $color-bg-card;
  border: 1px solid rgba($color-border, 0.75);
  border-radius: $radius-xl;
  box-shadow: $shadow-xl;
  overflow: hidden;
}

.copy-card-code-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 22px 14px;
  border-bottom: 1px solid $color-border-light;
  flex-shrink: 0;
}

.copy-card-code-dialog__eyebrow {
  font-size: 10px;
  font-weight: 700;
  color: $primary-color;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.copy-card-code-dialog__title {
  color: $color-text-primary;
  font-size: $font-size-base;
  font-weight: 700;
}

.copy-card-code-dialog__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: $radius-md;
  background: $color-bg-secondary;
  color: $color-text-tertiary;
  cursor: pointer;
  transition: all $transition-fast;

  svg {
    width: 16px;
    height: 16px;
  }

  &:hover {
    background: $color-bg-tertiary;
    color: $color-text-primary;
  }
}

.copy-card-code-dialog__hint {
  margin: 16px 22px 0;
  padding: 10px 12px;
  border-radius: $radius-md;
  background: linear-gradient(135deg, rgba($primary-color, 0.08) 0%, rgba($primary-color, 0.04) 100%);
  color: $color-text-secondary;
  font-size: 12px;
  line-height: 1.5;
  flex-shrink: 0;
}

.copy-card-code-dialog__editor {
  display: flex;
  margin: 14px 22px 0;
  flex: 1;
  min-height: 280px;
  border-radius: $radius-md;
  border: 1px solid $color-border;
  background: #1e1e2e;
  overflow: hidden;
  transition: border-color $transition-fast, box-shadow $transition-fast;

  &:focus-within {
    border-color: $color-border-focus;
    box-shadow: 0 0 0 3px rgba($primary-color, 0.08);
  }
}

.copy-card-code-dialog__line-numbers {
  flex-shrink: 0;
  width: 48px;
  min-height: 280px;
  padding: 14px 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
  background: #181825;
  border-right: 1px solid rgba(205, 214, 244, 0.15);
  user-select: none;

  &::-webkit-scrollbar {
    display: none;
  }

  div {
    padding: 0 14px 0 6px;
    line-height: 1.5;
    font-size: 13px;
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
    color: #ffffff;
  }
}

.copy-card-code-dialog__code-input {
  flex: 1;
  min-height: 280px;
  border: none;
  background: transparent;
  color: #cdd6f4;
  padding: 14px;
  line-height: 1.5;
  font-size: 13px;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  outline: none;
  resize: none;
  overflow-y: auto;
  overflow-x: auto;
  white-space: pre;
  tab-size: 2;

  &::selection {
    background: rgba(74, 158, 255, 0.35);
  }
}

.copy-card-code-dialog__error {
  margin: 10px 22px 0;
  padding: 8px 12px;
  border-radius: $radius-md;
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
  font-size: 12px;
  line-height: 1.4;
  flex-shrink: 0;
}

.copy-card-code-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 0;
  padding: 16px 22px 20px;
  flex-shrink: 0;
}

.copy-card-code-dialog__btn {
  min-width: 84px;
  height: 36px;
  padding: 0 18px;
  border-radius: $radius-md;
  border: 1px solid $color-border;
  background: $color-bg-secondary;
  color: $color-text-secondary;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: $color-bg-tertiary;
    transform: translateY(-1px);
  }

  &--primary {
    border-color: transparent;
    background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
    color: $color-text-inverse;

    &:hover {
      box-shadow: 0 4px 12px rgba($primary-color, 0.3);
    }
  }
}

.copy-edit-dialog__panel {
  width: min(620px, calc(100vw - 40px));
  background: $color-bg-card;
  border: 1px solid rgba($color-border, 0.75);
  border-radius: $radius-xl;
  box-shadow: $shadow-xl;
  overflow: hidden;
}

.copy-edit-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 22px 14px;
  border-bottom: 1px solid $color-border-light;
}

.copy-edit-dialog__eyebrow {
  font-size: 10px;
  font-weight: 700;
  color: $primary-color;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.copy-edit-dialog__title {
  color: $color-text-primary;
  font-size: $font-size-base;
  font-weight: 700;
}

.copy-edit-dialog__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: $radius-md;
  background: $color-bg-secondary;
  color: $color-text-tertiary;
  cursor: pointer;
  transition: all $transition-fast;

  svg {
    width: 16px;
    height: 16px;
  }

  &:hover {
    background: $color-bg-tertiary;
    color: $color-text-primary;
  }
}

.copy-edit-dialog__hint {
  margin: 16px 22px 0;
  padding: 10px 12px;
  border-radius: $radius-md;
  background: linear-gradient(135deg, rgba($primary-color, 0.08) 0%, rgba($primary-color, 0.04) 100%);
  color: $color-text-secondary;
  font-size: 12px;
  line-height: 1.5;
}

.copy-edit-dialog__textarea {
  width: calc(100% - 44px);
  min-height: 150px;
  margin: 14px 22px 0;
  resize: vertical;
  border-radius: $radius-md;
  border: 1px solid $color-border;
  background: linear-gradient(180deg, $color-bg-secondary 0%, $color-bg-tertiary 100%);
  color: $color-text-primary;
  padding: 12px;
  line-height: 1.6;
  font-size: 14px;
  outline: none;
  transition: all $transition-fast;

  &:focus {
    border-color: $color-border-focus;
    box-shadow: 0 0 0 3px rgba($primary-color, 0.08);
  }
}

.copy-edit-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 0;
  padding: 16px 22px 20px;
}

.copy-edit-dialog__btn {
  min-width: 84px;
  height: 36px;
  padding: 0 18px;
  border-radius: $radius-md;
  border: 1px solid $color-border;
  background: $color-bg-secondary;
  color: $color-text-secondary;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: $color-bg-tertiary;
    transform: translateY(-1px);
  }

  &--primary {
    border-color: transparent;
    background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);
    color: $color-text-inverse;

    &:hover {
      box-shadow: 0 4px 12px rgba($primary-color, 0.3);
    }
  }
}

.copy-confirm-dialog {
  position: fixed;
  inset: 0;
  z-index: 9100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(6px);
}

.copy-confirm-dialog__panel {
  width: min(420px, calc(100vw - 40px));
  background: $color-bg-card;
  border: 1px solid rgba($color-border, 0.75);
  border-radius: $radius-xl;
  box-shadow: $shadow-xl;
  padding: 22px;
}

.copy-confirm-dialog__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  margin-bottom: 14px;
  border-radius: $radius-lg;
  color: $warning-color;
  background: rgba($warning-color, 0.12);

  svg {
    width: 21px;
    height: 21px;
  }
}

.copy-confirm-dialog__title {
  font-size: $font-size-base;
  font-weight: 700;
  color: $color-text-primary;
  margin-bottom: 8px;
}

.copy-confirm-dialog__message {
  color: $color-text-secondary;
  font-size: 13px;
  line-height: 1.6;
}

.copy-confirm-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

.copy-confirm-dialog__btn {
  height: 36px;
  padding: 0 16px;
  border-radius: $radius-md;
  border: 1px solid $color-border;
  background: $color-bg-secondary;
  color: $color-text-secondary;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: $color-bg-tertiary;
    transform: translateY(-1px);
  }

  &--primary {
    border-color: transparent;
    color: $color-text-inverse;
    background: linear-gradient(135deg, $primary-gradient-start 0%, $primary-gradient-end 100%);

    &:hover {
      box-shadow: 0 4px 12px rgba($primary-color, 0.3);
    }
  }
}

.copy-toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.85);
  color: #fff;
  padding: 14px 28px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 500;
  z-index: 9999;
  pointer-events: none;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
}

.toast-enter-active {
  transition: all 0.2s ease-out;
}

.toast-leave-active {
  transition: all 0.3s ease-in;
}

.toast-enter-from {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.9);
}

.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.9);
}

@keyframes copy-spin {
  to { transform: rotate(360deg); }
}
</style>
