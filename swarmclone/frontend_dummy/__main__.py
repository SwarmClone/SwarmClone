import socket
import threading
import queue
from time import time, sleep

from ..request_parser import *
from ..config import config

# 前端模拟模块主程序
# 通过socket与面板通信，处理语音识别(ASR)、语音合成(TTS)、大语言模型(LLM)等模块的消息
# 使用双队列机制实现消息的接收和发送

# 初始化模块就绪消息
MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("frontend") # type: ignore 格式化来源字段

# 接收消息队列和接收线程
q_recv: queue.Queue[RequestType] = queue.Queue()
def recv_msg(sock: socket.socket, q: queue.Queue[RequestType], stop_module: threading.Event):
    """消息接收线程函数
    参数:
        sock: 网络套接字
        q: 消息接收队列
        stop_module: 线程停止事件
    """
    # TODO:检查这里是否仍然适用
    loader = Loader(config)  # 使用配置初始化请求加载器
    while True:
        data = sock.recv(1024)  # 接收网络数据
        if not data:  # 连接断开时退出循环
            break
        loader.update(data.decode())  # 解码并加载数据
        messages = loader.get_requests()  # 获取完整请求列表
        for message in messages:
            q.put(message)  # 将消息放入接收队列

# 发送消息队列和发送线程 
q_send: queue.Queue[RequestType] = queue.Queue()
def send_msg(sock: socket.socket, q: queue.Queue[RequestType], stop_module: threading.Event):
    """消息发送线程函数
    参数:
        sock: 网络套接字
        q: 消息发送队列
        stop_module: 线程停止事件
    """
    while True:
        message = q.get()  # 从队列获取消息
        data = dumps([message]).encode()  # 序列化并编码消息
        sock.sendall(data)  # 发送完整网络数据


if __name__ == '__main__':
    # 主程序入口
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # 连接面板服务器
        sock.connect((config.panel.server.host, config.unity_frontend.port))
        
        # 初始化线程控制事件
        stop_module = threading.Event()
        
        # 启动接收线程
        t_recv = threading.Thread(target=recv_msg, args=(sock, q_recv, stop_module))
        t_recv.start()
        
        # 启动发送线程
        t_send = threading.Thread(target=send_msg, args=(sock, q_send, stop_module))
        t_send.start()

        # 发送模块就绪通知
        q_send.put(MODULE_READY)

        # 等待面板启动指令
        while True:
            try:
                message: RequestType | None = q_recv.get(False)
                if message == PANEL_START:  # 收到启动指令后跳出循环
                    break
            except queue.Empty:
                sleep(0.1)  # 队列为空时短暂休眠

        # 初始化对话状态跟踪变量
        t0 = time()  # 时间基准点
        target = .0  # 下一个token的显示时间目标
        q_sentences: queue.Queue[str | None] = queue.Queue()  # 待处理句子队列
        tokens: dict[str, tuple[float, str] | None] = {}  # token缓存字典
        sentence_finished = True  # 当前句子是否处理完成
        current_sentence: str | None = None  # 当前处理的句子ID
        clear_screen = False  # 清屏标志
        user_str = ''  # 用户输入缓存
        ai_str = ''  # AI输出缓存
        
        # 主消息处理循环
        while True:
            message = None
            try:
                message = q_recv.get(False)  # 非阻塞获取消息
                print(message)  # 调试输出
            except queue.Empty:
                sleep(1 / 60)  # 维持约60FPS的刷新率
            
            # 清屏并显示当前对话状态
            print("\033[H\033[J", end="")  # ANSI清屏指令
            print(f"User: {user_str}\nAI: {ai_str}")  # 显示对话内容
            
            # 消息类型匹配处理
            match message:
                case x if x == PANEL_STOP:  # 停止指令
                    stop_module.set()
                    break
                case x if x == ASR_ACTIVATE:  # ASR激活通知
                    print("ASR activated")
                    # 重置语音处理状态
                    while not q_sentences.empty(): q_sentences.get()
                    tokens.clear()
                    clear_screen = True
                    current_sentence = None
                    sentence_finished = True
                    target = .0
                case {'from': 'asr', 'type': 'data', 'payload': {'user': user, 'content': content}}:  # 语音识别结果
                    user_str = f"{content}"  # 更新用户输入显示
                case {'from': 'tts', 'type': 'data', 'payload': {'id': sid, 'token': token, 'duration': duration}}:  # 语音合成token
                    if tokens[sid] is None: # type: ignore
                        tokens[sid] = [] # type: ignore  # 初始化token列表
                    tokens[sid].append((duration, token)) # type: ignore  # 添加token信息
                case {'from': 'llm', 'type': 'data', 'payload': {'content': content, 'id': sid}}:  # 大模型响应
                    q_sentences.put(sid) # type: ignore  # 将句子ID加入队列
                    tokens[sid] = None # type: ignore  # 初始化句子token缓存
                case x if x == LLM_EOS:  # 大模型响应结束
                    q_sentences.put(None)  # 添加结束标记

            # 句子处理逻辑
            if sentence_finished and not q_sentences.empty():
                sentence_finished = False
                current_sentence = q_sentences.get()  # 获取新句子ID
                print(current_sentence)  # 调试输出
                
                if current_sentence is None:  # 结束标记处理
                    sentence_finished = True
                    clear_screen = True
                    continue
                elif clear_screen:  # 清屏处理
                    clear_screen = False
                    ai_str = ''  # 重置AI输出

            # token显示处理
            if not sentence_finished and current_sentence and time() - t0 > target:
                if current_sentence not in tokens:  # 无对应token时跳过
                    continue
                if tokens[current_sentence] == []:  # token处理完成
                    sentence_finished = True
                    del tokens[current_sentence]
                    continue
                if tokens[current_sentence] is None:  # 等待token数据
                    continue
                
                # 取出并显示token
                (duration, token), *tokens[current_sentence] = tokens[current_sentence] # type: ignore
                print(f"Token: {token}, Duration: {duration}")  # 调试输出
                ai_str += token # type: ignore  # 追加到AI输出
                target = duration # type: ignore  # 设置下一个token显示时间
                t0 = time()  # 重置时间基准点
        
        # 等待线程结束
        t_recv.join()
        t_send.join()
