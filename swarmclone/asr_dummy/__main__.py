import socket
import time
from . import config
from ..request_parser import *

def is_panel_ready(sock: socket.socket):
    msg = sock.recv(1024)
    return loads(msg.decode())[0] == PANEL_START

if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.PANEL_HOST, config.ASR_PORT))
        print(" * ASR Dummy 初始化完成，等待面板准备就绪。")
        sock.sendall(dumps([MODULE_READY]).encode())
        while not is_panel_ready(sock):
            time.sleep(0.5)
        print(" * 就绪。")
        while True:
            s = input("> ")
            sock.sendall(dumps([ASR_ACTIVATE]).encode('utf-8'))
            time.sleep(0.1)
            sock.sendall(dumps([{
                'from': 'asr',
                'type': 'data',
                'payload': {
                    'user': 'Developer A',
                    'content': s
                }   
            }]).encode('utf-8'))
