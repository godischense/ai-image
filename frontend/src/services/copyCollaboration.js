// 文案管理 - 协作客户端服务
// 功能描述：
//     封装 WebSocket 客户端 + 锁/块锁/广播/订阅能力；
//     单例模式（整页只保持一条 WS 连接），自动重连 3 秒后重连；
//     不关联任何用户身份，所有「谁」的信息都通过本地 token 比对判断。
//     失败处理：所有 fetch/ws 异常都会被 catch 并通过 Promise reject 上抛，
//     调用方负责根据业务决定是否重试。

const HEARTBEAT_INTERVAL_MS = 10 * 1000
const RECONNECT_DELAY_MS = 3 * 1000

function authHeaders(extra = {}) {
  return extra
}

function withToken(url) {
  return url
}

// 生成一个本地 owner token（UUID 风格）
function generateToken() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
}

class CopyCollaboration {
  constructor() {
    this.ws = null
    this.url = ''
    this.connected = false
    this.reconnectTimer = null
    this.shouldReconnect = true
    // 当前已订阅的 file_key -> callbacks
    this.subscribers = new Map()
    // 等待 block_lock 响应的 Promise 队列
    this.blockLockCallbacks = new Map()
    // 每个 file_key 的心跳定时器
    this.heartbeatTimers = new Map()
    // 服务端下发的 presence_count
    this.presenceCounts = new Map()
  }

  // 拼接 WebSocket URL：自动把 http 升级为 ws，https 升级为 wss
  _buildWsUrl() {
    const apiBase = (import.meta?.env?.VITE_API_BASE_URL) || ''
    if (apiBase) {
      return withToken(apiBase.replace(/^http/, 'ws') + '/api/copy/ws')
    }
    // 默认走当前 origin
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return withToken(`${protocol}://${window.location.host}/api/copy/ws`)
  }

  // 启动连接（幂等）
  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return
    }
    this.shouldReconnect = true
    this.url = this._buildWsUrl()
    try {
      this.ws = new WebSocket(this.url)
    } catch (e) {
      // 某些环境 new WebSocket 直接抛错，安排重连
      this._scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this.connected = true
      // 重连成功后重新订阅所有 file_key
      for (const fileKey of this.subscribers.keys()) {
        this._send({ type: 'subscribe', file_key: fileKey })
      }
    }

    this.ws.onmessage = (event) => {
      let data = null
      try {
        data = typeof event.data === 'string' ? JSON.parse(event.data) : null
      } catch (e) {
        return
      }
      if (!data || typeof data !== 'object') return
      this._dispatch(data)
    }

    this.ws.onerror = () => {
      // 浏览器中 onerror 之后通常会触发 onclose
    }

    this.ws.onclose = () => {
      this.connected = false
      this.ws = null
      // 通知所有 block_lock 等待者失败
      for (const [key, cb] of this.blockLockCallbacks.entries()) {
        cb.reject(new Error('WebSocket 已断开'))
        this.blockLockCallbacks.delete(key)
      }
      if (this.shouldReconnect) {
        this._scheduleReconnect()
      }
    }
  }

  // 主动断开连接（不会自动重连）
  disconnect() {
    this.shouldReconnect = false
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    // 停掉所有心跳
    for (const timer of this.heartbeatTimers.values()) {
      clearInterval(timer)
    }
    this.heartbeatTimers.clear()
    if (this.ws) {
      try {
        this.ws.close()
      } catch (e) {
        // ignore
      }
      this.ws = null
    }
    this.connected = false
  }

  // 安排重连
  _scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (this.shouldReconnect) {
        this.connect()
      }
    }, RECONNECT_DELAY_MS)
  }

  // 发送消息（自动 JSON 序列化）
  _send(message) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false
    }
    try {
      this.ws.send(JSON.stringify(message))
      return true
    } catch (e) {
      return false
    }
  }

  // 分发服务端消息
  _dispatch(data) {
    const type = data.type
    const fileKey = data.file_key
    if (!fileKey) return
    const subs = this.subscribers.get(fileKey)
    if (!subs) return

    if (type === 'file_locked') {
      if (subs.onFileLocked) subs.onFileLocked(data)
    } else if (type === 'file_unlocked') {
      if (subs.onFileUnlocked) subs.onFileUnlocked(data)
    } else if (type === 'block_locked') {
      if (subs.onBlockLocked) subs.onBlockLocked(data)
    } else if (type === 'block_unlocked') {
      if (subs.onBlockUnlocked) subs.onBlockUnlocked(data)
    } else if (type === 'content_update') {
      if (subs.onContentUpdate) subs.onContentUpdate(data)
    } else if (type === 'presence_count') {
      this.presenceCounts.set(fileKey, data.count)
      if (subs.onPresenceCount) subs.onPresenceCount(data)
    } else if (type === 'handoff_request') {
      if (subs.onHandoffRequest) subs.onHandoffRequest(data)
    } else if (type === 'handoff_accepted') {
      if (subs.onHandoffAccepted) subs.onHandoffAccepted(data)
    } else if (type === 'handoff_rejected') {
      if (subs.onHandoffRejected) subs.onHandoffRejected(data)
    } else if (type === 'block_lock_result') {
      const key = `${fileKey}::${data.block_id}`
      const cb = this.blockLockCallbacks.get(key)
      if (cb) {
        this.blockLockCallbacks.delete(key)
        if (data.ok && !data.conflict) {
          cb.resolve({ ok: true, conflict: false })
        } else {
          cb.resolve({ ok: false, conflict: true })
        }
      }
    } else if (type === 'heartbeat_ack' || type === 'pong') {
      // 静默忽略
    }
  }

  // 订阅一个 file_key 的所有事件；返回取消订阅函数
  subscribeFile(fileKey, callbacks) {
    this.subscribers.set(fileKey, callbacks || {})
    if (this.connected) {
      this._send({ type: 'subscribe', file_key: fileKey })
    } else {
      this.connect()
    }
    return () => {
      this.subscribers.delete(fileKey)
      this.presenceCounts.delete(fileKey)
      this._stopHeartbeatForFile(fileKey)
    }
  }

  // 通过 HTTP 申请文件级锁
  // 实现逻辑：POST /api/copy/lock/acquire，把服务端返回的 token 返回给调用方
  async acquireFileLock(fileKey, ownerToken) {
    const token = ownerToken || generateToken()
    try {
      const resp = await fetch('/api/copy/lock/acquire', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ file_key: fileKey, owner_token: token })
      })
      const data = await resp.json().catch(() => ({}))
      if (resp.status === 409) {
        return { ok: false, conflict: true, locked: true, token }
      }
      if (!resp.ok || !data.success) {
        return { ok: false, conflict: false, locked: false, token, error: data.error || '请求失败' }
      }
      return {
        ok: data.ok,
        conflict: data.conflict,
        locked: data.locked,
        token: data.token || token
      }
    } catch (e) {
      return { ok: false, conflict: false, locked: false, token, error: e.message }
    }
  }

  // 通过 HTTP 释放文件级锁
  async releaseFileLock(fileKey, ownerToken) {
    try {
      const resp = await fetch('/api/copy/lock/release', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ file_key: fileKey, owner_token: ownerToken })
      })
      const data = await resp.json().catch(() => ({}))
      return data
    } catch (e) {
      return { success: false, error: e.message }
    }
  }

  // 强制获取文件锁（无视已有锁，直接接管）
  // 实现逻辑：POST /api/copy/lock/force-acquire，服务端会先释放旧锁再创建新锁
  async forceAcquireFileLock(fileKey, ownerToken) {
    const token = ownerToken || generateToken()
    try {
      const resp = await fetch('/api/copy/lock/force-acquire', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ file_key: fileKey, owner_token: token })
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok || !data.success) {
        return { ok: false, conflict: false, locked: false, token, error: data.error || '请求失败' }
      }
      return {
        ok: data.ok,
        conflict: data.conflict,
        locked: data.locked,
        token: data.token || token
      }
    } catch (e) {
      return { ok: false, conflict: false, locked: false, token, error: e.message }
    }
  }

  // 启动文件级锁的心跳；切换到下一个 file_key 时会自动停掉上一个
  startHeartbeat(fileKey, ownerToken) {
    this.stopHeartbeat()
    const timer = setInterval(() => {
      // 优先用 WS 发送心跳（更轻量）
      if (this._send({ type: 'heartbeat', file_key: fileKey, token: ownerToken })) {
        return
      }
      // WS 不可用时降级为 HTTP
      fetch('/api/copy/lock/heartbeat', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ file_key: fileKey, owner_token: ownerToken })
      }).catch(() => { })
    }, HEARTBEAT_INTERVAL_MS)
    this.heartbeatTimers.set(fileKey, timer)
  }

  // 停掉所有文件的心跳
  stopHeartbeat() {
    for (const timer of this.heartbeatTimers.values()) {
      clearInterval(timer)
    }
    this.heartbeatTimers.clear()
  }

  _stopHeartbeatForFile(fileKey) {
    const timer = this.heartbeatTimers.get(fileKey)
    if (timer) {
      clearInterval(timer)
      this.heartbeatTimers.delete(fileKey)
    }
  }

  // 通过 WebSocket 广播内容变更（保留，供将来文件级内容同步使用）
  broadcastContentUpdate(fileKey, blockId, html, ownerToken) {
    this._send({
      type: 'content_update',
      file_key: fileKey,
      block_id: blockId,
      html,
      token: ownerToken
    })
  }

  // 编辑权限移交协议：纯 HTTP 轮询，不依赖 WS
  // 请求方：POST 写入请求 → 轮询 GET 等待结果
  // 持有方：轮询 GET 发现请求 → 弹窗确认 → POST 接受/拒绝
  async sendHandoffRequest(fileKey, ownerToken) {
    try {
      await fetch('/api/copy/handoff/request', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ file_key: fileKey, token: ownerToken || '' })
      })
    } catch (e) { /* ignore */ }
  }
  async pollHandoffResponse(fileKey) {
    try {
      const resp = await fetch(withToken(`/api/copy/handoff/poll?file_key=${encodeURIComponent(fileKey)}`), { headers: authHeaders() })
      const data = await resp.json().catch(() => ({}))
      return data.status || 'none'
    } catch (e) {
      return 'none'
    }
  }
  async pollHandoffIncoming(fileKey) {
    try {
      const resp = await fetch(withToken(`/api/copy/handoff/incoming?file_key=${encodeURIComponent(fileKey)}`), { headers: authHeaders() })
      const data = await resp.json().catch(() => ({}))
      return data
    } catch (e) {
      return { has_request: false }
    }
  }
  async sendHandoffAccepted(fileKey) {
    try {
      await fetch('/api/copy/handoff/accepted', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ file_key: fileKey })
      })
    } catch (e) { /* ignore */ }
  }
  async sendHandoffRejected(fileKey) {
    try {
      await fetch('/api/copy/handoff/rejected', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ file_key: fileKey })
      })
    } catch (e) { /* ignore */ }
  }

  // 取当前某个 file_key 的 presence 数量（最近一次服务端推送）
  getPresenceCount(fileKey) {
    return this.presenceCounts.get(fileKey) || 0
  }
}

// 导出单例
const collabInstance = new CopyCollaboration()
export default collabInstance
export { generateToken }
