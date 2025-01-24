import socket
import threading
import json
from typing import Optional
from queue import Queue, Empty
from time import time, sleep
from . import config
from ..request_parser import loads, dumps, PANEL_START, MODULE_READY

def is_panel_ready(sock: socket.socket):
    msg = sock.recv(1024)
    return loads(msg.decode())[0] == PANEL_START

def get_data(sock: socket.socket, q_llm: Queue[Optional[str]], q_asr: Queue[Optional[str]]):
    while True:
        msg = sock.recv(1024)
        if not msg:
            break
        try:
            data = json.loads(msg.decode())
        except:
            continue
        if data["from"] == "stop":
            break
        if data["from"] == "LLM":
            q_llm.put(data["token"])
        if data["from"] == "ASR":
            q_asr.put(f"{data['name']}: {data['text']}")
    q_llm.put(None)

face_template = """
 ___
({eye}{mouth}{eye})
"""

eyes = "O-"
mouths = "wo"

if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((config.PANEL_HOST, config.FRONTEND_PORT))
        
        print(" * Frontend 初始化完成，等待面板准备就绪。")
        s.sendall(dumps([MODULE_READY]).encode())
        while not is_panel_ready(s):
            sleep(0.5)
        print(" * 就绪。")

        q_llm: Queue[Optional[str]] = Queue()
        q_asr: Queue[Optional[str]] = Queue()
        t = threading.Thread(target=get_data, args=(s, q_llm, q_asr))
        t.start()
        model_s: str = ""
        asr_res: Optional[str] = ""
        do_clear = False
        do_refresh = False
        eye_closed = False
        word_count = 0
        t0 = time()
        while True:
            try:
                token = q_llm.get(False)
            except Empty:
                pass
            else:
                if token is None:
                    break
                word_count += 1
                if do_clear:
                    model_s = ""
                    do_clear = False
                if token == "<eos>":
                    do_clear = True
                    word_count = 0
                else:
                    model_s += token
                do_refresh = True

            try:
                asr_res = q_asr.get(False)
            except Empty:
                pass
            else:
                do_refresh = True
            
            t1 = time()
            if eye_closed and t1 - t0 > 0.2:
                eye_closed = False
                t0 = t1
                do_refresh = True
            elif not eye_closed and t1 - t0 > 2:
                eye_closed = True
                t0 = t1
                do_refresh = True

            if do_refresh:
                print("\033[H\033[J")
                eye = eyes[eye_closed]
                mouth = mouths[word_count % 10 > 6]
                face = face_template.format(eye=eye, mouth=mouth)
                print(face)
                print(asr_res)
                print(f"Qwen2.5-0.5b-Instruct: {model_s}")
                do_refresh = False
        