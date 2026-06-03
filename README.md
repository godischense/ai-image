# AI-image 图片生成应用 / AI Image Generation App

> 基于 Vue 3 + Flask 的 AI 图像生成、编辑、素材管理与文案协同一体化桌面/局域网 Web 应用。
> A Vue 3 + Flask based web app for AI image generation, editing, material management and copy collaboration.

---

## ✨ 功能特性 / Features

- 🖼️ **AI 图像生成** — 集成 OpenAI 兼容接口、fal.ai (gpt-image-2)、GPTsAPI 等多种模型
- ✏️ **AI 图像编辑** — 异步编辑、蒙版绘制、参考图上传、批量操作
- 📚 **图片库管理** — 文件夹分类、标签、批量编辑、回收站
- 🎨 **素材库** — 上传/管理参考素材，自动生成缩略图
- 📝 **文案协同** — 多国家营销文案管理，AI 辅助生成与对比
- 🖼️ **预备成品** — 一键发布前的成品图片管理
- 🔧 **配置中心** — 通过 Web UI 统一管理所有 API Key、模型、提示词
- 💾 **本地存储** — 所有图片下载到本地，支持离线查看与代理访问

---

## 🛠️ 技术栈 / Tech Stack

### 前端 Frontend
- **Vue 3** (Composition API)
- **Vite 5** — 构建工具
- **Pinia** — 状态管理
- **Vue Router 4** — 路由
- **Axios** — HTTP 请求
- **SCSS** — 样式

### 后端 Backend
- **Python 3.12+**
- **Flask** — Web 框架
- **Flask-CORS** — 跨域支持
- **SQLite** — 元数据存储
- **Pillow** — 图像处理
- **Requests** — HTTP 客户端
- **fal.ai Client** — fal.ai SDK

---

## 📦 项目结构 / Project Structure

```
AI-image/
├── backend/                    # Flask 后端
│   ├── app.py                  # 入口文件
│   ├── requirements.txt        # Python 依赖
│   ├── config/                 # 配置文件（含 *.example 模板）
│   ├── models/                 # 数据模型
│   ├── routes/                 # API 路由
│   └── services/               # 业务逻辑
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── components/         # 通用组件
│   │   ├── views/              # 页面
│   │   ├── stores/             # Pinia stores
│   │   ├── services/           # API 客户端
│   │   ├── router/             # 路由配置
│   │   └── styles/             # 全局样式
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── package-lock.json
├── 启动.bat                    # 一键启动脚本（Windows）
├── README.md                   # 本文件
├── .gitignore                  # Git 忽略规则
└── .trae/
    └── rules/                  # 项目工作规则
```

---

## 🚀 快速开始 / Quick Start

### 前置依赖 / Prerequisites

- **Python 3.12+** （推荐使用 venv 或 conda）
- **Node.js 18+** 与 **npm 9+**
- **Windows 10/11**（项目为 Windows 优化，其他系统可能需要小调整）

### 1. 克隆仓库 / Clone

```bash
git clone https://github.com/godischense/ai-image.git
cd ai-image
```

### 2. 后端启动 / Backend Setup

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制配置文件模板并填写真实配置
copy config\image_api.json.example config\image_api.json
copy config\fal_api.json.example config\fal_api.json
copy config\gptsapi_api.json.example config\gptsapi_api.json
copy config\file_upload.json.example config\file_upload.json
copy config\server.json.example config\server.json

# 启动后端
python app.py
```

后端默认监听 `http://localhost:5678`。

#### 🔬 使用 Conda 创建 Python 环境 / Using Conda

如果你的系统中已安装 [Anaconda](https://www.anaconda.com/) 或 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)，推荐使用 Conda 隔离项目依赖，避免污染全局 Python。

```bash
# 1. 创建指定版本的 Conda 虚拟环境（Python 3.12，与本项目嵌入式 env 同版本）
conda create -n ai-image python=3.12 -y

# 2. 激活环境
# Windows (cmd / PowerShell)
conda activate ai-image
# Linux / macOS (bash / zsh)
conda activate ai-image

# 3. 升级 pip（conda 环境的 pip 版本可能偏旧）
python -m pip install --upgrade pip

# 4. 进入后端目录
cd backend

# 5. 安装项目依赖
pip install -r requirements.txt

# 6. 复制配置文件模板并填写真实配置
# Windows
copy config\image_api.json.example config\image_api.json
copy config\fal_api.json.example config\fal_api.json
copy config\gptsapi_api.json.example config\gptsapi_api.json
copy config\file_upload.json.example config\file_upload.json
copy config\server.json.example config\server.json
# Linux / macOS
cp config/image_api.json.example config/image_api.json
cp config/fal_api.json.example config/fal_api.json
cp config/gptsapi_api.json.example config/gptsapi_api.json
cp config/file_upload.json.example config/file_upload.json
cp config/server.json.example config/server.json

# 7. 启动后端
python app.py
```

**常用 Conda 命令速查 / Useful Conda Commands**

| 操作 | 命令 |
|------|------|
| 查看所有环境 | `conda env list` |
| 激活环境 | `conda activate ai-image` |
| 退出当前环境 | `conda deactivate` |
| 查看已安装包 | `conda list` |
| 导出环境配置 | `conda env export > environment.yml` |
| 从 yml 创建环境 | `conda env create -f environment.yml` |
| 删除环境 | `conda env remove -n ai-image` |

**遇到问题？/ Troubleshooting**

- **Q: 激活时报 `CondaError: Run 'conda init' before 'conda activate'`**
  - A: 先执行 `conda init powershell`（或 `conda init bash`），然后**重启终端**生效
- **Q: pip 安装包时很慢**
  - A: 切换国内镜像源：
    ```bash
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
    ```
- **Q: 启动后端报 `ModuleNotFoundError: No module named 'flask'`**
  - A: 确认终端前缀是 `(ai-image)`，且 `pip install -r requirements.txt` 已执行完成
- **Q: 想把 Conda 环境也提交到仓库供协作者使用**
  - A: 不推荐（环境体积大且与平台相关）。可改用 `requirements.txt` + 上述步骤重建

### 3. 前端启动 / Frontend Setup

```bash
# 新开一个终端
cd frontend

# 安装依赖
npm install

# 开发模式启动
npm run dev
```

前端开发服务器默认监听 `http://localhost:3000`，API 请求自动代理到 `http://localhost:5678`。

### 4. 生产构建 / Production Build

```bash
# 在 frontend 目录下
npm run build
```

构建产物输出到 `../www/` 目录，可由后端 Flask 直接托管（访问 `http://localhost:5678`）。

### 5. 一键启动（Windows）

直接双击项目根目录的 `启动.bat`，自动启动后端并打开浏览器。

---

## ⚙️ 配置说明 / Configuration

所有配置文件位于 `backend/config/` 目录，仓库**仅包含 `.example` 模板**（不含真实 API Key）。

| 文件 | 用途 |
|------|------|
| `image_api.json` | 主图像生成 API（OpenAI 兼容） |
| `fal_api.json` | fal.ai 模型配置 |
| `gptsapi_api.json` | GPTsAPI 备用接口 |
| `file_upload.json` | 文件上传服务配置 |
| `server.json` | 后端服务端口（默认 5678） |

> ⚠️ **重要**：配置文件首次启动时会自动从 `app_config` 数据库表读取。如果数据库为空会使用 `config_model.py` 中的默认值。**建议在 Web UI 的「设置」页面填写 API Key，会自动保存到数据库。**

### 数据库存储位置

`backend/storage/images.db`（首次运行自动创建）

---

## 🔒 安全注意事项 / Security Notes

- ❌ **不要**将包含真实 API Key 的配置文件提交到 Git
- ❌ **不要**将 `backend/storage/*.db` 数据库文件提交到 Git（含业务数据）
- ✅ 所有 `*.example` 模板都是占位符，可安全入仓
- ✅ 通过 Web UI 的「设置」页面管理 API Key，会自动加密存储在本地数据库

---

## 🐛 常见问题 / Troubleshooting

### Q1: 启动后端报 `ModuleNotFoundError`
A: 确认已激活虚拟环境并执行 `pip install -r requirements.txt`

### Q2: 前端 `npm run dev` 报 EACCES 错误
A: Windows 上以管理员身份运行 PowerShell，或检查 `node_modules` 写入权限

### Q3: 浏览器访问 `localhost:3000` 看不到后端 API
A: 确认后端 `python app.py` 已启动并监听 5678 端口。Vite 已配置 `/api` 代理

### Q4: 启动.bat 找不到 Python
A: 项目使用本地嵌入式 Python `env\python.exe`，需在项目根目录保留 `env/` 文件夹。也可修改 `启动.bat` 使用系统 Python

---

## 📄 许可证 / License

本项目仅供学习与个人使用，请勿用于商业用途。  
This project is for learning and personal use only. Please do not use it for commercial purposes.

---

## 🙏 致谢 / Acknowledgments

- [OpenAI](https://openai.com/) — GPT-image-2 API
- [fal.ai](https://fal.ai/) — fal.ai Client SDK
- [Vue.js](https://vuejs.org/) — Progressive JavaScript Framework
- [Flask](https://flask.palletsprojects.com/) — Micro Web Framework
