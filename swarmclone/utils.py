from modelscope import snapshot_download as modelscope_snapshot_download
from huggingface_hub import snapshot_download as huggingface_snapshot_download
import re

def download_model(model_id: str, model_source: str, local_dir: str):
    match model_source:
        case "modelscope":
            modelscope_snapshot_download(model_id, local_dir=local_dir, repo_type="model")
        case "huggingface":
            huggingface_snapshot_download(model_id, local_dir=local_dir, repo_type="model")
        case x if x.startswith("openai+"):
            raise ValueError((
                f"OpenAI API模型不能被下载。"
                "如果你在使用`LLMTransformers`（默认选项）时遇到了这个问题，"
                "请转而使用`LLMOpenAI`。"
            ))
        case _:
            raise ValueError(f"Invalid model source: {model_source}")

def split_text(s: str, separators: str="。？！～.?!~\n\r") -> list[str]: # By DeepSeek
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

def escape_all(s: str) -> str: # By Kimi-K2 & Doubao-Seed-1.6
    # 把非可打印字符（含换行、制表等）统一转成 \xhh 或 \uXXXX
    def _escape(m: re.Match[str]):
        c = m.group()
        # 优先使用简写转义
        return {
            '\n': r'\n',
            '\r': r'\r',
            '\t': r'\t',
            '\b': r'\b',
            '\f': r'\f',
            '\\': r'\\',
            '\"': r'\"',
            '\'': r'\'',
        }.get(c, c.encode('unicode_escape').decode('ascii'))

    # 预编译正则表达式，匹配非打印字符和特定特殊字符
    pattern = re.compile(r'([\x00-\x1F\x7F-\x9F\u0080-\u009F\u2000-\u200F\u2028-\u2029\'\"\\])')

    return re.sub(pattern, _escape, s)

import ast
def unescape_all(s: str) -> str: # By Kimi-K2 & KyvYang
    return ast.literal_eval(f'"{s}"')

import torch
def get_devices() -> dict[str, str]:
    devices: dict[str, str] = {}
    for i in range(torch.cuda.device_count()):
        devices[f"cuda:{i}"] = f"cuda:{i} " + torch.cuda.get_device_name(i)
    devices['cpu'] = 'CPU'
    return devices

import pathlib
import json
def get_live2d_models() -> dict[str, str]:
    """
    res/ 目录下 *.json 文件：
    {
        "name": "模型名称",
        "path": "相对于本目录的模型文件（.model3.json/.model.json）路径"
    }
    """
    res_dir = pathlib.Path("./res")
    models: dict[str, str] = {}
    for file in res_dir.glob("*.json"):
        try:
            data = json.load(open(file))
            name = data['name']
            if not isinstance(name, str):
                raise TypeError("模型名称必须为字符串")
            path = res_dir / pathlib.Path(data['path'])
            if not path.is_file():
                raise FileNotFoundError(f"模型文件不存在：{path}")
        except Exception as e:
            print(f"{file} 不是正确的模型导入文件：{e}")
            continue
        models[name] = str(path)
    return models
