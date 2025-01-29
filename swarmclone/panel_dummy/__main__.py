import socket
<<<<<<< Updated upstream
import json
import subprocess
import time
from . import config
from ..request_parser import *
=======
import time
import webbrowser

from .core.types import ModuleType
from .core.module_manager import ModuleManager
from .frontend.service import FrontendService
from . import config
>>>>>>> Stashed changes


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

<<<<<<< Updated upstream
SUBMODULE_NAMES = ["LLM", "ASR", "TTS", "FRONTEND", "CHAT"]
PORTS = [
    config.LLM_PORT,
    config.ASR_PORT,
    config.TTS_PORT,
    config.FRONTEND_PORT, 
    config.CHAT_PORT
]
LLM = iota()
ASR = iota()
TTS = iota()
FRONTEND = iota()
CHAT = iota()
CONN_TABLE: dict[int, tuple[list[int], list[int]]] = {
#  发送方       信号接受方               数据接受方
    LLM:  ([     TTS, FRONTEND], [     TTS, FRONTEND]),
    ASR:  ([LLM, TTS, FRONTEND], [LLM,      FRONTEND]),
    TTS:  ([LLM,      FRONTEND], [          FRONTEND]),
    CHAT: ([                  ], [LLM,      FRONTEND])
} # 数据包转发表
CONNECTIONS: list[socket.socket | None] = [None for _ in range(iota.count)]

def handle_submodule(submodule: int, sock: socket.socket) -> None:
    global CONNECTIONS, running
    loader = Loader(config)
    print(f"Waiting for {SUBMODULE_NAMES[submodule]}...")
    CONNECTIONS[submodule], _ = sock.accept() # 不需要知道连接的地址所以直接丢弃
    while True: # 等待模块上线
        data = CONNECTIONS[submodule].recv(1024) # type: ignore
        if not data:
            continue
        loader.update(data.decode())
        if MODULE_READY in loader.get_requests():
            break
        time.sleep(0.1)
    print(f"{SUBMODULE_NAMES[submodule]} is online.")
    try:
        while not running: # 等待启动
            time.sleep(0.1)
        CONNECTIONS[submodule].sendall(dumps([PANEL_START]).encode("utf-8")) # type: ignore

        while running:
            # CONNECTIONS[submodule]必然不会是None
            data = CONNECTIONS[submodule].recv(1024) # type: ignore
            if not data:
                running = False
                break
            # 逐个解析请求并将其转发给相应的模块
            loader.update(data.decode())
            for request in loader.get_requests():
                print(f"{SUBMODULE_NAMES[submodule]}: {request}")
                request_bytes = dumps([request]).encode()
                for receiver in CONN_TABLE[submodule][request["type"] == "data"]:
                    if CONNECTIONS[receiver]:
                        CONNECTIONS[receiver].sendall(request_bytes) # type: ignore
    except KeyboardInterrupt:
        running = False

    # 让模块停止并退出
    if CONNECTIONS[submodule] is not None:
        CONNECTIONS[submodule].sendall(dumps([PANEL_STOP]).encode("utf-8")) # type: ignore
        CONNECTIONS[submodule].close() # type: ignore
        CONNECTIONS[submodule] = None

if __name__ == '__main__':
    running = False

    # 创建套接字并监听
    sockets: list[socket.socket] = [
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for _ in range(iota.count)
    ]
    for i, sock in enumerate(sockets):
        sock.bind((config.PANEL_HOST, PORTS[i]))
        sock.listen(1)

    # 分别启动处理各个模块的子线程
    threads: list[threading.Thread] = [
        threading.Thread(target=handle_submodule, args=t)
        for t in enumerate(sockets)
    ]
    for t in threads:
        t.start()

    # 只需要LLM、TTS和FRONTEND上线即可开始运行，ASR和CHAT不必需
    while not all([CONNECTIONS[LLM], CONNECTIONS[TTS], CONNECTIONS[FRONTEND]]):
        time.sleep(0.1) # 防止把CPU占满
    
    print("Start.")
    running = True
    for t in threads:
        t.join()

    # 所有子线程都已退出
    for s in sockets:
        s.close()
=======
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
>>>>>>> Stashed changes
