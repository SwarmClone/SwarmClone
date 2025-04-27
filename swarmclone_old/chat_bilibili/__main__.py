## TODO: 协程+多线程太不优雅了，应该有更好的实现
import socket
import threading
import queue
from time import sleep
from bilibili_api import live, sync

from ..request_parser import *
from ..config import config

MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("chat") # type: ignore

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

if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.panel.server.host, config.chat.port))
        stop_module = threading.Event()
        t_recv = threading.Thread(target=recv_msg, args=(sock, q_recv, stop_module))
        t_recv.start()
        t_send = threading.Thread(target=send_msg, args=(sock, q_send, stop_module))
        t_send.start()
        q_send.put(MODULE_READY)

        while True: # 等待开始
            try:
                message: RequestType | None = q_recv.get(False)
                if message == PANEL_START:
                    break
            except queue.Empty:
                sleep(0.1)
        room = live.LiveDanmaku(config.chat.bilibili.live_room_id)

        @room.on('DANMU_MSG')
        async def on_danmaku(event):
            # 收到弹幕
            print(f"{(user := event['data']['info'][2][1])}: {(msg := event['data']['info'][1])}")
            q_send.put({
                'from': 'chat',
                'type': 'data',
                'payload': {
                    'user': user,
                    'content': msg
                }
            })

        try:
            sync(room.connect())
        except KeyboardInterrupt:
            pass
        finally:
            stop_module.set()
            t_recv.join()
            t_send.join()
