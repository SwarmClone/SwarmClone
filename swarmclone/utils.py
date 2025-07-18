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
            '\f': r'\f'
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
            if not isinstance(data["path"], str):
                raise TypeError("模型文件路径必须为字符串")
            if not data["path"].endswith(".model.json") and not data["path"].endswith(".model3.json"):
                raise ValueError("模型文件扩展名必须为.model.json或.model3.json")
            path = res_dir / pathlib.Path(data['path'])
            if not path.is_file():
                raise FileNotFoundError(f"模型文件不存在：{path}")
        except Exception as e:
            print(f"{file} 不是正确的模型导入文件：{e}")
            continue
        models[name] = str(path)
    return models

import srt
def parse_srt_to_list(srt_text: str) -> list[dict[str, float | str]]: # By: Kimi-K2
    """
    把 SRT 全文转换成：
    [{'token': <歌词>, 'duration': <秒>}, ...]
    若字幕间有空档，用空字符串占位。
    """
    subs = list(srt.parse(srt_text))
    if not subs:          # 空字幕直接返回
        return []

    result: list[dict[str, float | str]] = []
    total_expected = subs[-1].end.total_seconds()  # 歌曲总长度
    cursor = 0.0

    for sub in subs:
        start = sub.start.total_seconds()
        end   = sub.end.total_seconds()

        # 处理字幕开始前的空白
        gap = start - cursor
        if gap > 1e-4:      # 出现超过 0.1 ms 的空白
            result.append({'token': '', 'duration': gap})

        # 字幕本身
        result.append({'token': sub.content.replace('\n', ' ').strip(),
                       'duration': end - start})
        cursor = end

    # 处理最后一段空白（如果存在）
    trailing_gap = total_expected - cursor
    if trailing_gap > 1e-4:
        result.append({'token': '', 'duration': trailing_gap})

    # 校验：所有 duration 之和必须等于 total_expected
    assert abs(sum(item['duration'] for item in result) - total_expected) < 1e-4
    return result
