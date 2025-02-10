import socket
import time
import queue
import threading

from ..request_parser import *
from swarmclone.config import config


MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("asr") # type: ignore

q_recv: queue.Queue[RequestType] = queue.Queue()
def recv_msg(sock: socket.socket, q: queue.Queue[RequestType], stop_module: threading.Event):
    # TODO:检查这里是否仍然适用
    loader = Loader(config)
    while True:
        data = sock.recv(1024)
        if not data:
            break
        loader.update(data.decode())
        messages = loader.get_requests()
        for message in messages:
            q.put(message)

q_send: queue.Queue[RequestType] = queue.Queue()
def send_msg(sock: socket.socket, q: queue.Queue[RequestType], stop_module: threading.Event):
    while True:
        message = q.get()
        data = dumps([message]).encode()
        sock.sendall(data)

stop = threading.Event()

if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.panel.server.port, config.asr.port))
        # 启动接收和发送线程
        t_send = threading.Thread(target=send_msg, args=(sock, q_send, stop))
        t_recv = threading.Thread(target=recv_msg, args=(sock, q_recv, stop))
        t_send.start()
        t_recv.start()

        q_send.put(MODULE_READY) # 初始化完毕
        while True: # 等待模块开始
            try:
                message = q_recv.get(False)
            except queue.Empty:
                continue
            if message == PANEL_START:
                break
            time.sleep(0.1)
        while True:
            s = input("> ")

            # 是否需要退出
            try:
                message = q_recv.get(False)
            except queue.Empty:
                pass
            else:
                if message == PANEL_STOP:
                    break
            
            # 发出激活信息和语音信息
            q_send.put(ASR_ACTIVATE)
            time.sleep(0.1)
            q_send.put({
                'from': 'asr',
                'type': 'data',
                'payload': {
                    'user': 'Developer A',
                    'content': s
                }
            })
    stop.set() # 通知线程退出
    t_send.join()
    t_recv.join()
