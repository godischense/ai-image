"""
读取服务器端口配置脚本

功能描述：
    从后端数据库中读取 server 配置的 port 字段，并将端口号输出到 stdout。
    供 启动.bat 调用以确定实际启动端口和浏览器跳转地址。

实现逻辑：
    1. 通过将 backend 目录加入 sys.path 复用项目内的 config_model 模块
    2. 调用 get_single_config 读取经默认值归一化后的 server 配置
    3. 将 port 字段打印到 stdout
    4. 任何异常均回退到默认端口 5678，保证 bat 调用方不会拿到空值

异常处理：
    - 数据库连接失败、配置不存在等异常：捕获后打印默认端口 5678，保证 bat 流程不中断
"""

import os
import sys
from contextlib import redirect_stdout
from io import StringIO


def main():
    # 将 backend 目录加入 Python 路径，复用项目内的数据库配置模块
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(backend_dir):
        print(5678)
        return

    sys.path.insert(0, backend_dir)
    try:
        with redirect_stdout(StringIO()):
            from models.config_model import get_single_config
            server_config = get_single_config('server') or {}
        port = server_config.get('port', 5678)
        # 兜底：端口必须是 1-65535 之间的整数
        try:
            port = int(port)
            if port < 1 or port > 65535:
                port = 5678
        except (TypeError, ValueError):
            port = 5678
        print(port)
    except Exception:
        # 任何异常都打印默认端口，避免 bat 脚本读取到空值导致流程阻塞
        print(5678)


if __name__ == '__main__':
    main()
