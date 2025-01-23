import socket
import threading
import json
import queue
import os
import re
import uuid
import time
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer, StoppingCriteria # type: ignore
from . import config, qwen2_config
from ..request_parser import *

class CustomStoppingCriteria(StoppingCriteria):
    def __init__(self, stop_event: threading.Event, eos_token_id: int):
        self.stop_event = stop_event
        self.eos_token_id = eos_token_id

    def __call__(self, input_ids, scores) -> bool: # input_ids和scores因为不想为了类型单独导入torch所以没有类型提示
        if self.stop_event.is_set(): # 在需要时可以直接停止生成
            return True
        if input_ids[0][-1] == self.eos_token_id:
            return True
        return False

def split_text(text: str, separators: list[str]) -> list[str]:
    return [part for part in re.split("|".join(separators), text) if part.strip()]

q_recv: queue.Queue[RequestType] = queue.Queue()
def recv_msg(sock: socket.socket, q: queue.Queue[RequestType], stop_module: threading.Event):
    while True:
        data = sock.recv(1024)
        if not data:
            break
        messages = loads(data.decode())
        for message in messages:
            q.put(message)

q_send: queue.Queue[RequestType] = queue.Queue()
def send_msg(sock: socket.socket, q: queue.Queue[RequestType], stop_module: threading.Event):
    while True:
        message = q.get()
        data = dumps([message]).encode()
        sock.sendall(data)

def generate(model: AutoModelForCausalLM, text_inputs: list[dict[str, str]], streamer: TextIteratorStreamer):
    try:
        text = tokenizer.apply_chat_template(text_inputs, tokenizer=False, add_generation_prompt=True)
        model_inputs = tokenizer(text, return_tensors="pt").to(model.device)
        model.generate(
            model_inputs,
            max_new_tokens=512,
            streamer=streamer,
            stopping_criteria=CustomStoppingCriteria(stop_generation, tokenizer.eos_token_id)
        )
    except Exception as e:
        print(e)
        stop_generation.set()

# 状态
STANDBY = 0
GENERATE = 1
WAIT_FOR_TTS = 2
WAIT_FOR_ASR = 3

# 事件
stop_generation = threading.Event()
stop_module = threading.Event()

if __name__ == '__main__':
    successful = False
    abs_model_path = os.path.expanduser(qwen2_config.MODEL_PATH)
    while not successful:
        try:
            model = AutoModelForCausalLM.from_pretrained(abs_model_path, torch_dtype="auto", device_map="auto")
            tokenizer = AutoTokenizer.from_pretrained(abs_model_path, padding_side="left")
        except:
            choice = input("加载模型失败，是否下载模型？(Y/n)")
            if choice.lower() != "n":
                import huggingface_hub # type: ignore
                huggingface_hub.snapshot_download(
                    repo_id=qwen2_config.MODEL_ID,
                    repo_type="model",
                    local_dir=abs_model_path,
                    endpoint="https://hf-mirror.com"
                )
    
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.PANEL_HOST, config.LLM_PORT))
        t_recv = threading.Thread(target=recv_msg, args=(sock, q_recv, stop_module))
        t_recv.start()
        t_send = threading.Thread(target=send_msg, args=(sock, q_send, stop_module))
        t_send.start()
        generation_thread: threading.Thread | None = None # 在没有生成任务前没有值

        history: list[dict[str, str]] = []
        state = STANDBY
        text = ""
        standby_time = time.time()
        while True: # 状态机
            """
            待机状态：
             - 若处于待机状态时间大于5s，切换到生成状态
             - 若收到ASR给出的语音活动信号，切换到等待ASR状态
            生成状态：
             - 生成一段回复完毕后切换到等待TTS状态
             - 若收到ASR给出的语音活动信号，切换到等待ASR状态
             - 从生成状态切换到其他状态时发出一个<eos>信号
            等待TTS状态：
             - 若收到TTS给出的生成完毕信号，切换到待机状态
            等待ASR状态：
            - 若收到ASR给出的语音识别信息，切换到生成状态
            """
            try:
                message: RequestType | None = q_recv.get(False)
            except queue.Empty:
                message = None
            match state:
                case STANDBY:
                    if time.time() - standby_time > 5:
                        stop_generation.clear()
                        history.append({'role': 'user', 'content': '请随便说点什么吧！'})
                        kwargs = {"model": model, "text_inputs": history, "streamer": streamer}
                        generation_thread = threading.Thread(target=generate, kwargs=kwargs)
                        generation_thread.start()
                        state = GENERATE
                        text = ""
                        continue
                    if message == ASR_ACTIVATE:
                        state = WAIT_FOR_ASR

                case GENERATE:
                    try:
                        text += next(streamer)
                    except StopIteration:
                        q_send.put(LLM_EOS)
                        state = WAIT_FOR_TTS
                        stop_generation.set()
                        if generation_thread is not None and generation_thread.is_alive():
                            generation_thread.join()
                        continue
                    if message == ASR_ACTIVATE:
                        q_send.put(LLM_EOS)
                        state = WAIT_FOR_ASR
                        stop_generation.set()
                        if generation_thread is not None and generation_thread.is_alive():
                            generation_thread.join()
                        continue
                    *sentences, text = split_text(text, ".!?。？！…\n\r") # 将所有完整的句子发送
                    for i, sentence in enumerate(sentences):
                        q_send.put({
                            'from': 'llm',
                            'type': 'data',
                            'payload': {
                                'content': sentence,
                                'id': str(uuid.uuid4())
                            }
                        })

                case WAIT_FOR_ASR:
                    if message is not None and message['from'] == 'asr' and message['type'] == 'data':
                        stop_generation.clear()
                        history.append({'role': 'user', 'content': message['payload']['content']})
                        kwargs = {"model": model, "text_inputs": history, "streamer": streamer}
                        generation_thread = threading.Thread(target=generate, kwargs=kwargs)
                        generation_thread.start()
                        state = GENERATE
                        text = ""
                        continue

                case WAIT_FOR_TTS:
                    if message == TTS_FINISH:
                        state = STANDBY
                        standby_time = time.time()
                        continue
            if message is not None and message['type'] == 'signal' and message['payload'] == 'exit':
                stop_generation.set()
                stop_module.set()
        t_recv.join()
        t_send.join()
        if generation_thread is not None and generation_thread.is_alive():
            generation_thread.join()
