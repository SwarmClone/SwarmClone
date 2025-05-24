import socket
import threading

from time import sleep
from queue import Queue
from typing import List

from ..request_parser import *
from ..config import config

MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("tts") # type: ignore

def is_panel_ready(sock: socket.socket):
    msg = sock.recv(1024)
    return loads(msg.decode())[0] == PANEL_START

# 生成队列
q: Queue[List[str]] = Queue()

def get_data(sock: socket.socket):
    global q
    global q_fname
    s = ""
    while True:
        msg = sock.recv(1024)
        if not msg:
            break
        try:
            data :RequestType = loads(msg.decode())[0]
        except Exception as e:
            print(e)
            continue
        match data:
            case x if x == PANEL_STOP:
                break
            case {"from": "llm", "type": "data", "payload": {"content": tokens, "id": sentence_id}}:
                q.put([sentence_id, tokens])    # type: ignore
                continue
            case {'from': 'llm', 'type': 'signal', 'payload': 'eos'}:
                q.put(["<eos>", "<eos>"])
                continue
            case x if x == ASR_ACTIVATE:
                while not q.empty():
                    q.get()
    q.put(["<eos>", "<eos>"])

            
if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.panel.server.host, config.tts.port))
        print(" * TTS Dummy 初始化完成，等待面板准备就绪。")
        sock.sendall(dumps([MODULE_READY]).encode())
        while not is_panel_ready(sock):
            sleep(0.5)
        print(" * 就绪。")
        
        get_data_thread = threading.Thread(target=get_data, args=(sock, ))
        get_data_thread.start()
        
        while True:
            if not q.empty():
                sentence_id, s = q.get()
                if s is None:
                    break
                if not s or s.isspace():
                    continue
                if sentence_id == "<eos>":
                    print(" * Send TTS finish signal。")
                    sock.sendall(
                        dumps([{"from": "tts", 
                                "type": "signal", 
                                "payload": "finish"}]
                                ).encode())
                    continue
                print(f" * getText：{s}, id：{sentence_id}")
                sock.sendall(
                    dumps([{"from": "tts", 
                            "type": "data", 
                            "payload": {"id": sentence_id, 
                                        "token": s,
                                        "duration": 1.0}}]
                            ).encode())
                sleep(0.2)

        sock.close()
    