import socket
import threading
import multiprocessing as mp
from typing import List, Callable, Dict, Any
from flask import Flask, request, jsonify, Response
from werkzeug.serving import make_server

from utils.logger import log


def _command_listener(conn, routes_dict: Dict, routes_lock: threading.Lock, stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            if conn.poll(0.5):
                cmd = conn.recv()
                action = cmd.get('cmd')

                if action == 'add':
                    with routes_lock:
                        routes_dict[cmd['path']] = {
                            'handler': cmd['handler'],
                            'methods': cmd.get('methods', ['GET'])
                        }
                    conn.send({'status': 'ok', 'action': 'added', 'path': cmd['path']})

                elif action == 'remove':
                    with routes_lock:
                        removed = routes_dict.pop(cmd['path'], None) is not None
                    conn.send({
                        'status': 'ok',
                        'action': 'removed',
                        'path': cmd['path'],
                        'existed': removed
                    })

                elif action == 'stop':
                    conn.send({'status': 'ok', 'action': 'stopping'})
                    stop_event.set()
                    break

        except (EOFError, ConnectionError):
            break
        except Exception as e:
            try:
                conn.send({'status': 'error', 'msg': str(e)})
            except:
                pass


def _flask_app_worker(conn: mp.Pipe, port: int):
    app = Flask(__name__)
    routes_lock = threading.Lock()
    stop_event = threading.Event()
    dynamic_routes: Dict[str, Dict[str, Any]] = {}

    @app.route('/', defaults={'path': ''}, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    @app.route('/<path:path>', methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    def dispatcher(path):
        full_path = '/' + path if path else '/'

        with routes_lock:
            route_info = dynamic_routes.get(full_path)

        if route_info:
            handler = route_info['handler']
            try:
                result = handler(request)
                if isinstance(result, str):
                    return Response(result, mimetype='text/html')
                elif isinstance(result, tuple):
                    return jsonify(result[0]), result[1]
                else:
                    return jsonify(result)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        return jsonify({"error": "not found", "path": full_path}), 404

    listener_thread = threading.Thread(
        target=_command_listener,
        args=(conn, dynamic_routes, routes_lock, stop_event),
        daemon=True  # 设为守护线程，避免阻碍主程序退出
    )
    listener_thread.start()

    server = make_server('127.0.0.1', port, app, threaded=True)

    server.timeout = 0.5

    conn.send({'status': 'ready', 'port': port})

    # 循环处理请求，直到收到停止信号
    while not stop_event.is_set():
        try:
            server.handle_request()
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt received, shutting down server...")
            break
        except Exception:
            break  # 出错时直接退出循环

    server.shutdown()
    listener_thread.join(timeout=2)
    conn.close()


class APIServer:
    def __init__(self, port: int, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.parent_conn, self.child_conn = mp.Pipe(duplex=True)
        self.process: mp.Process = None

    def start(self):
        if self.process and self.process.is_alive():
            return True

        self.process = mp.Process(
            target=_flask_app_worker,
            args=(self.child_conn, self.port),
            name=f"APIServer-{self.port}"
        )
        self.process.start()

        if self.parent_conn.poll(5):
            msg = self.parent_conn.recv()
            if isinstance(msg, dict) and msg.get('status') == 'ready':
                return True

        self.process.terminate()
        raise RuntimeError("Server failed to start within 5 seconds")

    def add_route(self, path: str, methods: List[str], handler: Callable) -> Dict[str, Any]:
        """
        添加一个动态路由
        :param path:  路由路径，用于指定URL的路径部分
        :param methods:  支持的HTTP方法列表，如GET、POST等
        :param handler:  处理请求的回调函数，当请求匹配该路由时被调用
        :return:  如果成功添加路由，返回服务器处理结果；如果超时则抛出异常
        """
        if not self.process or not self.process.is_alive():
            raise RuntimeError("Server not started")

        self.parent_conn.send({
            'cmd': 'add',
            'path': path,
            'handler': handler,
            'methods': methods if methods else ['GET']  # 如果未指定HTTP方法，默认使用GET
        })

        if self.parent_conn.poll(5):
            return self.parent_conn.recv()
        raise TimeoutError("Add route timeout")

    def remove_route(self, path: str) -> Dict[str, Any]:
        """
        移除一个动态路由，一并解绑该动态路由路径下绑定的回调函数
        :param path: 要移除的路由路径
        :return:  返回操作结果，包含状态和消息
        """
        if not self.process or not self.process.is_alive():
            return {'status': 'error', 'msg': 'server not running'}

        self.parent_conn.send({'cmd': 'remove', 'path': path})

        if self.parent_conn.poll(3):
            return self.parent_conn.recv()
        raise TimeoutError("Remove route timeout")

    def stop(self):
        if not self.process or not self.process.is_alive():
            return

        try:
            self.parent_conn.send({'cmd': 'stop'})

            if self.parent_conn.poll(timeout=1):
                try:
                    self.parent_conn.recv()
                except EOFError:
                    pass
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect((self.host, self.port))
                s.close()
            except:
                pass  # 服务器可能已关闭，忽略错误

            self.process.join(timeout=2)

            if self.process.is_alive():
                self.process.terminate()
                self.process.join()

        finally:
            self.parent_conn.close()
            self.child_conn.close()
            self.process = None
            log.info("Flask server stopped")
