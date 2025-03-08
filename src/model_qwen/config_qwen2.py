from dataclasses import dataclass

@dataclass
class Qwen2Config:
    MODEL_PATH: str = "~/.swarmclone/llm/Qwen/Qwen2.5-0.5B-Instruct"
    MODEL_ID: str = "Qwen/Qwen2.5-0.5B-Instruct"
