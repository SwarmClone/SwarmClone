import asyncio
import signal
import sys
import time
from sys import exc_info

from core.api_server import APIServer
from flask import Request

from core.config_manager import ConfigManager
from core.event_bus import EventBus
from core.module_manager import ModuleManager
from utils.logger import log


def root_page_handler(request: Request):

    host = request.host

    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SwarmClone Backend</title>
        <link rel="icon" href="#" type="image/x-icon">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #f0f2f5;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: #ffffff;
                padding: 3rem 4rem;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                text-align: center;
            }
            h1 { font-size: 2.5rem; margin-bottom: 0.5rem; color: #000; }
            .subtitle { color: #666; margin-bottom: 2rem; }
            .status {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background: #000;
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                margin-bottom: 2rem;
                font-size: 0.9rem;
            }
            .status::before {
                content: "";
                width: 8px;
                height: 8px;
                background: #08d983;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.4; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status">Running</div>
            <h1>SwarmClone</h1>
            <p class="subtitle">Backend is running on """ + host + """</p>
            <p style="color: #999; font-size: 0.9rem;">It's time to start!</p>
        </div>
    </body>
    </html>
    """
    return html_content


async def main():
    port = 4927

    api_server = APIServer(port=port)
    config_manager = ConfigManager()
    event_bus = EventBus()

    api_server.start()
    api_server.add_route("/", methods=["GET"], handler=root_page_handler)

    module_manager = ModuleManager(config_manager, api_server, event_bus)
    module_manager.discover_modules()

    shutdown_event = asyncio.Event()
    def signal_handler(signum, frame):
        log.info(f"收到信号 {signum}，开始停止服务...")
        api_server.stop()
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        init_success = await module_manager.initialize_all_enabled()
        if not init_success:
            log.error("初始化模块过程中出现问题，无法将继续执行代码，请检查配置文件或联系开发者")
            return

        initialized = module_manager.get_initialized_modules()
        log.info(f"已初始化 {len(initialized)} 个模块: {', '.join(initialized)}")

        # 等待事件总线准备
        await asyncio.sleep(1)

        await module_manager.start_all_enabled()

        # 等待模块完全启动
        await asyncio.sleep(2)

        started = module_manager.get_started_modules()
        log.info(f"已启动 {len(started)} 个模块: {started}")

        log.info(f"Server running at http://127.0.0.1:{port}/")
        log.info("Press Ctrl+C to stop...")

        # 主循环
        while not shutdown_event.is_set():
            await asyncio.sleep(1)

    except Exception as e:
        log.error(f"Error: {e}", exc_info=True)
    finally:
        await module_manager.stop_all()
        api_server.stop()
        log.info("All server stopped")


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())