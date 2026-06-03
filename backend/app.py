import logging
import os
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from models.config_model import ensure_config_data_ready, get_single_config

# 配置日志格式和级别，确保所有模块的日志都能输出到控制台
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = Flask(__name__)
CORS(app)

ensure_config_data_ready()

image_api_config = get_single_config('image_api')
server_config = get_single_config('server')

IMAGE_API_BASE_URL = image_api_config.get('baseUrl', '')
IMAGE_API_KEY = image_api_config.get('apiKey', '')
IMAGE_MODELS = image_api_config.get('imageModels', [])

PORT = server_config.get('port', 5678)

fal_api_config = get_single_config('fal_api')
FAL_API_KEY = fal_api_config.get('apiKey', '')
FAL_MODELS = fal_api_config.get('falModels', [])

gptsapi_api_config = get_single_config('gptsapi_api')
GPTSAPI_BASE_URL = gptsapi_api_config.get('baseUrl', 'https://api.gptsapi.net')
GPTSAPI_API_KEY = gptsapi_api_config.get('apiKey', '')

file_upload_config = get_single_config('file_upload')
FILE_UPLOAD_BASE_URL = file_upload_config.get('baseUrl', '')
FILE_UPLOAD_API_KEY = file_upload_config.get('apiKey', '')

app.config['IMAGE_API_BASE_URL'] = IMAGE_API_BASE_URL
app.config['IMAGE_API_KEY'] = IMAGE_API_KEY
app.config['IMAGE_MODELS'] = IMAGE_MODELS
app.config['SERVER_PORT'] = PORT
app.config['FAL_API_KEY'] = FAL_API_KEY
app.config['FAL_MODELS'] = FAL_MODELS
app.config['GPTSAPI_BASE_URL'] = GPTSAPI_BASE_URL
app.config['GPTSAPI_API_KEY'] = GPTSAPI_API_KEY
app.config['FILE_UPLOAD_BASE_URL'] = FILE_UPLOAD_BASE_URL
app.config['FILE_UPLOAD_API_KEY'] = FILE_UPLOAD_API_KEY

from routes.images import images_bp
from routes.config import config_bp
from routes.webhook import webhook_bp
from routes.folder_manager import folder_manager_bp
from routes.recycle_bin import recycle_bp
from routes.material import material_bp
from routes.prompt import prompt_bp
from routes.image_proxy import image_proxy_bp
from routes.file_upload import file_upload_bp
from routes.preparation import preparation_bp
from routes.copy_management import copy_management_bp

app.register_blueprint(images_bp)
app.register_blueprint(config_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(folder_manager_bp)
app.register_blueprint(recycle_bp)
app.register_blueprint(material_bp)
app.register_blueprint(prompt_bp)
app.register_blueprint(image_proxy_bp)
app.register_blueprint(file_upload_bp)
app.register_blueprint(preparation_bp)
app.register_blueprint(copy_management_bp)

# 注册静态文件服务，将 generated_images 目录映射为 /api/static/generated_images
# 项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# generated_images 文件夹
GENERATED_IMAGES_DIR = os.path.join(project_root, 'generated_images')
if not os.path.exists(GENERATED_IMAGES_DIR):
    os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)

# generated_thumbnails 文件夹
GENERATED_THUMBNAILS_DIR = os.path.join(project_root, 'generated_thumbnails')
if not os.path.exists(GENERATED_THUMBNAILS_DIR):
    os.makedirs(GENERATED_THUMBNAILS_DIR, exist_ok=True)

# 编辑原图与编辑缩略图目录
EDIT_IMAGES_DIR = os.path.join(project_root, 'edit_folders')
if not os.path.exists(EDIT_IMAGES_DIR):
    os.makedirs(EDIT_IMAGES_DIR, exist_ok=True)

EDIT_THUMBNAILS_DIR = os.path.join(project_root, 'edit_thumbnails')
if not os.path.exists(EDIT_THUMBNAILS_DIR):
    os.makedirs(EDIT_THUMBNAILS_DIR, exist_ok=True)

# 回收站目录
RECYCLE_BIN_DIR = os.path.join(project_root, '回收站')
if not os.path.exists(RECYCLE_BIN_DIR):
    os.makedirs(RECYCLE_BIN_DIR, exist_ok=True)

# 素材目录
MATERIAL_DIR = os.path.join(project_root, '素材')
if not os.path.exists(MATERIAL_DIR):
    os.makedirs(MATERIAL_DIR, exist_ok=True)

# 素材缩略图目录
MATERIAL_THUMBNAIL_DIR = os.path.join(project_root, '素材缩略图')
if not os.path.exists(MATERIAL_THUMBNAIL_DIR):
    os.makedirs(MATERIAL_THUMBNAIL_DIR, exist_ok=True)

# 预备成品图片目录
PREPARATION_DIR = os.path.join(project_root, '预备')
if not os.path.exists(PREPARATION_DIR):
    os.makedirs(PREPARATION_DIR, exist_ok=True)


@app.route('/api/static/generated_images/<path:filename>')
def serve_generated_image(filename):
    """
    提供生成的图片静态文件服务

    功能描述：
        将本地 generated_images 目录中的图片文件提供给前端访问

    参数：
        filename: 图片文件名

    返回：
        图片文件内容
    """
    return send_from_directory(GENERATED_IMAGES_DIR, filename)


@app.route('/api/static/generated_thumbnails/<path:filename>')
def serve_generated_thumbnail(filename):
    """
    提供缩略图静态文件服务

    功能描述：
        将本地 generated_thumbnails 目录中的缩略图文件提供给前端访问

    参数：
        filename: 缩略图文件名

    返回：
        缩略图文件内容
    """
    return send_from_directory(GENERATED_THUMBNAILS_DIR, filename)


@app.route('/api/static/edit_images/<path:filename>')
def serve_edit_image(filename):
    """
    提供编辑原图静态文件服务

    功能描述：
        将 edit_folders 目录中的编辑结果原图提供给前端访问。
    """
    return send_from_directory(EDIT_IMAGES_DIR, filename)


@app.route('/api/static/edit_thumbnails/<path:filename>')
def serve_edit_thumbnail(filename):
    """
    提供编辑页缩略图静态文件服务

    功能描述：
        将 edit_thumbnails 目录中的编辑页缩略图提供给前端访问。
    """
    return send_from_directory(EDIT_THUMBNAILS_DIR, filename)


@app.route('/api/static/recycle/<path:filename>')
def serve_recycle_image(filename):
    """
    提供回收站图片静态文件服务

    功能描述：
        将回收站目录中的图片文件提供给前端访问。
    """
    return send_from_directory(RECYCLE_BIN_DIR, filename)


@app.route('/api/static/material/<path:filename>')
def serve_material_image(filename):
    """
    提供素材图片静态文件服务

    功能描述：
        将素材目录中的图片文件提供给前端访问。
    """
    return send_from_directory(MATERIAL_DIR, filename)


@app.route('/api/static/material_thumbnails/<path:filename>')
def serve_material_thumbnail(filename):
    """
    提供素材缩略图静态文件服务

    功能描述：
        将素材缩略图目录中的缩略图文件提供给前端访问。
    """
    return send_from_directory(MATERIAL_THUMBNAIL_DIR, filename)


@app.route('/api/static/preparation/<path:filename>')
def serve_preparation_image(filename):
    """
    提供预备成品图片静态文件服务

    功能描述：
        将预备目录中的成品图片文件提供给前端访问。
    """
    return send_from_directory(PREPARATION_DIR, filename)


@app.route('/api/edit-images/save', methods=['POST'])
def save_edit_result():
    """
    保存编辑结果到本地存储

    功能描述：
        接收编辑结果图片URL，下载并保存到 edit_folders 目录，
        自动生成缩略图到 edit_thumbnails 目录。

    请求体 JSON:
        {
            "image_url": "图片URL",
            "prompt": "编辑提示词（可选）",
            "size": "图片尺寸（可选）"
        }

    返回:
        成功: { "success": true, "url": "...", "thumbnail": "..." }
        失败: { "success": false, "error": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        image_url = data.get('image_url', '').strip()
        prompt = data.get('prompt', '').strip()
        size = data.get('size', None)

        if not image_url:
            return jsonify({'success': False, 'error': '缺少 image_url 参数'}), 400

        from services.edit_asset_service import save_edit_result_directly
        result = save_edit_result_directly(image_url, prompt, size)

        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        print(f"[SaveEditResult] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/edit-images/save-to-library', methods=['POST'])
def save_edit_to_library():
    """
    将编辑结果图片保存到素材库

    功能描述：
        两步流程：
        1. 先将图片下载到 edit_folders（如已有则跳过），并自动生成缩略图到 edit_thumbnails
        2. 再从 edit_folders 复制到 素材 目录

    请求体 JSON:
        {
            "image_url": "图片URL",
            "prompt": "编辑提示词（可选）"
        }

    返回:
        成功: { "success": true, "message": "...", "data": {...} }
        失败: { "success": false, "error": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        image_url = data.get('image_url', '').strip()
        prompt = data.get('prompt', '').strip()

        if not image_url:
            return jsonify({'success': False, 'error': '缺少 image_url 参数'}), 400

        from services.edit_asset_service import save_edit_result_directly, EDIT_FOLDERS_DIR
        from services.folder_service import sanitize_folder_name

        # Step 1: 下载到 edit_folders + 生成缩略图
        # 如果图片已经是本地 URL（/api/static/edit_images/xxx），说明已存在，跳过下载
        edit_prefix = '/api/static/edit_images/'
        if image_url.startswith(edit_prefix):
            filename = image_url.replace(edit_prefix, '', 1)
            local_path = os.path.join(EDIT_FOLDERS_DIR, filename)
            if os.path.exists(local_path):
                result = {'success': True, 'local_path': local_path, 'image_relative_path': filename}
            else:
                result = save_edit_result_directly(image_url, prompt)
        else:
            # 远程 URL，下载到 edit_folders
            result = save_edit_result_directly(image_url, prompt)

        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error', '下载到 edit_folders 失败')}), 500

        local_path = result.get('local_path', '')
        if not local_path or not os.path.exists(local_path):
            return jsonify({'success': False, 'error': '编辑图片保存到本地失败'}), 500

        # Step 2: 从 edit_folders 复制到 素材 目录
        target_dir = MATERIAL_DIR
        os.makedirs(target_dir, exist_ok=True)

        # 生成素材文件名
        safe_prompt = sanitize_folder_name(prompt or 'edited')[:20]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"edit_{safe_prompt}_{timestamp}.png"

        target_path = os.path.join(target_dir, filename)
        if os.path.exists(target_path):
            name_part, ext_part = os.path.splitext(filename)
            filename = f"{name_part}_{datetime.now().strftime('%H%M%S')}{ext_part}"
            target_path = os.path.join(target_dir, filename)

        shutil.copy2(local_path, target_path)

        # Step 3: 生成素材缩略图到 素材缩略图 目录
        from services.material_thumbnail_service import create_material_thumbnail
        thumbnail_result = create_material_thumbnail(target_path)
        if not thumbnail_result.get('success'):
            print(f"[SaveEditToLibrary] Warning: 素材缩略图生成失败: {thumbnail_result.get('error', '')}")

        return jsonify({
            'success': True,
            'message': '已保存到素材库',
            'data': {
                'edit_folders_path': local_path,
                'material_path': target_path,
                'filename': filename
            }
        }), 200

    except Exception as e:
        print(f"[SaveEditToLibrary] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500




# 前端构建目录（dist）和静态前端目录（www）
FRONTEND_DIST_DIR = os.path.join(project_root, 'frontend', 'dist')
WWW_DIR = os.path.join(project_root, 'www')

def get_static_dir():
    """
    获取静态文件目录

    功能描述：
        优先返回 www 目录（Vite 构建输出目录）
        如果不存在则返回 frontend/dist 目录（备用构建产物）

    返回：
        静态文件目录路径
    """
    if os.path.exists(WWW_DIR):
        return WWW_DIR
    return FRONTEND_DIST_DIR

@app.route('/')
def serve_www_index():
    """
    提供静态前端入口页面服务

    功能描述：
        当访问根路径时，返回构建后的前端 index.html 文件
        优先使用 www 目录，如果不存在则使用 frontend/dist 目录
        这允许直接访问静态前端页面，而不需要启动前端开发服务器
        静态前端页面中的资源请求（/assets/*）和API请求（/api/*）都通过本后端服务

    返回：
        index.html 文件内容
    """
    static_dir = get_static_dir()
    return send_from_directory(static_dir, 'index.html')


@app.route('/assets/<path:filename>')
def serve_www_assets(filename):
    """
    提供静态前端资源文件服务

    功能描述：
        将静态资源目录中的资源文件（JS、CSS等）提供给前端访问
        优先从 www/assets 目录获取，如果不存在则从 frontend/dist/assets 获取
        确保静态前端能够正常加载所需的静态资源

    参数：
        filename: 资源文件名

    返回：
        资源文件内容
    """
    static_dir = get_static_dir()
    assets_dir = os.path.join(static_dir, 'assets')
    return send_from_directory(assets_dir, filename)


@app.route('/<path:unknown_path>')
def serve_spa_fallback(unknown_path):
    """
    提供 SPA 刷新fallback服务

    功能描述：
        处理 SPA 应用中刷新页面时访问子路径的情况
        将所有未匹配的路径（除了 /api/* 和 /assets/*）重定向到 index.html
        确保刷新页面时不会返回 404，而是由前端路由处理

    参数：
        unknown_path: 未匹配的路径

    返回：
        index.html 文件内容
    """
    static_dir = get_static_dir()
    return send_from_directory(static_dir, 'index.html')


if __name__ == '__main__':
    from services.task_processor import start_task_processor
    from services.background_download_service import start_background_download_service
    start_task_processor(app, max_retries=600)
    start_background_download_service(app, max_workers=2)
    app.run(host='0.0.0.0', port=PORT, debug=True)
