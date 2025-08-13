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
    s = s.replace("\"", r"\"")
    return ast.literal_eval(f'"""{s}"""')

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
    
def get_live2d_actions() -> dict[str, str]:
    """
    res/ 目录下 *.json 文件：
    {
        "name": "对应模型名称",
        "action": "相对于本目录的动作文件（json）路径"
    }
    """
    res_dir = pathlib.Path("./res")
    actions: dict[str, str] = {}
    for file in res_dir.glob("*.json"):
        try:
            data = json.load(open(file))
            name = data['name']
            if not isinstance(name, str):
                raise TypeError("动作名称必须为字符串")
            if not isinstance(data["action"], str):
                raise TypeError("动作文件路径必须为字符串")
            if not data["path"].endswith(".json"):
                raise ValueError("动作文件扩展名必须为.json")
            path = res_dir / pathlib.Path(data['path'])
            if not path.is_file():
                raise FileNotFoundError(f"动作文件不存在：{path}")
        except Exception as e:
            print(f"{file} 不是正确的动作文件：{e}")
            continue
        actions[name] = str(path)
    return actions

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
        result.append({'token': sub.content.replace('\n', ' ').strip() + "\n",
                       'duration': end - start})
        cursor = end

    # 处理最后一段空白（如果存在）
    trailing_gap = total_expected - cursor
    if trailing_gap > 1e-4:
        result.append({'token': '', 'duration': trailing_gap})

    # 校验：所有 duration 之和必须等于 total_expected
    assert abs(sum(item['duration'] for item in result) - total_expected) < 1e-4
    return result

import asyncio
from edge_tts import VoicesManager
def get_voices():
    """
    获得 edge-tts 提供的所有中文声音，并返回[{'friendly_name': [人类易读的名称], 'voice': [声音标签]}, ...]
    """
    async def _get_voices():
        voices = await VoicesManager.create()
        chinese_voices = voices.find(Gender="Female", Locale="zh-CN")
        return [
            {
                'friendly_name': f"{voice['FriendlyName']}",
                'voice': voice['ShortName']
            }
            for voice in chinese_voices
        ]
    
    # 获取事件循环并运行异步函数
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_get_voices())
    except RuntimeError:
        # 如果没有事件循环，创建一个新的
        return asyncio.run(_get_voices())

get_type_name = lambda obj: type(obj).__name__

import math
from typing import Callable
def cosine_interpolation(a: float, b: float, t: float) -> float:
    # [0, 1] -> [0, pi] -cos-*-1-> [-1, 1] -/2-+0.5-> [0, 1]
    x = -math.cos(t * math.pi) / 2 + 0.5
    return a * (1 - x) + b * x

def quintic_interpolation(a: float, b: float, t: float) -> float:
    x = 6 * t ** 5 - 15 * t ** 4 + 10 * t ** 3
    return a * (1 - x) + b * x

def multioctave_perlin_noise(
    x: float,
    interpolation: Callable[[float, float, float], float],
    octaves: int | None = None,
    persistence: float | None = None,):
    total = 0
    if octaves is not None and persistence is not None:
        amplitudes = [persistence ** i for i in range(octaves)]
    else:
        raise ValueError("Either amplitudes or octaves and persistence must be provided.")
    total_amp = sum(amplitudes)
    highest_freq = 2 ** (octaves - 1)
    x = x / highest_freq
    for i in range(octaves):
        frequency = 2 ** i
        total += smooth_perlin_noise(x * frequency, interpolation) * amplitudes[i]
    return total / total_amp

def smooth_perlin_noise(x: float, interpolation: Callable[[float, float, float], float]):
    perm_table = [
        151,160,137,91,90,15,
		131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,
		190, 6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,
		88,237,149,56,87,174,20,125,136,171,168, 68,175,74,165,71,134,139,48,27,166,
		77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,
		102,143,54, 65,25,63,161, 1,216,80,73,209,76,132,187,208, 89,18,169,200,196,
		135,130,116,188,159,86,164,100,109,198,173,186, 3,64,52,217,226,250,124,123,
		5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,
		223,183,170,213,119,248,152, 2,44,154,163, 70,221,153,101,155,167, 43,172,9,
		129,22,39,253, 19,98,108,110,79,113,224,232,178,185, 112,104,218,246,97,228,
		251,34,242,193,238,210,144,12,191,179,162,241, 81,51,145,235,249,14,239,107,
		49,192,214, 31,181,199,106,157,184, 84,204,176,115,121,50,45,127, 4,150,254,
		138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180,
		151
    ]
    a: int = int(x)
    b = a + 1
    t = x - a
    value1 = (perm_table[a % 255] / 255 - 0.5) * 2
    value2 = (perm_table[b % 255] / 255 - 0.5) * 2
    return interpolation(value1, value2, t)