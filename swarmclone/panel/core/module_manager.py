import socket
import threading
from typing import Dict, Optional
from ...request_parser import *
from .types import ModuleType, CONNECTION_TABLE
import time


class ModuleManager:
    def __init__(self):
        self.running = False
        self.connections: Dict[ModuleType, Optional[socket.socket]] = {
            mt: None for mt in ModuleType
        }
        self.lock = threading.Lock()
        self.start_event = threading.Event()

    def start_module_handler(self, module: ModuleType, sock: socket.socket):
        """启动模块处理线程"""
        def handler():
            print(f"Waiting for {module.display_name}...")
            with sock:
                conn, _ = sock.accept()
                with conn:
                    with self.lock:
                        self.connections[module] = conn
                    print(f"{module.display_name} is online.")
                    
                    self._wait_until_ready()
                    self._process_messages(module, conn)

            with self.lock:
                self.connections[module] = None

        threading.Thread(target=handler, daemon=True).start()

    def _wait_until_ready(self):
        """等待必要模块就绪"""
        required = {ModuleType.LLM, ModuleType.TTS, ModuleType.FRONTEND}
        while not all(self.connections[mt] for mt in required):
            if not self.running:
                return
            time.sleep(0.1)

    def _process_messages(self, module: ModuleType, conn: socket.socket):
        """处理模块消息"""
        while self.running:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                self._forward_messages(module, data)
            except (ConnectionResetError, TimeoutError):
                break

    def _forward_messages(self, source: ModuleType, data: bytes):
        """转发消息到目标模块"""
        for request in loads(data.decode()):
            targets = CONNECTION_TABLE[source][request["type"] == "data"]
            request_bytes = dumps([request]).encode()
            
            with self.lock:
                for target in targets:
                    if conn := self.connections.get(target):
                        try:
                            conn.sendall(request_bytes)
                        except (BrokenPipeError, OSError):
                            self.connections[target] = None