import socket
import threading
import json
import queue
import os
import re
import uuid
import time
from enum import Enum
import torch
import torch.nn.functional as F
from tokenizers import Tokenizer # type: ignore
from . import config, llm_config
from ..request_parser import *
from .model import LLM

MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("llm") # type: ignore

def build_context(history: list[tuple[str, str]], tokenizer: Tokenizer,
                max_length: int) -> torch.Tensor:
    ids = []
    human_prefix_ids = tokenizer.encode(llm_config.HUMAN_PREFIX).ids
    ai_prefix_ids = tokenizer.encode(llm_config.AI_PREFIX).ids
    separator_ids = tokenizer.encode("\n" * 3).ids
    for i in range(len(history)):
        turn = history[i]
        ids += human_prefix_ids + tokenizer.encode(turn[0]).ids + separator_ids
        ids += ai_prefix_ids + tokenizer.encode(turn[1]).ids
        if i < len(history) - 1:
            ids += separator_ids
    ids = ids[-max_length:]
    return torch.LongTensor(ids).unsqueeze(0)

def append_history(history: list[tuple[str, str]], role: str, text: str) -> list[tuple[str, str]]:
    if role == "human":
        history.append((text, ""))
    else:
        history[-1] = (history[-1][0], text)
    return history

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

q_generate: queue.Queue[str] = queue.Queue()
def generate(model: LLM, tokenizer: Tokenizer, model_config: dict,
            text_inputs: list[tuple[str, str]], q: queue.Queue[str], stop_generation: threading.Event):
    with torch.no_grad():
        n_blank_lines = 0
        print(text_inputs)
        input_ids = build_context(text_inputs, tokenizer, model_config['max_length']).to(config.DEVICE)
        while not stop_generation.is_set():
            output = model(input_ids)
            logits = F.softmax(output[0][-1] / model_config['temperature'], dim=-1)
            probs, indices = logits.topk(round(tokenizer.get_vocab_size() * model_config['top_p']))
            sample = torch.multinomial(probs, 1)
            token_id = indices[sample]
            input_ids = torch.cat([input_ids, token_id.unsqueeze(0)], dim=-1)[:, -model_config['max_length']:]
            token = tokenizer.id_to_token(token_id.item())
            print(token)
            if token == "\n":
                n_blank_lines += 1
                if n_blank_lines >= 3:
                    q.put("<eos>")
                    break
            else:
                n_blank_lines = 0
                q.put(token)


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
    successful = False
    abs_model_path = os.path.expanduser(llm_config.MODEL_PATH)
    while not successful:
        try:
            model_config = json.load(open(abs_model_path))
            config_dir = os.path.dirname(abs_model_path)
            tokenizer = Tokenizer.from_file(os.path.join(config_dir, model_config['tokenizer_path']))
            vocab_size = tokenizer.get_vocab_size()
            model = LLM(
                vocab_size=vocab_size,
                dim=model_config['model_dim'],
                max_length=model_config['max_length'],
                n_heads=model_config['num_heads'],
                n_blocks=model_config['num_layers'],
                dropout=0 # 推理时不使用dropout
            )
            if model_config['checkpoint_file']:
                print(f"正在从{model_config['checkpoint_file']}加载模型……")
                checkpoint_path = os.path.join(config_dir, model_config['checkpoint_file'])
                model.load_state_dict(torch.load(checkpoint_path, weights_only=True))
            model.to(config.DEVICE)
            model.eval()
            successful = True
        except:
            choice = input("加载模型失败，请检查是否将MiniLM2模型放置于对应位置！")
            exit(1)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.PANEL_HOST, config.LLM_PORT))
        t_recv = threading.Thread(target=recv_msg, args=(sock, q_recv, stop_module))
        t_recv.start()
        t_send = threading.Thread(target=send_msg, args=(sock, q_send, stop_module))
        t_send.start()
        generation_thread: threading.Thread | None = None # 在没有生成任务前没有值

        torch.set_float32_matmul_precision('medium') # 降低矩阵乘法精度以减少显存使用
        print("开始编译模型")
        model.compile(fullgraph=True) # 进行编译提高推理速度
        model(torch.zeros((1, model_config['max_length']), dtype=torch.int, device=config.DEVICE)) # 进行前向传播触发编译
        print("编译成功结束")

        q_send.put(MODULE_READY) # 就绪

        while True: # 等待启动
            try:
                message: RequestType | None = q_recv.get(False)
            except queue.Empty:
                message = None
            if message is not None and message == PANEL_START:
                break
            time.sleep(0.1) # 防止CPU占用过高

        history: list[tuple[str, str]] = []
        state: States = States.STANDBY
        text = "" # 尚未发送的文本
        full_text = "" # 一轮生成中的所有文本
        standby_time = time.time()
        message_consumed = True # 收到消息后是否已处理
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
            print(message)
            if message_consumed:
                try:
                    message = q_recv.get(False)
                    message_consumed = False
                    if message.get("from") == "tts" and message.get("type") == "data": # 不需要处理TTS给出的对齐信息
                        message_consumed = True
                        continue
                except queue.Empty:
                    message = None
            match state:
                case States.STANDBY:
                    if time.time() - standby_time > 50000:
                        stop_generation.clear()
                        history = append_history(history, "human", "请随便说点什么吧！")
                        kwargs = {
                            'model': model,
                            'tokenizer': tokenizer,
                            'model_config': model_config,
                            'text_inputs': history,
                            'q': q_generate,
                            'stop_generation': stop_generation
                        }
                        generation_thread = threading.Thread(target=generate, kwargs=kwargs)
                        generation_thread.start()
                        state = States.GENERATE
                        text = ""
                        full_text = ""
                    if message == ASR_ACTIVATE:
                        state = States.WAIT_FOR_ASR
                        message_consumed = True

                case States.GENERATE:
                    try:
                        token = q_generate.get(False)
                    except queue.Empty:
                        token = ""
                    if token == "<eos>": # 生成完毕
                        # 停止生成并清空队列
                        stop_generation.set()
                        if generation_thread is not None and generation_thread.is_alive():
                            generation_thread.join()
                        while not q_generate.empty():
                            q_generate.get()
                        # 处理剩余的文本
                        if text.strip():
                            q_send.put({
                                'from': 'llm',
                                'type': 'data',
                                'payload': {
                                    'content': text,
                                    'id': str(uuid.uuid4())
                                }
                            })
                        full_text += text
                        # 将这轮的生成文本加入历史记录
                        history = append_history(history, "ai", full_text.strip())
                        # 发送信号并等待TTS
                        state = States.WAIT_FOR_TTS
                        q_send.put(LLM_EOS)
                        text = ""
                        full_text = ""
                        continue
                    text += token
                    if message == ASR_ACTIVATE:
                        print("ASR激活")
                        # 停止生成并清空队列
                        stop_generation.set()
                        if generation_thread is not None and generation_thread.is_alive():
                            generation_thread.join()
                        q_send.put(LLM_EOS)
                        while not q_generate.empty():
                            q_generate.get()
                        # 处理剩余的文本，被打断时的文本直接加入历史记录不需要发出
                        full_text += text
                        # 将这轮的生成文本加入历史记录
                        history = append_history(history, "ai", full_text.strip())
                        # 发送信号并等待ASR
                        state = States.WAIT_FOR_ASR
                        q_send.put(LLM_EOS)
                        text = ""
                        full_text = ""
                        message_consumed = True
                        continue
                    sentences = []
                    if text.strip():
                        *sentences, text = split_text(text) # 将所有完整的句子发送
                    for i, sentence in enumerate(sentences):
                        q_send.put({
                            'from': 'llm',
                            'type': 'data',
                            'payload': {
                                'content': sentence,
                                'id': str(uuid.uuid4())
                            }
                        })

                case States.WAIT_FOR_ASR:
                    if     (message is not None and
                            message['from'] == 'asr' and
                            message['type'] == 'data' and
                            isinstance(message['payload'], dict) and
                            isinstance(message['payload']['content'], str)):
                        message_consumed = True
                        stop_generation.clear()
                        history = append_history(history, "human", message['payload']['content'])
                        kwargs = {
                            'model': model,
                            'tokenizer': tokenizer,
                            'model_config': model_config,
                            'text_inputs': history,
                            'q': q_generate,
                            'stop_generation': stop_generation
                        }
                        generation_thread = threading.Thread(target=generate, kwargs=kwargs)
                        generation_thread.start()
                        state = States.GENERATE
                        text = ""
                        full_text = ""

                case States.WAIT_FOR_TTS:
                    if message == TTS_FINISH:
                        state = States.STANDBY
                        standby_time = time.time()
                        message_consumed = True
                    if message == ASR_ACTIVATE:
                        state = States.WAIT_FOR_ASR
                        message_consumed = True
            if message is not None and message == PANEL_STOP:
                stop_generation.set()
                stop_module.set()
                break
        t_recv.join()
        t_send.join()
        if generation_thread is not None and generation_thread.is_alive():
            generation_thread.join()
