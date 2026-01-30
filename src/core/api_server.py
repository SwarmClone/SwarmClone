import threading
from typing import List, Callable, Dict, Any
from flask import Flask, request, jsonify, Response
from werkzeug.serving import make_server

from utils.logger import log


class APIServer:
    def __init__(self, port: int, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.app = Flask(__name__)
        self.routes: Dict[str, Dict[str, Any]] = {}
        self.routes_lock = threading.Lock()
        self.server_thread = None
        self.server = None
        self.stop_event = threading.Event()

        # 设置一个通用的dispatcher
        @self.app.route('/', defaults={'path': ''}, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        @self.app.route('/<path:path>', methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        def dispatcher(path):
            full_path = '/' + path if path else '/'

            with self.routes_lock:
                route_info = self.routes.get(full_path)

            if route_info:
                handler = route_info['handler']
                try:
                    # 调用处理器
                    result = handler(request)
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

    def start(self):
        """启动服务器"""
        if self.server_thread and self.server_thread.is_alive():
            return True

        # 创建服务器
        self.server = make_server(self.host, self.port, self.app, threaded=True)

        # 在后台线程中运行服务器
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="APIServer-Thread"
        )
        self.server_thread.start()

        log.info(f"API服务器启动在 {self.host}:{self.port}")
        return True

    def _run_server(self):
        """运行服务器的主循环"""
        log.info(f"API服务器线程启动")
        try:
            self.server.serve_forever()
        except Exception as e:
            log.error(f"API服务器错误: {e}")

    def add_route(self, path: str, methods: List[str], handler: Callable) -> Dict[str, Any]:
        """
        添加一个动态路由
        """
        if methods is None:
            methods = ['GET']

        with self.routes_lock:
            self.routes[path] = {
                'handler': handler,
                'methods': methods
            }

        log.debug(f"添加路由: {path}, 方法: {methods}")
        return {'status': 'ok', 'action': 'added', 'path': path}

    def remove_route(self, path: str) -> Dict[str, Any]:
        """
        移除一个动态路由
        """
        with self.routes_lock:
            removed = self.routes.pop(path, None) is not None

        log.debug(f"移除路由: {path}, 存在: {removed}")
        return {
            'status': 'ok',
            'action': 'removed',
            'path': path,
            'existed': removed
        }

    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            if self.server_thread:
                self.server_thread.join(timeout=2)
            log.info("API服务器已停止")