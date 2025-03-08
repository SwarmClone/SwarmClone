import time
import socket
import threading
from json import JSONDecodeError
from loguru import logger as log
from typing import Dict, Optional, Set

# 导入请求解析相关函数
from .types import ModuleType, CONNECTION_TABLE
from request_parser import loads, dumps, PANEL_START

class ModuleManager:
    def __init__(self):
        self.running = False
        self.connections: Dict[ModuleType, Optional[socket.socket]] = {
            mt: None for mt in ModuleType
        }
        self.lock = threading.Lock()
        self.start_event = threading.Event()
        self.last_missing: Set[ModuleType] = set()

    def start_module_handler(self, module: ModuleType, sock: socket.socket):
        """启动模块处理线程"""
        def handler():
            log.debug(f"[{module.name}] Waiting for connection...")
            with sock:
                try:
                    conn, addr = sock.accept()
                    log.debug(f"[{module.name}] New connection from {addr}")
                    with conn:
                        with self.lock:
                            self.connections[module] = conn
                        log.success(f"[{module.name}] Connection established")
                        
                        with self.lock:
                            self.last_missing = set()
                        self._wait_until_ready()
                        self._process_messages(module, conn)

                except Exception as e:
                    log.error(f"[{module.name}] Connection error: {str(e)}")
                finally:
                    with self.lock:
                        if self.connections[module] is not None:
                            log.error(f"[{module.name}] Connection abruptly closed!")
                        self.connections[module] = None
                        self._notify_disconnection(module)

        threading.Thread(target=handler, daemon=True).start()

    def _wait_until_ready(self):
        """等待必要模块就绪"""
        required = {ModuleType.LLM, ModuleType.TTS, ModuleType.FRONTEND}
        initial_print = True
        
        while self.running and not all(self.connections[mt] for mt in required):
            with self.lock:
                missing = {mt for mt in required if not self.connections[mt]}
                
                if missing != self.last_missing:
                    missing_names = [mt.name for mt in missing]
                    status = "Initializing" if initial_print else "Module disconnected"
                    log_level = log.info if initial_print else log.error
                    log_level(f"[System] {status}, waiting for: {', '.join(missing_names)}")
                    self.last_missing = missing
                    initial_print = False
            
            time.sleep(0.5)

    def _notify_disconnection(self, module: ModuleType):
        """处理模块断开通知"""
        log.error(f"[System] Critical: {module.name} module disconnected!")
        with self.lock:
            self.last_missing = set()

    def _process_messages(self, module: ModuleType, conn: socket.socket):
        """处理模块消息"""
        log.debug(f"[{module.name}] Start processing messages")
        while self.running:
            try:
                data = conn.recv(1024)
                if not data:
                    log.error(f"[{module.name}] Connection closed by peer")
                    break
                
                log.debug(f"[{module.name}] Received {len(data)} bytes")
                self._forward_messages(module, data)
                
            except (ConnectionResetError, TimeoutError) as e:
                log.error(f"[{module.name}] Connection error: {str(e)}")
                break
            except Exception as e:
                log.exception(f"[{module.name}] Unexpected error:")
                break
                    
    def _forward_messages(self, source: ModuleType, data: bytes):
        """转发消息到目标模块"""
        try:
            requests = loads(data.decode('utf-8'))
            log.debug(f"[{source.name}] Decoded {len(requests)} request(s)")
        except JSONDecodeError as e:
            log.error(f"[{source.name}] JSON decode error: {str(e)}")
            return
        except Exception as e:
            log.error(f"[{source.name}] Message parsing failed: {str(e)}")
            return

        for idx, request in enumerate(requests):
            try:
                # 信号消息处理
                if request.get("type") == "signal":
                    payload = request.get("payload")
                    module_from = request.get("from", "").upper() # type: ignore
                    
                    if payload == "module.exit":
                        log.info(f"[{module_from}] Module exited normally")
                        self._handle_module_exit(module_from)
                        continue
                        
                    if payload == "module.crash":
                        log.error(f"[{module_from}] Module encountered critical error!")
                        self._handle_module_exit(module_from)
                        continue

                    # 处理MODULE_READY信号
                    if payload == "ready":
                        log.info(f"[{module_from}] Module is ready. Sending PANEL_START.")
                        try:
                            target_module = ModuleType[module_from]
                            with self.lock:
                                conn = self.connections.get(target_module)
                                if conn:
                                    start_signal = PANEL_START
                                    data_to_send = dumps([start_signal]).encode()
                                    conn.sendall(data_to_send)
                                    log.debug(f"[Panel] Sent PANEL_START to {target_module.name}")
                                else:
                                    log.error(f"[Panel] No connection for {target_module.name}")
                        except KeyError:
                            log.error(f"[Panel] Invalid module name: {module_from}")
                        continue

                # 正常消息转发流程
                req_type = request.get("type", "unknown")
                targets = CONNECTION_TABLE[source][req_type == "data"]
                
                log.debug(
                    f"[{source.name}] Request #{idx+1} "
                    f"(type={req_type}) -> {[t.name for t in targets]}"
                )

                request_bytes = dumps([request]).encode('utf-8')
                self._send_to_targets(source, request_bytes, targets)

            except KeyError as e:
                log.error(f"[{source.name}] Invalid request type: {str(e)}")
            except Exception as e:
                log.exception(f"[{source.name}] Request processing error:")

    def _handle_module_exit(self, module_name: str):
        """处理模块退出事件"""
        try:
            module = ModuleType[module_name]
            with self.lock:
                if conn := self.connections.get(module):
                    conn.close()
                    self.connections[module] = None
                    log.debug(f"[{module.name}] Connection cleaned up")
                self._notify_disconnection(module)
        except KeyError:
            log.error(f"Invalid module name: {module_name}")

            
    def _send_to_targets(self, source: ModuleType, data: bytes, targets: list):
        """发送数据到指定目标"""
        with self.lock:
            for target in targets:
                if conn := self.connections.get(target):
                    try:
                        sent = conn.send(data)
                        log.debug(
                            f"[{source.name}] Sent {sent} bytes to {target.name} "
                            f"(Total {len(data)} bytes)"
                        )
                    except (BrokenPipeError, OSError) as e:
                        log.error(f"[{target.name}] Send failed: {str(e)}")
                        self.connections[target] = None
                else:
                    log.warning(f"[{source.name}] Target {target.name} not connected")