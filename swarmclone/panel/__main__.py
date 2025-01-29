import socket
import time
import webbrowser

from .core.types import ModuleType
from .core.module_manager import ModuleManager
from .frontend.service import FrontendService
from . import config


def main():
    # 初始化前端服务
    frontend = FrontendService(
        host=config.PANEL_HOST,
        port=config.FRONTEND_PORT,
        static_dir="frontend/static"
    )
    started_event = frontend.start()

    # 初始化模块管理器
    manager = ModuleManager()
    
    # 创建套接字监听
    sockets = {
        mt: socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for mt in ModuleType
    }
    for mt in ModuleType:
        sockets[mt].bind((config.PANEL_HOST, mt.port))
        sockets[mt].listen(1)
        manager.start_module_handler(mt, sockets[mt])

    # 等待前端启动后打开浏览器
    started_event.wait()
    webbrowser.open(f'http://{config.PANEL_HOST}:{config.FRONTEND_PORT}/pages/index.html')

    try:
        manager.running = True
        while True:
            # 主线程保持运行
            time.sleep(1)
    except KeyboardInterrupt:
        manager.running = False
        frontend.stop()
        print("System shutdown gracefully")

if __name__ == "__main__":
    main()
