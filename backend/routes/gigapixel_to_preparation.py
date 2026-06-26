# Gigapixel 放大结果转预备 路由
#
# 功能描述：
#     提供 /api/gigapixel/copy-to-preparation 接口，
#     将 Topaz Gigapixel AI 已成功任务的放大结果图片复制到预备目录
#     （generated_images/预备），并写入 preparation_items 数据库记录，
#     使其出现在「预备」页面（PreparationView）中。
#
# 接口列表：
#     - POST /api/gigapixel/copy-to-preparation - 复制 gigapixel 输出到预备目录
#
# 实现逻辑：
#     1. 接收前端传来的 task_id，定位对应的 gigapixel 任务记录
#     2. 校验任务状态必须为 SUCCESS（项目规则：失败优先）
#     3. 关联查询 images 表，取 local_path（gigapixel_output 目录下的最终文件）
#     4. 校验源文件存在；不存在则 400
#     5. 用 unique_destination_path 生成不冲突的目标文件名
#     6. shutil.copy2 复制到 PREPARATION_DIR
#     7. 写入 preparation_items 表（platform='topaz_gigapixel' 标识来源）
#     8. 返回新创建的 item 记录
#
# 失败处理（项目规则：失败优先）：
#     - 缺 task_id -> 400
#     - 任务不存在 -> 404
#     - 任务状态非 SUCCESS -> 400
#     - 关联 image 不存在 -> 400
#     - 源文件不存在（被外部清理）-> 400
#     - 文件复制/数据库写入异常 -> 500 兜底
#
# 用户操作异常考虑：
#     - 用户对同一任务多次点击 -> 不阻止，由 unique_destination_path 生成不同文件名
#     - 用户点击时源文件刚好被删 -> 400 提示
#     - 用户在准备页面刷新后再次点击 -> 重复复制，不影响功能

import os
import uuid
import shutil
from datetime import datetime
from flask import Blueprint, request, jsonify

# 复用 preparation 模块中的常量、helper、序列化函数
# 避免重复实现与现有 copy-from 端点保持行为一致
from .preparation import (
    PREPARATION_DIR,
    unique_destination_path,
    serialize_preparation_item,
    get_db_connection,
)

# 复用 image_model 提供的 get_task / get_image_by_id
from models.image_model import get_task, get_image_by_id


# 创建蓝图
gigapixel_to_preparation_bp = Blueprint('gigapixel_to_preparation', __name__)


@ gigapixel_to_preparation_bp.route('/api/gigapixel/copy-to-preparation', methods=['POST'])
def copy_gigapixel_to_preparation():
    """
    将 gigapixel 任务的放大结果复制到预备目录并创建数据库记录

    请求体 JSON:
        {
            "task_id": "uuid-string"   // 必填，gigapixel 任务 ID
        }

    返回：
        200: { success: true, item: {...}, message: "已复制到预备目录" }
        400: { success: false, error: "..." }
        404: { success: false, error: "..." }
        500: { success: false, error: "..." }
    """
    try:
        # 解析请求参数
        data = request.get_json(silent=True) or {}
        task_id = (data.get('task_id') or '').strip()

        # 校验：必须提供 task_id
        if not task_id:
            return jsonify({
                'success': False,
                'error': 'task_id 不能为空'
            }), 400

        # 读取任务记录
        task = get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': f'任务不存在: {task_id}'
            }), 404

        # 校验任务状态必须为 SUCCESS
        current_status = task.get('status')
        if current_status != 'SUCCESS':
            return jsonify({
                'success': False,
                'error': f'任务状态为 {current_status}，只有已成功（SUCCESS）的任务可以复制到预备'
            }), 400

        # 读取关联的 image 记录，取 local_path
        image_id = task.get('image_id') or ''
        if not image_id:
            return jsonify({
                'success': False,
                'error': '该任务没有关联的图片记录，无法复制'
            }), 400

        source_image = get_image_by_id(image_id)
        if not source_image:
            return jsonify({
                'success': False,
                'error': f'关联图片不存在: {image_id}'
            }), 400

        # 取源文件路径（gigapixel_output 目录下的最终产物）
        # local_path 兼容 dict 和 ImageItem 对象
        if isinstance(source_image, dict):
            source_path = source_image.get('local_path') or ''
        else:
            source_path = getattr(source_image, 'local_path', '') or ''

        if not source_path or not os.path.exists(source_path):
            return jsonify({
                'success': False,
                'error': f'源文件不存在或已被清理: {source_path or "(空路径)"}'
            }), 400

        # 准备目标文件名（保留原扩展名，使用 unique_destination_path 避免冲突）
        original_filename = os.path.basename(source_path)
        name_without_ext, ext = os.path.splitext(original_filename)
        if not ext:
            ext = '.png'

        # 确保预备目录存在
        os.makedirs(PREPARATION_DIR, exist_ok=True)

        # 生成不冲突的目标路径
        target_path, target_filename = unique_destination_path(PREPARATION_DIR, original_filename)

        # 复制源文件到预备目录（copy2 保留元数据；原文件保留不动）
        shutil.copy2(source_path, target_path)

        # 写入 preparation_items 表
        # platform='topap_gigapixel' 便于在 PreparationView 中筛来源
        item_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        display_name = name_without_ext

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO preparation_items (
                    id, filename, folder_path, display_name, platform, score, copy_text, copy_title,
                    is_usable, is_publishable, publish_date, social_copy, publish_code, poster_copy, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item_id, target_filename, '', display_name, 'topaz_gigapixel',
                0, '', '', 0, 0, '', '', '', '',
                now, now
            ))
            conn.commit()

            # 回读写入的记录
            cursor.execute('SELECT * FROM preparation_items WHERE id = ?', (item_id,))
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return jsonify({
                'success': False,
                'error': '创建预备记录失败，数据库回读为空'
            }), 500

        print(f'[GigapixelToPreparation] 已复制 task_id={task_id} -> {target_path}')

        return jsonify({
            'success': True,
            'item': serialize_preparation_item(row),
            'message': f'已复制到预备目录：{target_filename}'
        }), 200

    except Exception as e:
        # 失败兜底：记录日志后返回 500
        print(f'[GigapixelToPreparation] copy-to-preparation error: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
