# 文案管理 - WebSocket 与锁 HTTP 路由
# 功能描述：
#     注册 flask-sock 提供的 WebSocket 路由 /api/copy/ws；
#     并在同一文件下注册普通 HTTP 端点用于「查询文件锁状态」「申请/释放文件锁」
#     「申请/释放块锁」「保存前验证 token」。
#     不涉及任何用户身份/登录态/权限。

import json
import os
import sys
import time
import uuid

from flask import Blueprint, jsonify, request
from flask_sock import Sock

# 让该路由可以 import 项目内的 services 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import copy_presence_service  # noqa: E402


# 创建一个 flask-sock 实例供 ws 端点使用
# 实现逻辑：通过 app.config['SOCK'] 复用 app.py 中创建的 Sock 实例
_ws_sock: Sock = None


def init_sock(sock: Sock) -> None:
    # 初始化 flask-sock 实例（在 app.py 中创建后传入）
    global _ws_sock
    _ws_sock = sock


# 普通 HTTP 蓝图
copy_websocket_bp = Blueprint('copy_websocket', __name__)


@copy_websocket_bp.route('/api/copy/lock/acquire', methods=['POST'])
def acquire_file_lock():
    # 申请文件级编辑锁
    # 请求体: {"file_key": "土耳其/xxx.html", "owner_token": "..."}
    # 响应: {"success": true, "ok": true|false, "token": "...", "locked": true|false, "conflict": true|false}
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        owner_token = (data.get('owner_token') or '').strip() or None

        if not file_key:
            return jsonify({'success': False, 'error': '缺少file_key参数'}), 400

        result = copy_presence_service.try_acquire_file_lock(file_key, owner_token)
        status = 200 if result.get('ok') else 409
        return jsonify({'success': True, **result}), status
    except Exception as e:
        print(f"[CopyWS] acquire_file_lock error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_websocket_bp.route('/api/copy/lock/release', methods=['POST'])
def release_file_lock():
    # 释放文件级编辑锁
    # 请求体: {"file_key": "...", "owner_token": "..."}
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        owner_token = (data.get('owner_token') or '').strip()

        if not file_key or not owner_token:
            return jsonify({'success': False, 'error': '缺少参数'}), 400

        released = copy_presence_service.release_file_lock(file_key, owner_token)
        # 释放文件锁时同时清掉所有该文件下的块级锁，避免残留
        copy_presence_service.force_release_block_locks_for_file(file_key)
        return jsonify({'success': True, 'released': released}), 200
    except Exception as e:
        print(f"[CopyWS] release_file_lock error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_websocket_bp.route('/api/copy/lock/heartbeat', methods=['POST'])
def heartbeat_file_lock():
    # 刷新文件级锁的心跳
    # 请求体: {"file_key": "...", "owner_token": "..."}
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        owner_token = (data.get('owner_token') or '').strip()

        if not file_key or not owner_token:
            return jsonify({'success': False, 'error': '缺少参数'}), 400

        result = copy_presence_service.heartbeat(file_key, owner_token)
        return jsonify({'success': True, **result}), 200
    except Exception as e:
        print(f"[CopyWS] heartbeat_file_lock error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_websocket_bp.route('/api/copy/lock/status', methods=['GET'])
def get_file_lock_status():
    # 查询文件锁状态（仅返回 locked: bool，不返回 holder 身份）
    try:
        file_key = (request.args.get('file_key') or '').strip()
        if not file_key:
            return jsonify({'success': False, 'error': '缺少file_key参数'}), 400
        result = copy_presence_service.get_file_lock_status(file_key)
        return jsonify({'success': True, **result}), 200
    except Exception as e:
        print(f"[CopyWS] get_file_lock_status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_websocket_bp.route('/api/copy/lock/all', methods=['GET'])
def list_all_locked_files():
    # 列出当前所有被锁文件 key 列表（用于前端侧边栏"正在编辑"徽章展示）
    # 实现逻辑：调用服务层 list_locked_file_keys，过滤掉心跳已过期的项；
    #          返回数组，元素为 file_key（与 list_copy_files 返回的 relative_path 一致）
    try:
        locked_files = copy_presence_service.list_locked_file_keys()
        return jsonify({'success': True, 'locked_files': locked_files}), 200
    except Exception as e:
        print(f"[CopyWS] list_all_locked_files error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_websocket_bp.route('/api/copy/lock/force-acquire', methods=['POST'])
def force_acquire_file_lock():
    # 强制获取文件锁（无论当前是否有锁，强制接管）
    # 实现逻辑：先 force_release 旧锁并广播 file_unlocked，再创建新锁
    # 用于只读用户主动接管长期未操作的编辑者持有的锁
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        owner_token = (data.get('owner_token') or '').strip()

        if not file_key:
            return jsonify({'success': False, 'error': '缺少file_key参数'}), 400

        # 强制释放旧锁并向所有订阅者通知
        copy_presence_service.force_release_file_lock(file_key)
        copy_presence_service.force_release_block_locks_for_file(file_key)

        # 创建新锁
        token = owner_token or uuid.uuid4().hex
        result = copy_presence_service.try_acquire_file_lock(file_key, token)
        return jsonify({'success': True, **result}), 200
    except Exception as e:
        print(f"[CopyWS] force_acquire_file_lock error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_websocket_bp.route('/api/copy/block/lock', methods=['POST'])
def acquire_block_lock():
    # 申请块级编辑锁
    # 请求体: {"file_key": "...", "block_id": "...", "owner_token": "..."}
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        block_id = (data.get('block_id') or '').strip()
        owner_token = (data.get('owner_token') or '').strip() or None

        if not file_key or not block_id:
            return jsonify({'success': False, 'error': '缺少参数'}), 400

        result = copy_presence_service.try_acquire_block_lock(file_key, block_id, owner_token)
        status = 200 if result.get('ok') else 409
        if result.get('ok') and not result.get('conflict'):
            # 拿到锁后广播给同房间其他人
            copy_presence_service.broadcast(file_key, {
                'type': 'block_locked',
                'file_key': file_key,
                'block_id': block_id,
                'by_token': result.get('token', '')
            })
        return jsonify({'success': True, **result}), status
    except Exception as e:
        print(f"[CopyWS] acquire_block_lock error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@copy_websocket_bp.route('/api/copy/block/unlock', methods=['POST'])
def release_block_lock():
    # 释放块级编辑锁
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        block_id = (data.get('block_id') or '').strip()
        owner_token = (data.get('owner_token') or '').strip()

        if not file_key or not block_id or not owner_token:
            return jsonify({'success': False, 'error': '缺少参数'}), 400

        released = copy_presence_service.release_block_lock(file_key, block_id, owner_token)
        return jsonify({'success': True, 'released': released}), 200
    except Exception as e:
        print(f"[CopyWS] release_block_lock error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# 编辑权限移交 HTTP 端点（纯 HTTP 轮询，不依赖 WS）
# 服务端状态：请求方写入请求 → 持有方轮询发现 → 确认/拒绝 → 请求方轮询获取结果
_HANDOFF_REQUESTS: dict = {}   # {file_key: {from_token, created_at}}
_HANDOFF_RESPONSES: dict = {}  # {file_key: {status: 'accepted'|'rejected', created_at}}
_HANDOFF_TTL_SECONDS = 30

@copy_websocket_bp.route('/api/copy/handoff/request', methods=['POST'])
def http_handoff_request():
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        token = (data.get('token') or '').strip() or ''
        if not file_key:
            return jsonify({'success': False, 'error': '缺少file_key'}), 400
        _HANDOFF_REQUESTS[file_key] = {'from_token': token, 'created_at': time.time()}
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@copy_websocket_bp.route('/api/copy/handoff/incoming', methods=['GET'])
def http_handoff_incoming():
    # 持有锁的用户轮询此端点，检查是否有移交请求
    try:
        file_key = (request.args.get('file_key') or '').strip()
        if not file_key:
            return jsonify({'success': False, 'error': '缺少file_key'}), 400
        req = _HANDOFF_REQUESTS.get(file_key)
        if not req:
            return jsonify({'success': True, 'has_request': False}), 200
        if time.time() - req.get('created_at', 0) > _HANDOFF_TTL_SECONDS:
            _HANDOFF_REQUESTS.pop(file_key, None)
            return jsonify({'success': True, 'has_request': False}), 200
        return jsonify({'success': True, 'has_request': True, 'from_token': req.get('from_token', '')}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@copy_websocket_bp.route('/api/copy/handoff/accepted', methods=['POST'])
def http_handoff_accepted():
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        if not file_key:
            return jsonify({'success': False, 'error': '缺少file_key'}), 400
        _HANDOFF_REQUESTS.pop(file_key, None)  # 清理请求
        _HANDOFF_RESPONSES[file_key] = {'status': 'accepted', 'created_at': time.time()}
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@copy_websocket_bp.route('/api/copy/handoff/rejected', methods=['POST'])
def http_handoff_rejected():
    try:
        data = request.get_json(silent=True) or {}
        file_key = (data.get('file_key') or '').strip()
        if not file_key:
            return jsonify({'success': False, 'error': '缺少file_key'}), 400
        _HANDOFF_REQUESTS.pop(file_key, None)  # 清理请求
        _HANDOFF_RESPONSES[file_key] = {'status': 'rejected', 'created_at': time.time()}
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@copy_websocket_bp.route('/api/copy/handoff/poll', methods=['GET'])
def http_handoff_poll():
    # 请求方轮询此端点，等待持有方的响应
    try:
        file_key = (request.args.get('file_key') or '').strip()
        if not file_key:
            return jsonify({'success': False, 'error': '缺少file_key'}), 400
        resp = _HANDOFF_RESPONSES.get(file_key)
        if not resp:
            # 检查请求是否仍存在（对方可能还没响应）
            if _HANDOFF_REQUESTS.get(file_key):
                return jsonify({'success': True, 'status': 'pending'}), 200
            return jsonify({'success': True, 'status': 'none'}), 200
        if time.time() - resp.get('created_at', 0) > _HANDOFF_TTL_SECONDS:
            _HANDOFF_RESPONSES.pop(file_key, None)
            return jsonify({'success': True, 'status': 'none'}), 200
        result = {'success': True, 'status': resp.get('status', 'none')}
        _HANDOFF_RESPONSES.pop(file_key, None)  # 已读取，清理
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def register_ws_route(sock: Sock) -> None:
    # 注册 WebSocket 路由
    # 实现逻辑：通过 flask-sock 的 @sock.route 装饰器注册 /api/copy/ws
    @sock.route('/api/copy/ws')
    def copy_ws(ws):
        # 单个客户端的 WebSocket 处理器
        # 实现逻辑：
        #   1) 进入循环读取 ws.receive() 的 JSON 消息
        #   2) 根据消息 type 分发到 subscribe / heartbeat / block_lock / block_unlock / content_update
        #   3) subscribe 后定时推送 presence_count 给该 ws
        #   4) 客户端断开时清理订阅并停止定时任务
        import threading

        subscribed_file_key: dict = {'key': None}
        stopped: dict = {'flag': False}
        timer_holder: dict = {'timer': None}

        # flask-sock 的 send() 不自动序列化 dict → 必须手动 json.dumps
        def send_msg(msg: dict) -> None:
            ws.send(json.dumps(msg))

        def stop():
            # 标记停止并清理订阅
            stopped['flag'] = True
            timer = timer_holder.get('timer')
            if timer:
                try:
                    timer.cancel()
                except Exception:
                    pass
            key = subscribed_file_key.get('key')
            if key:
                copy_presence_service.unsubscribe(key, ws)

        def push_presence_count():
            # 定时推送订阅者数量
            if stopped['flag']:
                return
            key = subscribed_file_key.get('key')
            if not key:
                return
            count = copy_presence_service.get_presence_count(key)
            try:
                send_msg({'type': 'presence_count', 'file_key': key, 'count': count})
            except Exception:
                stop()
                return
            timer = threading.Timer(5.0, push_presence_count)
            timer.daemon = True
            timer_holder['timer'] = timer
            timer.start()

        try:
            while not stopped['flag']:
                try:
                    raw = ws.receive()
                except Exception:
                    break
                if raw is None:
                    break

                # 解析 JSON
                try:
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode('utf-8', errors='ignore')
                    message = json.loads(raw) if isinstance(raw, str) else {}
                except Exception:
                    continue

                msg_type = message.get('type')
                file_key = (message.get('file_key') or '').strip()
                token = (message.get('token') or '').strip() or None
                block_id = (message.get('block_id') or '').strip()

                if msg_type == 'subscribe':
                    if not file_key:
                        continue
                    # 取消旧订阅
                    old_key = subscribed_file_key.get('key')
                    if old_key and old_key != file_key:
                        copy_presence_service.unsubscribe(old_key, ws)
                    subscribed_file_key['key'] = file_key
                    copy_presence_service.subscribe(file_key, ws)
                    # 推送当前文件锁状态
                    lock_status = copy_presence_service.get_file_lock_status(file_key)
                    if lock_status.get('locked'):
                        try:
                            send_msg({
                                'type': 'file_locked',
                                'file_key': file_key,
                                'locked': True
                            })
                        except Exception:
                            break
                    # 推送当前 presence count
                    count = copy_presence_service.get_presence_count(file_key)
                    try:
                        send_msg({
                            'type': 'presence_count',
                            'file_key': file_key,
                            'count': count
                        })
                    except Exception:
                        break
                    # 启动 presence 定时推送
                    if not timer_holder.get('timer'):
                        timer = threading.Timer(5.0, push_presence_count)
                        timer.daemon = True
                        timer_holder['timer'] = timer
                        timer.start()

                elif msg_type == 'heartbeat':
                    if file_key and token:
                        copy_presence_service.heartbeat(file_key, token)
                        try:
                            send_msg({
                                'type': 'heartbeat_ack',
                                'file_key': file_key
                            })
                        except Exception:
                            break

                elif msg_type == 'block_lock':
                    if file_key and block_id and token:
                        result = copy_presence_service.try_acquire_block_lock(file_key, block_id, token)
                        try:
                            send_msg({
                                'type': 'block_lock_result',
                                'file_key': file_key,
                                'block_id': block_id,
                                'ok': result.get('ok', False),
                                'conflict': result.get('conflict', False)
                            })
                        except Exception:
                            break
                        if result.get('ok'):
                            copy_presence_service.broadcast(file_key, {
                                'type': 'block_locked',
                                'file_key': file_key,
                                'block_id': block_id,
                                'by_token': token
                            })

                elif msg_type == 'block_unlock':
                    if file_key and block_id and token:
                        copy_presence_service.release_block_lock(file_key, block_id, token)

                elif msg_type == 'content_update':
                    if file_key and block_id and token:
                        html_content = message.get('html', '')
                        copy_presence_service.broadcast(file_key, {
                            'type': 'content_update',
                            'file_key': file_key,
                            'block_id': block_id,
                            'html': html_content,
                            'by_token': token
                        })

                # 编辑权限移交协议：请求→接受/拒绝，全部通过广播通知同一文件的所有订阅者
                elif msg_type == 'handoff_request':
                    if file_key:
                        copy_presence_service.broadcast(file_key, {
                            'type': 'handoff_request',
                            'file_key': file_key,
                            'from_token': token or ''
                        })
                elif msg_type == 'handoff_accepted':
                    if file_key:
                        copy_presence_service.broadcast(file_key, {
                            'type': 'handoff_accepted',
                            'file_key': file_key,
                            'from_token': token or ''
                        })
                elif msg_type == 'handoff_rejected':
                    if file_key:
                        copy_presence_service.broadcast(file_key, {
                            'type': 'handoff_rejected',
                            'file_key': file_key,
                            'from_token': token or ''
                        })

                elif msg_type == 'ping':
                    try:
                        send_msg({'type': 'pong'})
                    except Exception:
                        break
                else:
                    # 未知消息类型，忽略
                    continue
        except Exception as e:
            print(f"[CopyWS] ws loop error: {e}")
        finally:
            stop()
