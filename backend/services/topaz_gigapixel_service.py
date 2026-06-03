# Topaz Gigapixel AI subprocess 封装服务
#
# 功能描述：
#     通过 subprocess 调用本机安装的 Topaz Gigapixel AI 可执行文件 (gigapixel.exe)，
#     对单张图片执行放大、降噪、锐化、压缩修复等操作。
#     移植自 ComfyUI 插件 sh570655308/ComfyUI-GigapixelAI 的 gigapixel_upscale 方法，
#     剥离了 ComfyUI 的 tensor 转换逻辑，改为纯文件路径输入输出。
#
# 实现逻辑：
#     1. check_available()：校验 exe 文件是否存在，捕获 FileNotFoundError
#     2. upscale_one()：构造 CLI 参数 -> subprocess.run(shell=True, timeout=600) -> 扫描输出目录
#     3. 所有异常向上抛 ValueError / RuntimeError，由调用方 (gigapixel_task_service) 写 tasks.fail_reason
#
# 失败处理（项目规则：失败优先）：
#     - exe 不存在 -> 抛 ValueError
#     - 输入图片不存在 -> 抛 ValueError
#     - 路径超 250 字符 -> 抛 ValueError
#     - 输出目录不可写 -> 抛 ValueError
#     - subprocess 超时 (默认 600s) -> 抛 RuntimeError
#     - 输出目录无图片文件 -> 抛 ValueError
#     - subprocess 返回非 0 (异常退出) -> 抛 RuntimeError
#
# 用户操作异常考虑：
#     - 用户配置的 exe 路径不存在/被误删：check_available 预先返回 False，前端展示红字提示
#     - 用户选择了不存在的输入图：upscale_one 抛 ValueError，UI 提示
#     - 用户输入路径含中文/空格：自动用引号包裹
#     - 用户同时提交多张图：每张图调用一次 upscale_one，由 worker 池串行处理

import os
import subprocess
import time
import shutil


# 模型名称 -> CLI 短码映射（与 ComfyUI 插件 GigapixelModelSettings.MODEL_MAPPING 保持一致）
MODEL_MAPPING = {
    'Art & CG': 'art',
    'Lines': 'lines',
    'Very Compressed': 'vc',
    'High Fidelity': 'fidelity',
    'Low Resolution': 'lowres',
    'Standard': 'std',
    'Text & Shapes': 'text',
    'Redefine': 'redefine',
    'Recover': 'recovery',
}

# 需要加 --mv 2 参数的模型（与 ComfyUI 插件 MV2_MODELS 保持一致）
MV2_MODELS = {'std', 'fidelity', 'lowres', 'recovery'}

# Topaz Gigapixel AI 默认安装路径
DEFAULT_EXE_PATH = r'C:\Program Files\Topaz Labs LLC\Topaz Gigapixel AI\gigapixel.exe'

# Windows 路径长度限制（与原 ComfyUI 插件一致）
MAX_PATH_LENGTH = 250

# 单图最大超时（秒），与原 ComfyUI 插件一致
DEFAULT_TIMEOUT = 600

# 支持的图片扩展名（与原 ComfyUI 插件一致）
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.tif', '.tiff')


class TopazGigapixelService:
    """
    Topaz Gigapixel AI subprocess 调用封装。

    移植自 ComfyUI 插件的 GigapixelAI.gigapixel_upscale 方法，
    移除了所有 ComfyUI 框架依赖（folder_paths / torch.Tensor），
    改为接收纯文件路径。
    """

    def __init__(self, exe_path, use_system_command=False, timeout=DEFAULT_TIMEOUT):
        """
        初始化 TopazGigapixelService。

        参数:
            exe_path: gigapixel.exe 的完整路径
            use_system_command: 是否使用系统命令 'gigapixel'（需要已配置 PATH）
            timeout: subprocess 超时（秒）
        """
        self.exe_path = exe_path
        self.use_system_command = use_system_command
        self.timeout = timeout

    def check_available(self):
        """
        检查 gigapixel.exe 是否可用。

        返回:
            (bool, str): (是否可用, 错误信息或版本描述)
        """
        if self.use_system_command:
            # 系统命令模式：尝试执行 gigapixel --help
            try:
                result = subprocess.run(
                    'gigapixel --help',
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                    shell=True
                )
                if result.returncode == 0 or 'Gigapixel' in (result.stdout + result.stderr):
                    return (True, 'system command available')
                return (False, f'gigapixel 命令执行失败: {result.stderr[:200]}')
            except FileNotFoundError:
                return (False, '系统命令 gigapixel 未找到，请检查 PATH 配置或改用完整 exe 路径')
            except subprocess.TimeoutExpired:
                return (False, 'gigapixel 命令检查超时')
            except Exception as e:
                return (False, f'检查失败: {str(e)[:200]}')

        # 完整路径模式：校验文件存在
        if not self.exe_path:
            return (False, 'exe 路径未配置')

        if not os.path.exists(self.exe_path):
            return (False, f'exe 文件不存在: {self.exe_path}')

        return (True, self.exe_path)

    def upscale_one(self, input_path, output_dir, scale, model_name, settings):
        """
        对单张图片执行 Topaz Gigapixel AI 放大。

        参数:
            input_path: 输入图片绝对路径
            output_dir: 输出目录绝对路径（必须为空目录或不存在，将由本方法创建）
            scale: 缩放倍率 (1-16)
            model_name: 模型名称（MODEL_MAPPING 的 key），例如 'Standard'
            settings: dict，可包含以下键：
                - enabled: bool，是否启用详细参数
                - sharpen: float，0-100
                - denoise: float，0-100
                - compression: float，0-100
                - fr: float，0-100，Fine Detail Retention
                - pre_downscaling: float，50-100，仅 Recover 模型生效

        返回:
            (settings_dict, output_paths):
                - settings_dict: 本次实际生效的参数（含 model 短码等）
                - output_paths: 输出文件绝对路径列表

        异常:
            ValueError: 校验失败（exe 不存在、路径超长、输入不存在、输出无文件等）
            RuntimeError: subprocess 执行失败（超时、非 0 返回码等）
        """
        # 1. 校验输入文件存在
        if not os.path.exists(input_path):
            raise ValueError(f'输入图片不存在: {input_path}')

        # 2. 校验路径长度（与 ComfyUI 插件一致）
        if len(input_path) > MAX_PATH_LENGTH:
            raise ValueError(f'输入路径过长 ({len(input_path)} > {MAX_PATH_LENGTH}): {input_path}')
        if len(output_dir) > MAX_PATH_LENGTH:
            raise ValueError(f'输出路径过长 ({len(output_dir)} > {MAX_PATH_LENGTH}): {output_dir}')

        # 3. 校验并创建输出目录，校验可写
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            raise ValueError(f'创建输出目录失败: {output_dir}, 错误: {e}')

        if not os.access(output_dir, os.W_OK):
            raise ValueError(f'输出目录不可写: {output_dir}')

        # 4. 校验并转换模型名称
        if model_name not in MODEL_MAPPING:
            raise ValueError(f'不支持的模型: {model_name}, 支持: {list(MODEL_MAPPING.keys())}')
        model_code = MODEL_MAPPING[model_name]

        # 5. 校验 scale
        try:
            scale_val = float(scale)
            if scale_val < 1.0 or scale_val > 16.0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError(f'scale 必须为 1.0-16.0 之间的数字, 当前: {scale}')

        # 6. 拼装命令参数
        #    使用 'gigapixel' 系统命令时需要 shell=True，
        #    使用完整路径时可以直接传 list（更安全），但为了和原 ComfyUI 插件保持一致（处理带空格路径），
        #    这里统一使用字符串 + shell=True
        if self.use_system_command:
            command_exe = 'gigapixel'
        else:
            command_exe = f'"{self.exe_path}"'

        # 用引号包裹带空格的路径
        quoted_input = f'"{input_path}"'
        quoted_output = f'"{output_dir}"'

        gigapixel_args = [command_exe]

        enabled = bool(settings.get('enabled', True))
        if enabled:
            gigapixel_args.extend(['--scale', str(scale_val)])
            gigapixel_args.extend(['-i', quoted_input])
            gigapixel_args.extend(['-o', quoted_output])

            # 仅在参数 > 0 时才添加（与 ComfyUI 插件完全一致）
            # 兜底值与 ComfyUI-GigapixelAI 节点 GigapixelUpscaleSettings 一致
            # 注意：0 = 不传该参数，使用 Topaz 内部默认
            denoise = settings.get('denoise', 1)
            if denoise and float(denoise) > 0:
                gigapixel_args.extend(['--dn', str(float(denoise))])

            sharpen = settings.get('sharpen', 1)
            if sharpen and float(sharpen) > 0:
                gigapixel_args.extend(['--sh', str(float(sharpen))])

            compression = settings.get('compression', 67)
            if compression and float(compression) > 0:
                gigapixel_args.extend(['--cm', str(float(compression))])

            fr = settings.get('fr', 50)
            if fr and float(fr) > 0:
                gigapixel_args.extend(['--fr', str(float(fr))])

            # Pre-downscaling 仅在 Recover 模型 + >= 50 时生效（与 ComfyUI 插件完全一致）
            if model_code == 'recovery':
                pds = settings.get('pre_downscaling', 75)
                try:
                    if pds is not None and float(pds) >= 50:
                        gigapixel_args.extend(['--pds', str(float(pds))])
                except (TypeError, ValueError):
                    pass
        else:
            # 关闭详细参数：只传 scale + 输入 + 输出
            gigapixel_args.extend([
                '--scale', str(scale_val),
                '-i', quoted_input,
                '-o', quoted_output
            ])

        # 添加模型参数
        gigapixel_args.extend(['--model', model_code])
        # MV2 模型添加 --mv 2
        if model_code in MV2_MODELS:
            gigapixel_args.extend(['--mv', '2'])

        # 7. 执行 subprocess
        command_str = ' '.join(gigapixel_args)
        print(f'[TopazGigapixel] 执行命令: {command_str}')

        try:
            # Windows 下使用系统命令或带空格的完整路径时需要 shell=True
            use_shell = self.use_system_command or ' ' in self.exe_path
            result = subprocess.run(
                command_str,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                shell=use_shell
            )
            print(f'[TopazGigapixel] stdout: {result.stdout[:500]}')
            if result.stderr:
                print(f'[TopazGigapixel] stderr: {result.stderr[:500]}')

        except subprocess.TimeoutExpired:
            raise RuntimeError(f'Gigapixel AI 处理超时 (>{self.timeout}秒), 请检查图片或增大 timeout')
        except FileNotFoundError:
            raise ValueError(f'gigapixel 命令未找到: {command_exe}')
        except Exception as e:
            raise RuntimeError(f'执行 gigapixel 失败: {str(e)[:300]}')

        # 8. 校验输出：必须至少有一个图片文件
        try:
            output_files = [
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f.lower().endswith(IMAGE_EXTENSIONS)
            ]
        except Exception as e:
            raise ValueError(f'读取输出目录失败: {output_dir}, 错误: {e}')

        if not output_files:
            raise ValueError(f'Gigapixel AI 没有生成输出文件, 输出目录: {output_dir}')

        # 9. 构造返回的 settings dict
        returned_settings = {
            'scale': scale_val,
            'model': model_code,
            'model_name': model_name,
            'denoise': float(denoise) if enabled and denoise and float(denoise) > 0 else None,
            'sharpen': float(sharpen) if enabled and sharpen and float(sharpen) > 0 else None,
            'compression': float(compression) if enabled and compression and float(compression) > 0 else None,
            'fr': float(fr) if enabled and fr and float(fr) > 0 else None,
            'pre_downscaling': (
                float(settings.get('pre_downscaling', 75))
                if enabled and model_code == 'recovery'
                   and settings.get('pre_downscaling') is not None
                   and float(settings.get('pre_downscaling', 75)) >= 50
                else None
            ),
            'mv': 2 if model_code in MV2_MODELS else None,
            'enabled': enabled,
        }

        return (returned_settings, output_files)

    def clean_temp_dir(self, temp_dir):
        """
        清理临时目录（任务完成后调用）。

        与 ComfyUI 插件的 no_temp=True 行为对齐，但延迟到任务完成 + 复制完成之后。
        """
        if not temp_dir:
            return
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            print(f'[TopazGigapixel] 清理临时目录失败: {temp_dir}, 错误: {e}')
