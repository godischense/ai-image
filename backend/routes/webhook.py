from flask import Blueprint, request, jsonify
from models.image_model import get_image_by_task_id, update_image, get_task, update_task


webhook_bp = Blueprint('webhook', __name__)


# 将 webhook 收到的状态值标准化
# 功能描述：
#   webhook 回调中的状态可能是 'succeeded'/'failed' 等小写变体，
#   需要标准化后写入 tasks 表，确保前端能正确识别终态
# 实现逻辑：
#   1. succeeded 等 → SUCCESS
#   2. failed 等 → FAILURE
#   3. 其他状态保持 IN_PROGRESS
def normalize_webhook_status(raw_status: str) -> str:
    if not raw_status:
        return 'IN_PROGRESS'
    status_lower = str(raw_status).strip().lower()
    if status_lower in ('succeeded', 'success', 'completed', 'complete', 'done', 'finished'):
        return 'SUCCESS'
    if status_lower in ('failed', 'failure', 'fail', 'error', 'cancelled'):
        return 'FAILURE'
    return 'IN_PROGRESS'


@webhook_bp.route('/api/webhook/image', methods=['POST'])
def image_webhook():
    """
    接收图像生成完成的 webhook 回调

    功能描述：
        API 在异步图像生成完成后会向此端点发送 POST 请求。
        同时更新 images 表（图片 URL）和 tasks 表（任务状态），
        确保前端轮询时能立即看到终态。

    实现逻辑：
        1. 解析回调数据，提取 task_id 和状态
        2. 标准化状态值（succeeded → SUCCESS, failed → FAILURE）
        3. 更新 images 表的 url/thumbnail/prompt
        4. 同步更新 tasks 表的 status
        5. 如果 task 在数据库中存在但 image 不存在，只更新 task 状态
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        task_id = data.get('id')
        status = data.get('status')
        
        if not task_id:
            return jsonify({'error': 'task_id is required'}), 400

        normalized_status = normalize_webhook_status(status)
        
        if normalized_status == 'SUCCESS':
            result = data.get('result', {})
            image_data = result.get('data', [{}])[0] if result.get('data') else {}
            image_url = image_data.get('url', '')
            revised_prompt = image_data.get('revised_prompt', '')
            
            existing_image = get_image_by_task_id(task_id)
            if existing_image:
                existing_image.url = image_url
                existing_image.thumbnail = image_url
                if revised_prompt:
                    existing_image.prompt = revised_prompt
                update_image(existing_image)

                # 同步更新 tasks 表状态，确保前端能立即识别终态
                update_task(
                    task_id,
                    status='SUCCESS',
                    data={
                        'image_url': image_url,
                        'revised_prompt': revised_prompt,
                        'source': 'webhook'
                    }
                )
                
                return jsonify({
                    'status': 'success',
                    'message': 'Image and task updated successfully',
                    'task_id': task_id
                }), 200
            else:
                # image 不存在但可能 task 记录存在，尝试更新 task 状态
                existing_task = get_task(task_id)
                if existing_task:
                    update_task(
                        task_id,
                        status='SUCCESS',
                        data={
                            'image_url': image_url,
                            'revised_prompt': revised_prompt,
                            'source': 'webhook',
                            'note': 'image record not found'
                        }
                    )
                    return jsonify({
                        'status': 'success',
                        'message': 'Task updated but image record not found',
                        'task_id': task_id
                    }), 200

                return jsonify({
                    'status': 'not_found',
                    'message': 'Task not found in database',
                    'task_id': task_id
                }), 200
        
        elif normalized_status == 'FAILURE':
            error = data.get('error', {})
            error_message = error.get('message', 'Unknown error')

            # 同步更新 tasks 表状态
            update_task(
                task_id,
                status='FAILURE',
                fail_reason=error_message,
                data={'source': 'webhook', 'error_detail': str(data.get('error', {}))}
            )

            return jsonify({
                'status': 'failed',
                'message': f'Task failed: {error_message}',
                'task_id': task_id
            }), 200
        
        else:
            return jsonify({
                'status': 'processing',
                'message': 'Task is still processing',
                'task_id': task_id
            }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/api/webhook/health', methods=['GET'])
def webhook_health():
    """
    Webhook 健康检查端点
    用于验证 webhook URL 是否可达
    """
    return jsonify({
        'status': 'healthy',
        'message': 'Webhook endpoint is ready'
    }), 200
