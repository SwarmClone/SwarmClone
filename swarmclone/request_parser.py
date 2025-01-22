"""解析新的API.txt中定义的请求序列"""
import json
from .config import Config

config = Config()

def parse_request(request_str: str) -> list[dict]:
    request_strings = request_str.split(config.REQUESTS_SEPARATOR)
    requests = []
    for request_string in request_strings:
        try:
            requests.append(json.loads(request_string))
        except json.JSONDecodeError:
            print(f"Invalid JSON format: {request_string}")
    return requests
