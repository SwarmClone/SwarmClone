import threading
import socket
import json
import subprocess
from . import config
from ..request_parser import loads, dumps

class Iota:
    """枚举整数"""
    def __init__(self):
        self.count = 0
    
    def __call__(self) -> int:
        self.count += 1
        return self.count - 1

iota = Iota()

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
    TTS:  ([LLM,      FRONTEND], [LLM,      FRONTEND]),
    CHAT: ([                  ], [LLM,      FRONTEND])
} # 数据包转发表
CONNECTIONS: list[socket.socket | None] = [None for _ in range(iota.count)]

def handle_submodule(submodule: int, sock: socket.socket) -> None:
    global CONNECTIONS, running
    print(f"Waiting for {SUBMODULE_NAMES[submodule]}...")
    CONNECTIONS[submodule], _ = sock.accept() # 不需要知道连接的地址所以直接丢弃
    print(f"{SUBMODULE_NAMES[submodule]} is online.")
    while not running:...

    while running:
        # CONNECTIONS[submodule]必然不会是None
        data = CONNECTIONS[submodule].recv(1024) # type: ignore
        if not data:
            running = False
            break
        # 逐个解析请求并将其转发给相应的模块
        for request in loads(data.decode()):
            print(f" * [PANEL] Received From {SUBMODULE_NAMES[submodule]}: {request}")
            request_bytes = dumps([request]).encode()
            for receiver in CONN_TABLE[submodule][request["type"] == "data"]:
                if CONNECTIONS[receiver]:
                    CONNECTIONS[receiver].sendall(request_bytes) # type: ignore

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
    while not all([CONNECTIONS[LLM], CONNECTIONS[TTS], CONNECTIONS[FRONTEND]]):...
    
    running = True
    for t in threads:
        t.join()

    # 所有子线程都已退出
    for s in sockets:
        s.close()
