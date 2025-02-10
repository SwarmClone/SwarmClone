"""解析新的API.txt中定义的请求序列"""
import json
from .config import config
from typing import Literal

PayloadType = dict[str, str | float | int]
RequestType = dict[Literal["from", "type", "payload"], str | PayloadType]

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
        self.requests: list[RequestType] = []
    
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
    
    def get_requests(self) -> list[RequestType]:
        requests, self.requests = self.requests, []
        return requests

# 内置的信号
ASR_ACTIVATE: RequestType = {'from': 'asr', 'type': 'signal', 'payload': 'activate'}
LLM_EOS: RequestType = {'from': 'llm', 'type': 'signal', 'payload': 'eos'}
TTS_FINISH: RequestType = {'from': 'tts', 'type': 'signal', 'payload': 'finish'}
PANEL_START: RequestType = {'from': 'panel', 'type': 'signal', 'payload':'start'}
PANEL_STOP: RequestType = {'from': 'panel', 'type': 'signal', 'payload':'stop'}
MODULE_READY_TEMPLATE: RequestType = {'from':'{}', 'type': 'signal', 'payload':'ready'}

__all__ = [
    "loads",
    "dumps",
    "Loader",
    "PayloadType",
    "RequestType",
    "ASR_ACTIVATE",
    "LLM_EOS",
    "TTS_FINISH",
    "PANEL_START",
    "PANEL_STOP",
    "MODULE_READY_TEMPLATE"
] # 防止json、config等模块被重复导入
