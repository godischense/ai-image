# AI-image 图片生成应用 / AI Image Generation App

> 基于 Vue 3 + Flask 的 AI 图像生成、编辑、素材管理与文案协同一体化桌面/局域网 Web 应用。
> A Vue 3 + Flask based web app for AI image generation, editing, material management and copy collaboration.

---

## ✨ 功能特性 / Features

- 🖼️ **AI 图像生成** — 集成 OpenAI 兼容接口、fal.ai (gpt-image-2)、GPTsAPI 等多种模型
- ✏️ **AI 图像编辑** — 异步编辑、蒙版绘制、参考图上传、批量操作
- 🔍 **Topaz Gigapixel AI 图片放大** — 调用本机 Topaz Gigapixel AI（≥7.3.0，需商业授权）对图片进行无损放大、降噪、锐化、压缩修复；9 种模型可选（Art & CG / Lines / Very Compressed / High Fidelity / Low Resolution / Standard / Text & Shapes / Redefine / Recover）
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
├── 安装本地环境.bat            # 安装本地 Python 环境和前端依赖（Windows）
├── 启动.bat                    # 一键启动脚本（Windows）
├── README.md                   # 本文件
├── .gitignore                  # Git 忽略规则
└── .trae/
    └── rules/                  # 项目工作规则
```

---

## 🚀 快速开始 / Quick Start

### 前置依赖 / Prerequisites

- **Python 3.12+**（用于首次创建本地 `env/`）
- **Node.js 18+** 与 **npm 9+**
- **Windows 10/11**（项目为 Windows 优化，其他系统可能需要小调整）
- **可选：Topaz Gigapixel AI ≥ 7.3.0**（商业授权，本地安装）— 启用「图片放大」功能时需要；可在 https://www.topazlabs.com/downloads 下载

### 1. 克隆仓库 / Clone

```bash
git clone https://github.com/godischense/ai-image.git
cd ai-image
```

### 2. 安装本地嵌入式环境和依赖 / Install Local Environment

项目优先使用根目录下的本地 Python 环境 `env\python.exe`。`env/`、`frontend/node_modules/` 等目录不会提交到 GitHub，克隆后按下面步骤在本机重建。

Windows 推荐直接运行：

```bat
安装本地环境.bat
```

脚本会执行：

- 如果 `env\python.exe` 不存在，使用 `py -3.12 -m venv env` 创建本地 Python 环境
- 使用 `env\python.exe -m pip install -r backend\requirements.txt` 安装后端依赖
- 优先使用项目本地 `node-v24.15.0-win-x64\npm.cmd`，不存在时回退到系统 `npm`
- 在 `frontend/` 下执行 `npm install`

也可以手动执行：

```powershell
# 在项目根目录执行
py -3.12 -m venv env
.\env\python.exe -m pip install --upgrade pip
.\env\python.exe -m pip install -r .\backend\requirements.txt

cd frontend
npm install
```

### 3. 配置后端 / Backend Config

复制配置文件模板并填写真实配置：

```bat
cd backend
copy config\image_api.json.example config\image_api.json
copy config\fal_api.json.example config\fal_api.json
copy config\gptsapi_api.json.example config\gptsapi_api.json
copy config\apiyi_api.json.example config\apiyi_api.json
copy config\file_upload.json.example config\file_upload.json
copy config\server.json.example config\server.json
```

真实配置文件包含 API Key，不要提交到 Git。

### 4. 启动 / Start

生产模式：

```bat
启动.bat
```

`启动.bat` 会使用 `env\python.exe` 启动后端，并打开 `http://localhost:5678`。如果提示缺少 `www\index.html`，先执行前端构建：

```powershell
cd frontend
npm run build
```

开发模式需要分别启动后端和前端：

```powershell
# 终端 1：后端
cd backend
..\env\python.exe app.py
```

```powershell
# 终端 2：前端
cd frontend
npm run dev
```

后端默认监听 `http://localhost:5678`。前端开发服务器默认监听 `http://localhost:3000`，API 请求自动代理到 `http://localhost:5678`。

### 5. 上传到 GitHub / Publish to GitHub

仓库已配置远程地址：

```bash
git remote -v
```

首次或后续上传：

```bash
git status
git add README.md .gitignore 安装本地环境.bat 启动.bat backend frontend ComfyUI-GigapixelAI AIbanner.svg
git commit -m "docs: add local environment setup instructions"
git push origin main
```

上传前确认 `.gitignore` 已排除以下内容：

- `env/`
- `frontend/node_modules/`
- `node-v24.15.0-win-x64/`
- `www/`
- `backend/storage/`
- `logs/`
- `generated_images/`、`generated_thumbnails/`
- `edit_folders/`、`edit_thumbnails/`
- `gigapixel_output/`、`gigapixel_sources/`、`gigapixel_temp/`
- `素材/`、`素材缩略图/`、`预备/`、`回收站/`

这些都是本地环境、运行产物、业务数据或敏感配置，不应该入仓。

### 6. 生产构建 / Production Build

```bash
cd frontend
npm run build
```

构建产物输出到 `../www/` 目录，可由后端 Flask 直接托管（访问 `http://localhost:5678`）。

---

## ⚙️ 配置说明 / Configuration

所有配置文件位于 `backend/config/` 目录，仓库**仅包含 `.example` 模板**（不含真实 API Key）。

| 文件 | 用途 |
|------|------|
| `image_api.json` | 主图像生成 API（OpenAI 兼容） |
| `fal_api.json` | fal.ai 模型配置 |
| `gptsapi_api.json` | GPTsAPI 备用接口 |
| `apiyi_api.json` | API易接口配置 |
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
