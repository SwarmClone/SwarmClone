import socket
import threading
import queue
from time import time, sleep

from ..request_parser import *
from ..config import config

MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("frontend") # type: ignore

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


if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.panel.server.host, config.unity_frontend.port))
        stop_module = threading.Event()
        t_recv = threading.Thread(target=recv_msg, args=(sock, q_recv, stop_module))
        t_recv.start()
        t_send = threading.Thread(target=send_msg, args=(sock, q_send, stop_module))
        t_send.start()

        q_send.put(MODULE_READY) # 就绪

        while True: # 等待开始
            try:
                message: RequestType | None = q_recv.get(False)
                if message == PANEL_START:
                    break
            except queue.Empty:
                sleep(0.1)

        t0 = time()
        target = .0
        q_sentences: queue.Queue[str | None] = queue.Queue()
        tokens: dict[str, tuple[float, str] | None] = {}
        sentence_finished = True
        current_sentence: str | None = None
        clear_screen = False
        user_str = ''
        ai_str = ''
        while True:
            message = None
            try:
                message = q_recv.get(False)
                print(message)
            except queue.Empty:
                sleep(1 / 60)
            
            print("\033[H\033[J", end="")
            print(f"User: {user_str}\nAI: {ai_str}")
            
            match message:
                case x if x == PANEL_STOP:
                    stop_module.set()
                    break
                case x if x == ASR_ACTIVATE:
                    print("ASR activated")
                    while not q_sentences.empty(): q_sentences.get()
                    tokens.clear()
                    clear_screen = True
                    current_sentence = None
                    sentence_finished = True
                    target = .0
                case {'from': 'asr', 'type': 'data', 'payload': {'user': user, 'content': content}}:
                    user_str = f"{content}"
                case {'from': 'tts', 'type': 'data', 'payload': {'id': sid, 'token': token, 'duration': duration}}:
                    if tokens[sid] is None: # type: ignore
                        tokens[sid] = [] # type: ignore
                    tokens[sid].append((duration, token)) # type: ignore
                case {'from': 'llm', 'type': 'data', 'payload': {'content': content, 'id': sid}}:
                    q_sentences.put(sid) # type: ignore
                    tokens[sid] = None # type: ignore
                case x if x == LLM_EOS:
                    q_sentences.put(None)

            if sentence_finished and not q_sentences.empty():
                sentence_finished = False
                current_sentence = q_sentences.get()
                print(current_sentence)
                if current_sentence is None:
                    sentence_finished = True
                    clear_screen = True
                    continue
                elif clear_screen:
                    clear_screen = False
                    ai_str = ''

            if not sentence_finished and current_sentence and time() - t0 > target:
                if current_sentence not in tokens:
                    continue
                if tokens[current_sentence] == []:
                    sentence_finished = True
                    del tokens[current_sentence]
                    continue
                if tokens[current_sentence] is None:
                    continue
                (duration, token), *tokens[current_sentence] = tokens[current_sentence] # type: ignore
                print(f"Token: {token}, Duration: {duration}")
                ai_str += token # type: ignore
                target = duration # type: ignore
                t0 = time()
        
        t_recv.join()
        t_send.join()
