"""解析新的API.txt中定义的请求序列"""
import json
from .config import Config

config = Config()

def loads(request_str: str) -> list[dict]:
    request_strings = request_str.split(config.REQUESTS_SEPARATOR)
    requests = []
    for request_string in request_strings:
        if not request_string:
            continue
        try:
            requests.append(json.loads(request_string))
        except json.JSONDecodeError:
            print(f"Invalid JSON format: {request_string}")
    return requests

def dumps(requests: list[dict]) -> str:
    return "".join([
        (json.dumps(request).replace(config.REQUESTS_SEPARATOR, "") + # 防止在不应出现的地方出现分隔符
        config.REQUESTS_SEPARATOR)
        for request in requests
    ])
