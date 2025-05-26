import socket
import json
import time
import librosa
import sounddevice as sd # type: ignore
from typing import Literal
from .sherpa_asr import asr_init, create_recognizer
from .sherpa_vad import vad_init, create_detector

from . import config

# 抄自旧版 request_parser.py
##TODO: 清理旧代码改用asyncio
EmotionType = dict[Literal["like", "disgust", "anger", "happy", "sad", "neutral"], float]
PayloadType = dict[str, str | float | int | EmotionType]
RequestType = dict[Literal["from", "type", "payload"], str | PayloadType]

ASR_ACTIVATE: RequestType = {'from': 'asr', 'type': 'signal', 'payload': 'activate'}
LLM_EOS: RequestType = {'from': 'llm', 'type': 'signal', 'payload': 'eos'}
TTS_FINISH: RequestType = {'from': 'tts', 'type': 'signal', 'payload': 'finish'}
PANEL_START: RequestType = {'from': 'panel', 'type': 'signal', 'payload':'start'}
PANEL_STOP: RequestType = {'from': 'panel', 'type': 'signal', 'payload':'stop'}
MODULE_READY_TEMPLATE: RequestType = {'from':'{}', 'type': 'signal', 'payload':'ready'}

MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("asr") # type: ignore

def loads(request_str: str) -> list[RequestType]:
    request_strings = request_str.split(config.panel.server.requests_separator)
    requests = []
    for request_string in request_strings:
        if not request_string:
            continue
        try:
            requests.append(json.loads(request_string))
        except json.JSONDecodeError:
            print(f"Invalid JSON format: {request_string}")
    return requests

def dumps(requests: list[RequestType]) -> str:
    return "".join([
        (json.dumps(request).replace(config.panel.server.requests_separator, "") + # 防止在不应出现的地方出现分隔符
        config.panel.server.requests_separator)
        for request in requests
    ])

class Loader: # loads的进一步封装
    def __init__(self, config):
        self.sep = config.panel.server.requests_separator
        self.request_str = ""
        self.requests: list[dict] = []
    
    def update(self, request_str: str) -> None:
        self.request_str += request_str
        request_strings = self.request_str.split(self.sep)
        left = ""
        for i, request_string in enumerate(request_strings):
            if not request_string:
                continue
            try:
                self.requests.append(json.loads(request_string))
            except json.JSONDecodeError:
                if i == len(request_strings) - 1: # 最后一个请求被截断，留待下次更新
                    left = request_strings[-1]
                else:
                    print(f"Invalid JSON format: {request_string}")
        self.request_str = left
    
    def get_requests(self) -> list[dict]:
        requests, self.requests = self.requests, []
        return requests


if __name__ == '__main__':

    asr_init(config.asr.sherpa)
    vad_init(config.asr.sherpa)

    vad = create_detector(config.asr.sherpa)
    recognizer = create_recognizer(config.asr.sherpa)
    

    # sherpa-onnx will do resampling inside.
    sample_rate = 44100
    samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms

    stream = recognizer.create_stream()


    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        sd.InputStream(channels=1, dtype="float32", samplerate=sample_rate) as s
    ):
        sock.connect((config.panel.server.host, config.asr.port))
        last_result = ""
        segment_id = 0
        print("就绪，等待开始。")
        sock.sendall(dumps([MODULE_READY]).encode())
        while True:
            try:
                data = loads(sock.recv(1024).decode())
                if PANEL_START in data:
                    break
            except:
                continue
            time.sleep(0.1)

        print("开始录音。")
        speech_started = False
        while True:
            try:
                # samples_vad = alsa.read(samples_per_read)
                # vad.accept_waveform(samples_vad)
                # if vad.is_ready():
                #     vad_result = vad.get_result()
                #     if vad_result:
                #         print(f"VAD: {vad_result}")
                #     vad.reset()
                #     if vad_result != "speech":
                #         continue
                
                samples, _ = s.read(samples_per_read)  # a blocking read
                samples = samples.reshape(-1)

                vad.accept_waveform(librosa.resample(samples, orig_sr=sample_rate, target_sr=16000))

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
                        req: RequestType = {
                            "from": "asr",
                            "type": "data",
                            "payload": {
                                "user": "Developer A",
                                "content": result
                            }
                        }
                        sock.sendall(dumps([req]).encode())
                        segment_id += 1
                    recognizer.reset(stream)
            except KeyboardInterrupt:
                sock.close()
                break
