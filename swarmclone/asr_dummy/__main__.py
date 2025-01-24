import socket
import time
from . import config
from ..request_parser import *

if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.PANEL_HOST, config.ASR_PORT))
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
