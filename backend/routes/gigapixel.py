# Topaz Gigapixel AI HTTP 接口路由
#
# 功能描述：
#     提供 /api/gigapixel/* 系列 HTTP 接口，前端通过这些接口：
#     1. 检查本机 Topaz Gigapixel AI 是否可用
#     2. 上传本地图片到服务器磁盘（multipart）
#     3. 提交异步放大任务
#     4. 轮询任务状态 / 任务历史
#     5. 取消正在运行的任务
#     6. 列出已完成结果
#
# 实现逻辑：
#     - 上传：multipart/form-data -> 校验类型大小 -> 落盘 gigapixel_temp/uploads/ -> 返回本地路径 + 预览 URL
#     - 提交任务：解析 image_id/image_path -> 校验参数 -> 创建 image 占位记录 -> 创建 task 行 -> 推入后台队列
#     - 查询任务：读 tasks + images 表，组合返回
#     - 取消任务：标记 tasks.status='CANCELLED'，worker 完成后处理时会检查并丢弃结果
#     - 检查可用性：读 topaz_gigapixel 配置 -> 调 service.check_available()
#     - 失败处理：所有 catch 都返回 {success:false, error:'...'} 4xx
#
# 用户操作异常考虑：
#     - 用户未选图：400 提示
#     - 用户选不存在的 image_id：查不到记录，400
#     - 用户重复点击提交：每个提交独立 task，不去重
#     - 取消已被取消的任务：返回 400（避免重复处理）
#     - 取消已 SUCCESS/FAILURE 的任务：返回 400
#     - 提交时 exe 不可用：400 提示用户去设置页配置

import os
import re
import time
import uuid
from flask import Blueprint, request, jsonify, send_file

from models.config_model import get_single_config
from models.image_model import (
    add_image,
    add_task,
    get_db_connection,
    get_image_by_id,
    get_task,
    update_image,
    update_task,
)
from services.gigapixel_task_service import (
    enqueue_gigapixel_task,
    get_gigapixel_task_service,
)


gigapixel_bp = Blueprint('gigapixel', __name__)

# 支持的图片 MIME -> 文件后缀 映射
_ALLOWED_MIME_EXT = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/tiff': '.tif',
    'image/tif': '.tif',
}
# 单文件最大 50MB
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _get_project_root():
    """
    获取真正的项目根目录（e:\\AI-image）。
    __file__ = backend/routes/gigapixel.py，向上 3 级得到项目根。
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_upload_dir():
    """获取上传目录绝对路径（项目根/gigapixel_temp/uploads/），确保目录存在。"""
    d = os.path.join(_get_project_root(), 'gigapixel_sources', 'uploads')
    os.makedirs(d, exist_ok=True)
    return d


# 本地上传接口（multipart/form-data 文件上传）
@gigapixel_bp.route('/api/gigapixel/upload', methods=['POST'])
def upload_file():
    """
    接收前端 FormData 上传的图片文件，落盘到服务器本地磁盘，
    返回绝对路径供后续 submit 接口使用。

    请求：multipart/form-data，字段名 file
    返回：
        200: { success: true, uploaded_path: "E:\\...absolute...", filename: "..." }
        400: { success: false, error: "..." }
    """
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '缺少 file 字段'}), 400

        f = request.files['file']
        if not f or not f.filename:
            return jsonify({'success': False, 'error': '未选择文件'}), 400

        # 校验 MIME
        mime = (f.content_type or '').lower()
        ext = _ALLOWED_MIME_EXT.get(mime)
        if not ext:
            return jsonify({
                'success': False,
                'error': f'不支持的格式: {f.content_type}，仅支持 JPG / PNG / WebP / TIFF'
            }), 400

        # 校验大小（读入内存前先检查 Content-Length 快速拒绝）
        cl = request.content_length
        if cl and cl > _MAX_UPLOAD_BYTES:
            return jsonify({
                'success': False,
                'error': f'文件过大，最大 50MB，当前约 {round(cl / 1024 / 1024, 1)}MB'
            }), 400

        # 读取文件内容
        raw = f.read()
        if len(raw) > _MAX_UPLOAD_BYTES:
            return jsonify({
                'success': False,
                'error': f'文件过大，最大 50MB，当前 {round(len(raw) / 1024 / 1024, 1)}MB'
            }), 400

        # 写入磁盘
        upload_dir = _get_upload_dir()
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', f.filename or 'upload')
        ts = int(time.time() * 1000)
        uid = uuid.uuid4().hex[:8]
        filename = f'{os.path.splitext(safe_name)[0]}_{ts}_{uid}{ext}'
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, 'wb') as fw:
            fw.write(raw)
        abs_path = os.path.abspath(file_path)
        print(f'[gigapixel] upload success: {abs_path}')
        return jsonify({
            'success': True,
            'uploaded_path': abs_path,
            'filename': filename
        }), 200

    except Exception as e:
        print(f'[gigapixel] upload 异常: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# 检查 Topaz Gigapixel AI 是否可用
@gigapixel_bp.route('/api/gigapixel/check', methods=['GET'])
def check_gigapixel():
    """
    检查本机 Topaz Gigapixel AI 是否可用。

    实现逻辑：
        1. 读 topaz_gigapixel 配置（exePath/useSystemCommand）
        2. 调 TopazGigapixelService.check_available
        3. 返回 {available, exe_path, error}

    返回：
        { success: true, available, exe_path, error }
    """
    try:
        config = get_single_config('topaz_gigapixel') or {}
        exe_path = config.get('exePath', '') or ''
        use_system_command = bool(config.get('useSystemCommand', False))

        from services.topaz_gigapixel_service import TopazGigapixelService
        service = TopazGigapixelService(
            exe_path=exe_path,
            use_system_command=use_system_command
        )
        available, message = service.check_available()

        return jsonify({
            'success': True,
            'available': available,
            'exe_path': exe_path,
            'use_system_command': use_system_command,
            'message': message
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'available': False,
            'error': str(e)
        }), 500


# 提交异步放大任务
@gigapixel_bp.route('/api/gigapixel/upscale', methods=['POST'])
def submit_upscale():
    """
    提交一个 Topaz Gigapixel AI 异步放大任务。

    请求体 JSON:
        {
            "image_id": "xxx",       // 二选一：从图片库选（图片库里的图已有本地 local_path）
            "image_path": "E:\\...", // 二选一：通过 /api/gigapixel/upload 上传后拿到的绝对路径
            "scale": 2.0,
            "model": "Standard",
            "enabled": true,
            "sharpen": 1,            // ComfyUI 官方默认 1；0=不传该参数
            "denoise": 1,
            "compression": 67,
            "fr": 50,
            "pre_downscaling": 75
        }

    实现逻辑：
        1. 解析 image_id 或 image_path（两者都是本地磁盘上的绝对/相对路径，直接传给 gigapixel.exe）
        2. 校验 scale (1-16)、model 是否在支持列表
        3. 校验 exe 可用性（避免用户提交后再失败）
        4. 创建 image 占位记录（type='gigapixel', api_source='topaz_gigapixel'）
        5. 创建 task 行（api_source='topaz_gigapixel', status='PENDING'）
        6. 推入 GigapixelTaskService 队列
        7. 返回 202 + {task_id, image_id}

    返回：
        202: { success: true, task_id, image_id, status: 'pending' }
        400: { success: false, error: '...' }
        500: { success: false, error: '...' }
    """
    try:
        data = request.get_json(silent=True) or {}

        image_id = data.get('image_id') or ''
        image_path_input = data.get('image_path') or ''

        scale = data.get('scale', 2.0)
        model = data.get('model', 'Standard') or 'Standard'
        enabled = bool(data.get('enabled', True))
        # 兜底值与 ComfyUI-GigapixelAI 节点 GigapixelUpscaleSettings 一致：
        # sharpen=1 / denoise=1 / compression=67 / fr=50 / pre_downscaling=75
        # 注意：gigapixel.exe 命令行只在该参数 > 0 时才真正传递，0 = 不传
        sharpen = data.get('sharpen', 1)
        denoise = data.get('denoise', 1)
        compression = data.get('compression', 67)
        fr = data.get('fr', 50)
        pre_downscaling = data.get('pre_downscaling', 75)

        # 校验：必须二选一
        if not image_id and not image_path_input:
            return jsonify({'success': False, 'error': '必须提供 image_id 或 image_path'}), 400

        # 校验 scale
        try:
            scale_val = float(scale)
            if scale_val < 1.0 or scale_val > 16.0:
                return jsonify({'success': False, 'error': 'scale 必须在 1.0-16.0 之间'}), 400
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'scale 必须为数字'}), 400

        # 校验 model
        from services.topaz_gigapixel_service import MODEL_MAPPING
        if model not in MODEL_MAPPING:
            return jsonify({
                'success': False,
                'error': f'不支持的模型: {model}, 支持: {list(MODEL_MAPPING.keys())}'
            }), 400

        # 解析输入图片绝对路径
        # image_path 只接受两种来源（都是本地磁盘上的路径）：
        #   1. image_id -> 图片库选图 -> source_image.local_path
        #   2. image_path -> /api/gigapixel/upload 返回的本地路径
        input_path = ''
        source_image = None

        if image_id:
            source_image = get_image_by_id(image_id)
            if not source_image:
                return jsonify({'success': False, 'error': f'未找到图片: {image_id}'}), 400
            input_path = source_image.local_path or ''
            if not input_path or not os.path.exists(input_path):
                return jsonify({
                    'success': False,
                    'error': '所选图片无本地文件路径，请先确保图片已下载到本地'
                }), 400
        else:
            input_path = image_path_input
            if not os.path.exists(input_path):
                return jsonify({
                    'success': False,
                    'error': f'图片路径不存在: {input_path}。请先通过 /api/gigapixel/upload 上传。'
                }), 400

        # 预检 exe 可用性
        config = get_single_config('topaz_gigapixel') or {}
        exe_path = config.get('exePath', '') or ''
        use_system_command = bool(config.get('useSystemCommand', False))
        from services.topaz_gigapixel_service import TopazGigapixelService
        service = TopazGigapixelService(exe_path=exe_path, use_system_command=use_system_command)
        available, err_msg = service.check_available()
        if not available:
            return jsonify({
                'success': False,
                'error': f'Gigapixel AI 不可用: {err_msg}，请到「设置」配置 exe 路径',
                'code': 'GIGAPIXEL_UNAVAILABLE'
            }), 400

        # 准备 settings dict
        settings = {
            'scale': scale_val,
            'model': model,
            'enabled': enabled,
            'sharpen': float(sharpen) if sharpen is not None else 1,
            'denoise': float(denoise) if denoise is not None else 1,
            'compression': float(compression) if compression is not None else 67,
            'fr': float(fr) if fr is not None else 50,
            'pre_downscaling': float(pre_downscaling) if pre_downscaling is not None else 75,
        }

        # 创建 image 占位记录
        # 注意：add_image 不接受 id 参数，内部自动生成；返回值才有 id
        prompt_text = ''
        if source_image:
            prompt_text = f'Gigapixel 放大 ({settings["model"]} x{settings["scale"]}) - 源自 {source_image.title or source_image.id}'
        else:
            prompt_text = f'Gigapixel 放大 ({settings["model"]} x{settings["scale"]}) - 源自 {os.path.basename(input_path)}'

        # 复用 add_image 写入占位（url 留空，worker 完成后回填）
        new_image = add_image(
            url='',
            thumbnail='',
            prompt=prompt_text,
            model=model,
            size='',
            quality='gigapixel',
            task_id='',  # 后面回填
            local_path=input_path,
            thumbnail_path='',
            title=os.path.splitext(os.path.basename(input_path))[0],
            image_type='gigapixel',
            api_source='topaz_gigapixel',
            poster_copy=''
        )
        new_image_id = new_image.id

        # 创建 task 行
        task_id = str(uuid.uuid4())
        add_task(
            task_id=task_id,
            image_id=new_image_id,
            platform='topaz_gigapixel',
            status='PENDING',
            api_source='topaz_gigapixel',
            submit_time=int(time.time() * 1000),
            progress='0%',
            data={
                'input_path': input_path,
                'settings': settings,
                'source_image_id': image_id or None,
            }
        )

        # 回填 image.task_id
        new_image.task_id = task_id
        update_image(new_image)

        # 推入后台队列
        enqueue_gigapixel_task(
            task_id=task_id,
            image_id=new_image_id,
            input_path=input_path,
            settings=settings
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'image_id': new_image_id,
            'status': 'pending'
        }), 202

    except Exception as e:
        print(f'[GigapixelRoute] submit_upscale error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# 查询单个任务状态
def _get_task_input_path(task_id):
    task = get_task(task_id)
    if not task:
        return ''
    data = task.get('data') or {}
    input_path = data.get('input_path') or ''
    if not input_path or not os.path.isfile(input_path):
        return ''
    return os.path.abspath(input_path)


@gigapixel_bp.route('/api/gigapixel/input/<task_id>', methods=['GET'])
def serve_task_input(task_id):
    input_path = _get_task_input_path(task_id)
    if not input_path:
        return jsonify({'success': False, 'error': 'input image not found'}), 404
    return send_file(input_path)


@gigapixel_bp.route('/api/gigapixel/task/<task_id>', methods=['GET'])
def query_task(task_id):
    """
    查询单个 gigapixel 任务状态。

    实现逻辑：
        1. 读 tasks 行
        2. 关联读 images 行（task.image_id）
        3. 组合返回 status/progress/fail_reason/data/image

    返回：
        { success, task: { id, status, progress, fail_reason, data, start_time, finish_time, submit_time }, image: {...} | null }
    """
    try:
        task = get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        image_data = None
        image_id = task.get('image_id')
        if image_id:
            img = get_image_by_id(image_id)
            if img:
                image_data = _serialize_image(img)
        task_data = dict(task.get('data') or {})
        if task_data.get('input_path') and os.path.isfile(task_data.get('input_path')):
            task_data['input_url'] = f'/api/gigapixel/input/{task_id}'

        return jsonify({
            'success': True,
            'task': {
                'id': task.get('id'),
                'status': task.get('status'),
                'progress': task.get('progress'),
                'fail_reason': task.get('fail_reason'),
                'submit_time': task.get('submit_time'),
                'start_time': task.get('start_time'),
                'finish_time': task.get('finish_time'),
                'data': task_data,
                'platform': task.get('platform'),
                'api_source': task.get('api_source'),
            },
            'image': image_data
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 任务历史列表
@ gigapixel_bp.route('/api/gigapixel/tasks', methods=['GET'])
def list_tasks():
    """
    列出所有 topaz_gigapixel 任务（按 submit_time 倒序）。

    Query:
        status: 可选，按状态过滤（PENDING/IN_PROGRESS/SUCCESS/FAILURE/CANCELLED）
        limit: 默认 50
        cleanup_invalid: 可选，默认 false。
            为 true 时自动过滤掉「失败任务」和「图片不在 gigapixel_output 的任务」：
              - status IN ('FAILURE', 'CANCELLED') 视为失败任务，直接过滤
              - 关联 image 缺失 / local_path 为空 -> 过滤
              - local_path 不在 gigapixel_output 目录下 -> 过滤
              - local_path 指向的文件不存在 -> 过滤
              - PENDING/IN_PROGRESS 任务无论图片是否存在都保留（用户能继续轮询）

    返回：
        { success, tasks: [...], filtered_count?: int }
    """
    try:
        status_filter = (request.args.get('status') or '').strip()
        try:
            limit = int(request.args.get('limit') or 50)
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))
        # 是否启用失效任务清理（默认关闭，保持向后兼容）
        cleanup_invalid = (request.args.get('cleanup_invalid') or '').strip().lower() in ('1', 'true', 'yes')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if status_filter:
                cursor.execute('''
                    SELECT * FROM tasks
                    WHERE api_source = ? AND status = ?
                    ORDER BY COALESCE(submit_time, 0) DESC
                ''', ('topaz_gigapixel', status_filter))
            else:
                cursor.execute('''
                    SELECT * FROM tasks
                    WHERE api_source = ?
                    ORDER BY COALESCE(submit_time, 0) DESC
                ''', ('topaz_gigapixel',))
            rows = cursor.fetchall()

            # 预取所有相关 image 的 local_path（一次查询，避免 N+1）
            image_ids = {row['image_id'] for row in rows if row['image_id']}
            image_local_paths = {}
            if image_ids:
                placeholders = ','.join('?' * len(image_ids))
                cursor.execute(
                    f'SELECT id, local_path FROM images WHERE id IN ({placeholders})',
                    tuple(image_ids)
                )
                for img_row in cursor.fetchall():
                    image_local_paths[img_row['id']] = img_row['local_path'] or ''
        finally:
            conn.close()

        # gigapixel_output 目录的绝对路径（项目根/gigapixel_output）
        # 用与 gigapixel_task_service 一致的方式计算，跨平台兼容
        _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        gigapixel_output_dir_abs = os.path.normcase(os.path.abspath(os.path.join(_project_root, 'gigapixel_output')))

        def is_image_in_gigapixel_output(task_row):
            """
            判断任务的图片是否仍位于 gigapixel_output 目录中且文件存在。
            返回 True 表示保留，False 表示应过滤。
            """
            # PENDING/IN_PROGRESS 任务无论图片是否存在都保留（用户能继续轮询）
            status = task_row['status']
            if status in ('PENDING', 'IN_PROGRESS', '未启动', 'QUEUED', 'NOT_STARTED', 'NOT_START', 'WAITING'):
                return True

            # 失败/取消的任务一律过滤
            if status in ('FAILURE', 'CANCELLED'):
                return False

            # SUCCESS 任务需要进一步校验图片文件
            local_path = image_local_paths.get(task_row['image_id']) or ''
            if not local_path:
                return False
            local_path_abs = os.path.normcase(os.path.abspath(local_path))
            # 必须位于 gigapixel_output 目录
            try:
                if os.path.commonpath([local_path_abs, gigapixel_output_dir_abs]) != gigapixel_output_dir_abs:
                    return False
            except ValueError:
                # 跨盘符等异常情况，直接视为不在
                return False
            # 文件必须真实存在
            return os.path.isfile(local_path_abs)

        tasks = []
        filtered_count = 0
        for row in rows:
            # cleanup_invalid 模式下过滤失效任务
            if cleanup_invalid and not is_image_in_gigapixel_output(row):
                filtered_count += 1
                continue

            task = dict(row)
            if task.get('data') and isinstance(task['data'], str):
                import json
                try:
                    task['data'] = json.loads(task['data'])
                except Exception:
                    task['data'] = {}
            tasks.append({
                'id': task.get('id'),
                'image_id': task.get('image_id'),
                'status': task.get('status'),
                'progress': task.get('progress'),
                'fail_reason': task.get('fail_reason'),
                'submit_time': task.get('submit_time'),
                'start_time': task.get('start_time'),
                'finish_time': task.get('finish_time'),
                'data': task.get('data'),
            })
            # limit 截断
            if len(tasks) >= limit:
                break

        response = {'success': True, 'tasks': tasks}
        # 仅在 cleanup_invalid 启用时返回被过滤的数量，方便前端提示用户
        if cleanup_invalid:
            response['filtered_count'] = filtered_count
        return jsonify(response), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 取消任务
@gigapixel_bp.route('/api/gigapixel/task/<task_id>', methods=['DELETE'])
def cancel_task(task_id):
    """
    取消一个 gigapixel 任务。

    实现逻辑：
        1. 读 tasks 行
        2. 仅当 status 属于 pending 状态时才能取消
        3. 标记 status='CANCELLED'，worker 完成时检查并丢弃结果
        4. 不强杀进行中的 subprocess（避免文件锁 / 孤儿进程）

    返回：
        { success, message } 或 400（不能取消的终态）
    """
    try:
        task = get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        current_status = task.get('status')
        cancellable = {'PENDING', 'IN_PROGRESS', '未启动', 'QUEUED', 'NOT_STARTED', 'NOT_START', 'WAITING'}
        if current_status not in cancellable:
            return jsonify({
                'success': False,
                'error': f'任务状态为 {current_status}，无法取消'
            }), 400

        update_task(
            task_id,
            status='CANCELLED',
            fail_reason='用户取消',
            finish_time=int(time.time() * 1000)
        )

        return jsonify({
            'success': True,
            'message': '已标记取消，正在运行的任务将在完成时丢弃结果'
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 列出已完成 gigapixel 结果
@gigapixel_bp.route('/api/gigapixel/outputs', methods=['GET'])
def list_outputs():
    """
    列出所有 image_type='gigapixel' 的图片（前端可作为结果图库展示）。

    返回：
        { success, images: [...] }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM images
                WHERE image_type = 'gigapixel'
                ORDER BY created_at DESC
                LIMIT 200
            ''')
            rows = cursor.fetchall()
        finally:
            conn.close()

        images = []
        for row in rows:
            images.append(_serialize_image_row(row))

        return jsonify({'success': True, 'images': images}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 查询 gigapixel 队列状态（用于前端展示）
@gigapixel_bp.route('/api/gigapixel/queue', methods=['GET'])
def query_queue():
    """
    查询后台 worker 池状态（队列长度、worker 数量）。

    返回：
        { success, queue_size, max_workers, running }
    """
    try:
        try:
            svc = get_gigapixel_task_service()
            return jsonify({
                'success': True,
                'queue_size': svc.queue_size,
                'max_workers': svc._max_workers,
                'running': svc._running
            }), 200
        except RuntimeError:
            return jsonify({
                'success': True,
                'queue_size': 0,
                'max_workers': 0,
                'running': False
            }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _serialize_image(img):
    """
    将 ImageItem 序列化为 dict（与现有 image API 保持一致字段名）。
    """
    return {
        'id': getattr(img, 'id', ''),
        'url': getattr(img, 'url', '') or '',
        'thumbnail': getattr(img, 'thumbnail', '') or '',
        'prompt': getattr(img, 'prompt', '') or '',
        'model': getattr(img, 'model', '') or '',
        'title': getattr(img, 'title', '') or '',
        'local_path': getattr(img, 'local_path', '') or '',
        'thumbnail_path': getattr(img, 'thumbnail_path', '') or '',
        'image_type': getattr(img, 'image_type', '') or '',
        'api_source': getattr(img, 'api_source', '') or '',
        'task_id': getattr(img, 'task_id', '') or '',
        'parent_id': getattr(img, 'parent_id', '') or '',
        'created_at': getattr(img, 'created_at', '') or '',
        'updated_at': getattr(img, 'updated_at', '') or '',
    }


def _serialize_image_row(row):
    """
    将 images 表的 row 直接序列化为 dict（用于 /outputs 接口）。
    """
    return {
        'id': row['id'],
        'url': row['url'] or '',
        'thumbnail': row['thumbnail'] or '',
        'prompt': row['prompt'] or '',
        'model': row['model'] or '',
        'title': row['title'] or '',
        'local_path': row['local_path'] or '',
        'thumbnail_path': row['thumbnail_path'] or '',
        'image_type': row['image_type'] or '',
        'api_source': row['api_source'] or '',
        'task_id': row['task_id'] or '',
        'parent_id': row['parent_id'] or '',
        'created_at': row['created_at'] or '',
        'updated_at': row['updated_at'] or '',
    }
