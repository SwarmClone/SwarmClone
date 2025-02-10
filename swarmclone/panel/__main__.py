import socket
import time
import webbrowser
from loguru import logger as log

from swarmclone.config import config
from .core.types import ModuleType
from .core.module_manager import ModuleManager
from .frontend.service import FrontendService


def get_available_port(host, default_port, module_name):
    """获取可用端口"""
    while True:
        try:
            # 先测试端口是否可用
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_sock.bind((host, default_port))
            test_sock.close()
            return default_port
        except OSError as e:
            # TODO：测试能否起效
            if e.errno == 98:  # 端口被占用
                log.error(f"[{module_name}] Port {default_port} is already in use")
                new_port = input(
                    f"Please enter a new port for {module_name} (current: {default_port}), "
                    "or press Q to quit: "
                ).strip()
                
                if new_port.lower() == "q":
                    log.error("Exiting due to port conflict")
                    raise SystemExit(1)
                
                if not new_port:
                    continue  # 输入为空则重试
                
                try:
                    default_port = int(new_port)
                    if not (1 <= default_port <= 65535):
                        log.error("Port must be between 1-65535")
                        continue
                except ValueError:
                    log.error("Invalid port number")
                    continue
            else:
                raise

def create_module_socket(host, module_type):
    """创建模块socket并处理端口冲突"""
    port = module_type.port
    module_name = module_type.name
    
    try:
        # 尝试使用配置端口
        return socket.create_server((host, port), family=socket.AF_INET, reuse_port=False)
    except OSError as e:
        # TODO：测试能否起效
        if e.errno == 98:  # 端口被占用
            log.warning(f"[{module_name}] Configured port {port} is unavailable")
            new_port = get_available_port(host, port, module_name)
            
            # 创建新socket使用用户指定的端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, new_port))
            sock.listen(1)
            
            log.info(f"[{module_name}] Using temporary port {new_port} (original: {port})")
            log.warning("Please update the port in config.py for permanent changes")
            return sock
        raise

def main():
    # 初始化前端服务
    frontend = FrontendService(
        host=config.panel.server.host,
        port=config.panel.frontend.port,
        static_dir="frontend/static"
    )
    started_event = frontend.start()

    # 初始化模块管理器
    manager = ModuleManager()
    
    # 创建套接字监听并处理端口冲突
    sockets = {}
    for mt in ModuleType:
        try:
            sockets[mt] = create_module_socket(config.panel.server.host, mt)
            manager.start_module_handler(mt, sockets[mt])
        except Exception as e:
            log.critical(f"[{mt.name}] Failed to initialize: {str(e)}")
            raise SystemExit(1)

    # 等待前端启动后打开浏览器
    started_event.wait()
    webbrowser.open(f'http://{config.panel.server.host}:{config.panel.frontend.port}/pages/index.html')

    try:
        manager.running = True
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.running = False
        frontend.stop()
        log.success("System shutdown gracefully")

if __name__ == "__main__":
    main()