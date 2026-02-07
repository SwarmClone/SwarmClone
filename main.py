# SwarmCloneBackend
# Copyright (c) 2026 SwarmClone <github.com/SwarmClone> and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import asyncio
from quart import Request

from utils.logger import log
from core.api_server import APIServer
from core.config_manager import ConfigManager
from core.event_bus import EventBus
from core.module_manager import ModuleManager


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
    module_manager = ModuleManager(config_manager, api_server, event_bus)

    await api_server.start()
    await api_server.add_route("/", methods=["GET"], handler=root_page_handler)
    module_manager.discover_modules()

    init_success = await module_manager.initialize_all_enabled()
    if not init_success:
        log.error("模块初始化失败，程序退出")
        return

    await asyncio.sleep(1)
    await module_manager.start_all_enabled()
    await asyncio.sleep(2)

    started = module_manager.get_started_modules()
    log.info(f"服务运行中 - 已启动 {len(started)} 个模块: {', '.join(started)}")

    log.info(f"访问地址: http://127.0.0.1:{port}/")
    log.info("按 Ctrl+C 停止服务")

    try:
        await api_server.server_task
    except asyncio.CancelledError:
        pass
    finally:
        log.info("正在停止服务...")
        try:
            await asyncio.wait_for(module_manager.stop_all(), timeout=10.0)
        except asyncio.TimeoutError:
            log.warning("停止模块超时，强制继续")
        except Exception as e:
            log.error(f"停止模块出错: {e}")

        try:
            await asyncio.wait_for(api_server.stop(), timeout=5.0)
        except Exception:
            pass
        log.info("服务已停止")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass