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
from typing import List, Callable, Dict, Any

from quart import Quart, request, jsonify, Response
from hypercorn.config import Config
from hypercorn.asyncio import serve

from utils.logger import log


class APIServer:
    def __init__(self, port: int, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.app = Quart(__name__)
        self.routes: Dict[str, Dict[str, Any]] = {}
        self.routes_lock = asyncio.Lock()
        self.server_task: asyncio.Task | None = None

        # 设置一个通用的dispatcher
        @self.app.route('/', defaults={'path': ''}, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        @self.app.route('/<path:path>', methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        async def dispatcher(path: str):
            full_path = '/' + path if path else '/'

            async with self.routes_lock:
                route_info = self.routes.get(full_path)

            if route_info:
                handler = route_info['handler']
                try:
                    # 检测并支持异步/同步回调
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(request)
                    else:
                        result = handler(request)

                    # 处理不同类型的返回值
                    if isinstance(result, str):
                        return Response(result, mimetype='text/html')
                    elif isinstance(result, tuple):
                        return jsonify(result[0]), result[1]
                    else:
                        return jsonify(result)
                except Exception as e:
                    log.error(f"Error handling request {full_path}: {e}")
                    return jsonify({"error": str(e)}), 500

            return jsonify({"error": "not found", "path": full_path}), 404

    async def start(self) -> bool:
        """异步启动服务器"""
        if self.server_task and not self.server_task.done():
            return True

        config = Config()
        config.bind = [f"{self.host}:{self.port}"]

        self.server_task = asyncio.create_task(
            serve(self.app, config),
            name=f"APIServer-{self.host}:{self.port}"
        )

        log.info(f"API服务器启动在 {self.host}:{self.port}")
        return True

    async def stop(self) -> None:
        """停止服务"""
        if self.server_task:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
            self.server_task = None
            log.info("API服务器已停止")

    async def add_route(self, path: str, methods: List[str], handler: Callable) -> Dict[str, Any]:
        """
        添加动态路由
        """
        if methods is None:
            methods = ['GET']

        async with self.routes_lock:
            self.routes[path] = {
                'handler': handler,
                'methods': methods
            }

        log.debug(f"添加路由: {path}, 方法: {methods}")
        return {'status': 'ok', 'action': 'added', 'path': path}

    async def remove_route(self, path: str) -> Dict[str, Any]:
        """
        移除动态路由
        """
        async with self.routes_lock:
            removed = self.routes.pop(path, None) is not None

        log.debug(f"移除路由: {path}, 存在: {removed}")
        return {
            'status': 'ok',
            'action': 'removed',
            'path': path,
            'existed': removed
        }