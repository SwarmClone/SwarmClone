from dataclasses import dataclass

@dataclass
class ASRConfig:
    # 语音识别模型选择(paraformer)
    MODEL: str = "paraformer"
    # 语音模型路径
    MODELPATH="~/.swarmclone/asr/"
    # token.txt路径
    # 解码方法（greedy_search, modified_beam_search）
    DECODING_METHOD: str = "greedy_search"
    # 推理设备（cpu, cuda, coreml）
    PROVIDER: str = "cpu"
    # 热词文件路径，每行一个词/短语。
    HOTWORDS_FILE: str = ""
    # 热词分数，用于热词。仅在给定HOTWORDS_FILE时使用。
    HOTWORDS_SCORE: float = 1.5
    # 解码时对空字符的惩罚。
    BLANK_PENALTY: float = 0.0
