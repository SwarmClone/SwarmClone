import socket
import time
import queue
import threading
from . import config
from ..request_parser import *

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

stop = threading.Event()

    # sherpa-onnx will do resampling inside.
    sample_rate = 16000
    samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms

    stream = recognizer.create_stream()


    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        sd.InputStream(channels=1, dtype="float32", samplerate=sample_rate) as s
    ):
        sock.connect((config.PANEL_HOST, config.ASR_PORT))
        # 启动接收和发送线程
        t_send = threading.Thread(target=send_msg, args=(sock, q_send, stop))
        t_recv = threading.Thread(target=recv_msg, args=(sock, q_recv, stop))
        t_send.start()
        t_recv.start()

                vad.accept_waveform(samples)

                if vad.is_speech_detected():
                    if not speech_started:
                        sock.sendall(dumps([ASR_ACTIVATE]).encode())
                        speech_started = True
                else:
                    speech_started = False

                stream.accept_waveform(sample_rate, samples)
                while recognizer.is_ready(stream):
                    recognizer.decode_stream(stream)

                is_endpoint = recognizer.is_endpoint(stream)

                result: str = recognizer.get_result(stream)
                
                if result and (last_result != result):
                    last_result = result
                    print("\r{}:{}".format(segment_id, result), end="", flush=True)
                if is_endpoint:
                    if result:
                        print("\r{}:{}".format(segment_id, result), flush=True)
                        data: RequestType = {
                            "from": "asr",
                            "type": "data",
                            "payload": {
                                "user": "Developer A",
                                "content": result
                            }
                        }
                        sock.sendall(dumps([data]).encode())
                        segment_id += 1
                    recognizer.reset(stream)
            except KeyboardInterrupt:
                sock.sendall(b'{"from": "stop"}')
                sock.close()
                break
            time.sleep(0.1)
        while True:
            s = input("> ")

            # 是否需要退出
            try:
                message = q_recv.get(False)
            except queue.Empty:
                pass
            else:
                if message == PANEL_STOP:
                    break
            
            # 发出激活信息和语音信息
            q_send.put(ASR_ACTIVATE)
            time.sleep(0.1)
            q_send.put({
                'from': 'asr',
                'type': 'data',
                'payload': {
                    'user': 'Developer A',
                    'content': s
                }
            })
    stop.set() # 通知线程退出
    t_send.join()
    t_recv.join()
