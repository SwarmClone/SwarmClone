import socket
import threading
import json
import queue
import os
import re
import uuid
import time
from enum import Enum
from transformers import ( # type: ignore
    AutoModelForCausalLM,
    AutoTokenizer,
    TextIteratorStreamer,
    StoppingCriteriaList,
    StoppingCriteria,
    StopStringCriteria
)

from . import tokenizer, model, classifier_model, classifier_tokenizer
from ..request_parser import *
from ..config import config

MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("llm") # type: ignore

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

def split_text(s, separators="。？！～.?!~\n\r"): # By DeepSeek
    # 构建正则表达式模式
    separators_class = ''.join(map(re.escape, separators))
    pattern = re.compile(rf'([{separators_class}]+)')
    
    # 分割并处理结果
    parts = pattern.split(s)
    result = []
    
    # 合并文本与分隔符（成对处理）
    for text, delim in zip(parts[::2], parts[1::2]):
        if (cleaned := (text + delim).lstrip()):
            result.append(cleaned)
    
    # 处理未尾未配对内容（保留后置空格）
    if len(parts) % 2:
        if (last_cleaned := parts[-1].lstrip()):
            result.append(last_cleaned)
    
    return result

def get_emotion(text: str) -> EmotionType:
    ids = classifier_tokenizer([text], return_tensors="pt").input_ids.to(classifier_model.device)
    logits = classifier_model(input_ids=ids).logits
    neutral, like, sad, disgust, anger, happy = logits.tolist()[0]
    return {
        'like': like,
        'disgust': disgust,
        'anger': anger,
        'happy': happy,
        'sad': sad,
        'neutral': neutral
    }

def build_msg(
        content: str,
        emotion: EmotionType = {
            'like': 0,
            'disgust': 0,
            'anger': 0,
            'happy': 0,
            'sad': 0,
            'neutral': 1.0 # 无感情占位符
        }):
    return {
        'from': 'llm',
        'type': 'data',
        'payload': {
            'content': content,
            'id': str(uuid.uuid4()),
            'emotion': emotion
        }
    }

q_recv: queue.Queue[RequestType] = queue.Queue()
def recv_msg(sock: socket.socket, q: queue.Queue[RequestType], stop_module: threading.Event):
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

def generate(model: AutoModelForCausalLM, text_inputs: list[dict[str, str]], streamer: TextIteratorStreamer):
    try:
        text = tokenizer.apply_chat_template(text_inputs, tokenize=False, add_generation_prompt=True)
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
        model.generate(
            **model_inputs,
            max_new_tokens=512,
            streamer=streamer,
            stopping_criteria=StoppingCriteriaList([
                CustomStoppingCriteria(stop_generation, tokenizer.eos_token_id),
                StopStringCriteria(tokenizer, "\n" * 3)
            ])
        )
    except Exception as e:
        print(e)
        stop_generation.set()

# 状态
class States(Enum):
    STANDBY = 0
    GENERATE = 1
    WAIT_FOR_TTS = 2
    WAIT_FOR_ASR = 3

# 事件
stop_generation = threading.Event()
stop_module = threading.Event()

if __name__ == '__main__':
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.panel.server.host, config.llm.port))
        t_recv = threading.Thread(target=recv_msg, args=(sock, q_recv, stop_module))
        t_recv.start()
        t_send = threading.Thread(target=send_msg, args=(sock, q_send, stop_module))
        t_send.start()
        generation_thread: threading.Thread | None = None # 在没有生成任务前没有值

        q_send.put(MODULE_READY) # 就绪

        while True: # 等待启动
            try:
                message: RequestType | None = q_recv.get(False)
            except queue.Empty:
                message = None
            if message is not None and message == PANEL_START:
                break
            time.sleep(0.1) # 防止CPU占用过高

        history: list[dict[str, str]] = []
        chat_messages: list[tuple[str, str]] = []
        state: States = States.STANDBY
        text = "" # 尚未发送的文本
        full_text = "" # 一轮生成中的所有文本
        standby_time = time.time()
        message_consumed = True # 受到消息后是否已处理
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
            if message is not None:
                print(message, state)
            if message_consumed:
                try:
                    message = q_recv.get(False)
                    message_consumed = False
                    if message.get("from") == "tts" and message.get("type") == "data": # 不需要处理TTS给出的对齐信息
                        message_consumed = True
                        continue
                except queue.Empty:
                    message = None
            
            if state == States.STANDBY:
                if time.time() - standby_time > 10 and chat_messages:
                    stop_generation.clear()
                    history += [{'role': 'chat', 'content': f"{name}：{content}"} for name, content in chat_messages]
                    chat_messages.clear()
                    kwargs = {"model": model, "text_inputs": history, "streamer": streamer}
                    generation_thread = threading.Thread(target=generate, kwargs=kwargs)
                    generation_thread.start()
                    state = States.GENERATE
                    text = ""
                if message == ASR_ACTIVATE:
                    state = States.WAIT_FOR_ASR
                    message_consumed = True

            elif state == States.GENERATE:
                try:
                    text += next(streamer)
                except StopIteration: # 生成完毕
                    # 停止生成
                    stop_generation.set()
                    if generation_thread is not None and generation_thread.is_alive():
                        generation_thread.join()
                    # 处理剩余的文本
                    if stripped_text := text.strip():
                        emotion = get_emotion(stripped_text)
                        q_send.put(build_msg(stripped_text, emotion))
                    full_text += text
                    # 将这轮的生成文本加入历史记录
                    history.append({'role': 'assistant', 'content': full_text.strip()})
                    # 发出信号并等待TTS
                    q_send.put(LLM_EOS)
                    state = States.WAIT_FOR_TTS
                    text = ""
                    full_text = ""
                if message == ASR_ACTIVATE:
                    # 停止生成
                    stop_generation.set()
                    if generation_thread is not None and generation_thread.is_alive():
                        generation_thread.join()
                    for _ in streamer:... # 跳过剩余的文本
                    # 将这轮的生成文本加入历史记录
                    history.append({'role': 'assistant', 'content': full_text.strip()})
                    # 发出信号并等待ASR
                    q_send.put(LLM_EOS)
                    state = States.WAIT_FOR_ASR
                    text = ""
                    full_text = ""
                    message_consumed = True
                if text.strip(): # 防止文本为空导致报错
                    *sentences, text = split_text(text) # 将所有完整的句子发送
                    for i, sentence in enumerate(sentences):
                        emotion = get_emotion(sentence)
                        q_send.put(build_msg(sentence, emotion))

            elif state == States.WAIT_FOR_ASR:
                if     (message is not None and
                        message['from'] == 'asr' and
                        message['type'] == 'data' and
                        isinstance(message['payload'], dict) and
                        isinstance(message['payload']['content'], str)):
                    message_consumed = True
                    stop_generation.clear()
                    history += [{'role': 'chat', 'content': f"{name}：{content}"} for name, content in chat_messages]
                    chat_messages.clear()
                    history.append({'role': 'user', 'content': message['payload']['content']})
                    kwargs = {"model": model, "text_inputs": history, "streamer": streamer}
                    generation_thread = threading.Thread(target=generate, kwargs=kwargs)
                    generation_thread.start()
                    state = States.GENERATE
                    text = ""
                elif message == ASR_ACTIVATE:
                    message_consumed = True # 已经激活的不需要再激活一次

            elif state == States.WAIT_FOR_TTS:
                if message == TTS_FINISH:
                    state = States.STANDBY
                    standby_time = time.time()
                    message_consumed = True
                if message == ASR_ACTIVATE:
                    state = States.WAIT_FOR_ASR
                    message_consumed = True

            if (message is not None and
                message['from'] == 'chat' and
                message['type'] == 'data' and
                isinstance(message['payload'], dict) and
                isinstance(message['payload']['user'], str) and
                isinstance(message['payload']['content'], str)):
                chat_messages.append((message['payload']['user'], message['payload']['content']))
                message_consumed = True
            
            if message is not None and message == PANEL_STOP:
                stop_generation.set()
                stop_module.set()
                break
        t_recv.join()
        t_send.join()
        if generation_thread is not None and generation_thread.is_alive():
            generation_thread.join()
