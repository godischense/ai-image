# 文案管理 - 协作锁与存在服务
# 功能描述：
#     维护「文件级编辑锁」「块级编辑锁」两份内存表，配套心跳保活机制；
#     向所有订阅同文件的 WebSocket 客户端广播文件锁、块锁、内容变更事件。
#     不关联任何用户身份，锁的 owner 仅是客户端传入的随机 token 字符串。

import json
import threading
import time
import uuid
from typing import Any, Dict, Optional, Set


# 锁的过期时间（秒）：客户端需每 10 秒发一次心跳，超过此时间未心跳的锁视为失效
LOCK_TTL_SECONDS = 30

# 块级锁的过期时间（秒）：单个文字编辑操作时长远超此值，且对话框关闭后会主动释放；
# 设置此 TTL 兜底防止因网络断连 / 浏览器崩溃 / 消息丢失导致的块锁永久残留
BLOCK_LOCK_TTL_SECONDS = 60

# 清理线程的扫描周期（秒）
CLEANUP_INTERVAL_SECONDS = 5

# 文件级锁表：file_key -> {token, owner, acquired_at, last_heartbeat}
FILE_LOCKS: Dict[str, Dict[str, Any]] = {}

# 块级锁表：file_key -> {block_id -> {token, owner, acquired_at}}
BLOCK_LOCKS: Dict[str, Dict[str, Dict[str, Any]]] = {}

# 订阅者表：file_key -> Set[ws]
SUBSCRIBERS: Dict[str, Set[Any]] = {}

# 全局锁：保护上述三张表的并发读写
_STATE_LOCK = threading.RLock()

# 后台清理线程的运行标志
_CLEANUP_THREAD_STARTED = False
_CLEANUP_THREAD_LOCK = threading.Lock()


def _now_ts() -> float:
    # 获取当前时间戳（秒）
    return time.time()


def _send(ws, message: Dict[str, Any]) -> bool:
    # 向单个 WebSocket 客户端发送 JSON 消息
    # 实现逻辑：调用 ws.send 发送 JSON 字符串；flask-sock 不自动序列化 dict，必须手动 json.dumps
    try:
        ws.send(json.dumps(message))
        return True
    except Exception:
        return False


def broadcast(file_key: str, message: Dict[str, Any]) -> None:
    # 向订阅了 file_key 的所有 WebSocket 客户端广播消息
    # 实现逻辑：快照一份订阅者集合（避免遍历时其他线程修改），依次发送；发送失败的 ws 直接丢弃
    with _STATE_LOCK:
        subscribers = list(SUBSCRIBERS.get(file_key, set()))
    if not subscribers:
        return
    dead: list = []
    for ws in subscribers:
        if not _send(ws, message):
            dead.append(ws)
    if dead:
        with _STATE_LOCK:
            for ws in dead:
                SUBSCRIBERS.get(file_key, set()).discard(ws)


def subscribe(file_key: str, ws) -> None:
    # 将 WebSocket 客户端添加到 file_key 的订阅者集合
    with _STATE_LOCK:
        SUBSCRIBERS.setdefault(file_key, set()).add(ws)


def unsubscribe(file_key: str, ws) -> None:
    # 将 WebSocket 客户端从 file_key 的订阅者集合中移除
    with _STATE_LOCK:
        if file_key in SUBSCRIBERS:
            SUBSCRIBERS[file_key].discard(ws)
            if not SUBSCRIBERS[file_key]:
                SUBSCRIBERS.pop(file_key, None)


def unsubscribe_ws_from_all(ws) -> None:
    # 从所有 file_key 的订阅者集合中移除该 ws（连接断开时调用）
    # 实现逻辑：遍历所有 file_key，删除包含 ws 的项
    with _STATE_LOCK:
        empty_keys = []
        for file_key, members in SUBSCRIBERS.items():
            members.discard(ws)
            if not members:
                empty_keys.append(file_key)
        for k in empty_keys:
            SUBSCRIBERS.pop(k, None)


def _generate_token() -> str:
    # 生成锁的 token
    return uuid.uuid4().hex


def try_acquire_file_lock(file_key: str, owner_token: Optional[str] = None) -> Dict[str, Any]:
    # 尝试获取文件级编辑锁
    # 实现逻辑：
    #   1) 若 file_key 无锁 → 加锁并返回 ok
    #   2) 若已被本人持有（owner_token 匹配）→ 续期 last_heartbeat 并返回 ok
    #   3) 若被他人持有 → 返回 conflict=True（不透露他人身份）
    #   4) owner_token 为空时由服务端生成
    with _STATE_LOCK:
        now = _now_ts()
        existing = FILE_LOCKS.get(file_key)
        if not existing:
            token = owner_token or _generate_token()
            FILE_LOCKS[file_key] = {
                'token': token,
                'owner': token,
                'acquired_at': now,
                'last_heartbeat': now
            }
            return {'ok': True, 'token': token, 'locked': True, 'conflict': False}

        if owner_token and existing.get('token') == owner_token:
            existing['last_heartbeat'] = now
            return {'ok': True, 'token': owner_token, 'locked': True, 'conflict': False}

        # 已被他人持有，且心跳已过期 → 强制回收
        if now - existing.get('last_heartbeat', 0) > LOCK_TTL_SECONDS:
            FILE_LOCKS.pop(file_key, None)
            token = owner_token or _generate_token()
            FILE_LOCKS[file_key] = {
                'token': token,
                'owner': token,
                'acquired_at': now,
                'last_heartbeat': now
            }
            return {'ok': True, 'token': token, 'locked': True, 'conflict': False}

        return {'ok': False, 'token': existing.get('token'), 'locked': True, 'conflict': True}


def release_file_lock(file_key: str, owner_token: str) -> bool:
    # 释放文件级锁
    # 实现逻辑：仅当 owner_token 匹配时才释放；释放后连带清理该文件下所有块级锁
    with _STATE_LOCK:
        existing = FILE_LOCKS.get(file_key)
        if not existing:
            return False
        if existing.get('token') != owner_token:
            return False
        FILE_LOCKS.pop(file_key, None)
    broadcast(file_key, {'type': 'file_unlocked', 'file_key': file_key})
    # 文件锁释放后清理残留的块级锁（防止旧 session 的块锁在新 session 中造成 token 不匹配的冲突）
    force_release_block_locks_for_file(file_key)
    return True


def force_release_file_lock(file_key: str) -> None:
    # 强制释放文件级锁（用于后台清理过期锁时）
    # 实现逻辑：直接删除锁记录，并向订阅者广播 file_unlocked
    with _STATE_LOCK:
        if file_key in FILE_LOCKS:
            FILE_LOCKS.pop(file_key, None)
    broadcast(file_key, {'type': 'file_unlocked', 'file_key': file_key})


def heartbeat(file_key: str, owner_token: str) -> Dict[str, Any]:
    # 刷新文件级锁的心跳时间
    # 实现逻辑：仅当 owner_token 匹配时更新；返回 {ok, valid}
    with _STATE_LOCK:
        existing = FILE_LOCKS.get(file_key)
        if not existing:
            return {'ok': False, 'valid': False}
        if existing.get('token') != owner_token:
            return {'ok': False, 'valid': False}
        existing['last_heartbeat'] = _now_ts()
        return {'ok': True, 'valid': True}


def is_file_locked_by_other(file_key: str, owner_token: str) -> bool:
    # 检查文件是否被他人锁定（用于保存前快速校验）
    with _STATE_LOCK:
        existing = FILE_LOCKS.get(file_key)
        if not existing:
            return False
        if existing.get('token') == owner_token:
            return False
        if _now_ts() - existing.get('last_heartbeat', 0) > LOCK_TTL_SECONDS:
            return False
        return True


def verify_save_token(file_key: str, owner_token: Optional[str]) -> bool:
    # 校验保存请求的 token 是否仍然有效
    # 实现逻辑：
    #   1) 若文件无锁（已被释放或从未锁过）→ 允许通过
    #   2) 若文件有锁且 owner_token 匹配 → 允许通过
    #   3) 其他情况 → 拒绝
    if not owner_token:
        return False
    with _STATE_LOCK:
        existing = FILE_LOCKS.get(file_key)
        if not existing:
            return True
        if existing.get('token') == owner_token:
            return True
        return False


def get_file_lock_status(file_key: str) -> Dict[str, Any]:
    # 查询文件锁状态（仅返回是否被锁，不返回 holder 信息）
    with _STATE_LOCK:
        existing = FILE_LOCKS.get(file_key)
        if not existing:
            return {'locked': False}
        if _now_ts() - existing.get('last_heartbeat', 0) > LOCK_TTL_SECONDS:
            FILE_LOCKS.pop(file_key, None)
            return {'locked': False}
        return {'locked': True}


# 列出当前所有被锁文件 key（用于侧边栏"正在编辑"徽章展示）
# 实现逻辑：
#   1) 加锁遍历 FILE_LOCKS
#   2) 跳过心跳过期的项（顺便从 FILE_LOCKS 中清理掉，避免长期运行后内存增长）
#   3) 返回剩余的 file_key 列表（拷贝，防止外部持有引用被并发修改）
def list_locked_file_keys() -> list:
    with _STATE_LOCK:
        now = _now_ts()
        expired_keys = []
        alive_keys = []
        for file_key, info in FILE_LOCKS.items():
            if now - info.get('last_heartbeat', 0) > LOCK_TTL_SECONDS:
                expired_keys.append(file_key)
            else:
                alive_keys.append(file_key)
        # 顺手清掉过期项，与 get_file_lock_status 的清理行为保持一致
        for k in expired_keys:
            FILE_LOCKS.pop(k, None)
    return list(alive_keys)


def try_acquire_block_lock(file_key: str, block_id: str, owner_token: Optional[str] = None) -> Dict[str, Any]:
    # 尝试获取块级编辑锁
    # 实现逻辑：
    #   1) 若该块无锁 → 加锁并返回 ok
    #   2) 若被本人持有 → 续期（更新 acquired_at）并返回 ok
    #   3) 若被他人持有 → 返回 conflict=True
    with _STATE_LOCK:
        now = _now_ts()
        block_dict = BLOCK_LOCKS.setdefault(file_key, {})
        existing = block_dict.get(block_id)
        if not existing:
            token = owner_token or _generate_token()
            block_dict[block_id] = {
                'token': token,
                'owner': token,
                'acquired_at': now
            }
            return {'ok': True, 'token': token, 'conflict': False}

        if owner_token and existing.get('token') == owner_token:
            existing['acquired_at'] = now
            return {'ok': True, 'token': owner_token, 'conflict': False}

        return {'ok': False, 'conflict': True}


def release_block_lock(file_key: str, block_id: str, owner_token: str) -> bool:
    # 释放块级锁
    with _STATE_LOCK:
        block_dict = BLOCK_LOCKS.get(file_key)
        if not block_dict:
            return False
        existing = block_dict.get(block_id)
        if not existing or existing.get('token') != owner_token:
            return False
        block_dict.pop(block_id, None)
        if not block_dict:
            BLOCK_LOCKS.pop(file_key, None)
    broadcast(file_key, {
        'type': 'block_unlocked',
        'file_key': file_key,
        'block_id': block_id
    })
    return True


def force_release_block_locks_for_file(file_key: str) -> None:
    # 强制释放某文件下的所有块级锁（文件锁释放时调用，避免残留）
    with _STATE_LOCK:
        block_dict = BLOCK_LOCKS.pop(file_key, None)
    if block_dict:
        for block_id in list(block_dict.keys()):
            broadcast(file_key, {
                'type': 'block_unlocked',
                'file_key': file_key,
                'block_id': block_id
            })


def get_presence_count(file_key: str) -> int:
    # 获取某文件的当前订阅者数量（不含身份信息）
    with _STATE_LOCK:
        return len(SUBSCRIBERS.get(file_key, set()))


def _cleanup_expired_locks() -> None:
    # 后台线程的清理逻辑：扫描过期锁并释放
    # 实现逻辑：
    #   1) 每 5 秒一次，遍历 FILE_LOCKS，找出超过 LOCK_TTL_SECONDS 未心跳的项，调用 force_release_file_lock
    #   2) 遍历 BLOCK_LOCKS，找出超过 BLOCK_LOCK_TTL_SECONDS 的块锁，调用 release_block_lock 释放
    with _STATE_LOCK:
        expired_files = []
        now = _now_ts()
        for file_key, info in FILE_LOCKS.items():
            if now - info.get('last_heartbeat', 0) > LOCK_TTL_SECONDS:
                expired_files.append(file_key)
    for file_key in expired_files:
        force_release_file_lock(file_key)
        force_release_block_locks_for_file(file_key)

    # 清理过期的块级锁（即使文件锁仍有效，块锁也可能因 WS 消息丢失而残留）
    with _STATE_LOCK:
        expired_blocks = []
        now = _now_ts()
        for file_key, block_dict in list(BLOCK_LOCKS.items()):
            for block_id, info in list(block_dict.items()):
                if now - info.get('acquired_at', 0) > BLOCK_LOCK_TTL_SECONDS:
                    expired_blocks.append((file_key, block_id, info.get('token', '')))
    for file_key, block_id, owner_token in expired_blocks:
        release_block_lock(file_key, block_id, owner_token)


def _cleanup_loop() -> None:
    # 后台清理线程主循环
    while True:
        try:
            _cleanup_expired_locks()
        except Exception:
            pass
        time.sleep(CLEANUP_INTERVAL_SECONDS)


def start_cleanup_thread() -> None:
    # 启动后台清理线程（幂等）
    global _CLEANUP_THREAD_STARTED
    with _CLEANUP_THREAD_LOCK:
        if _CLEANUP_THREAD_STARTED:
            return
        thread = threading.Thread(target=_cleanup_loop, daemon=True, name='copy-presence-cleanup')
        thread.start()
        _CLEANUP_THREAD_STARTED = True
