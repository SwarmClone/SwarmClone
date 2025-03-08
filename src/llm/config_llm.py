from dataclasses import dataclass, field

@dataclass
class MiniLM2Config:
    MODEL_PATH: str = "~/.swarmclone/llm/MiniLM2/MiniLM2-nGPT-0.4b-dialogue"
    MODEL_ID: str = "KyvYang/MiniLM2-nGPT-0.4b-dialogue"
