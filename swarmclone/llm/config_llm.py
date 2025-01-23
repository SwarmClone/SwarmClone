from dataclasses import dataclass, field

@dataclass
class LLMConfig:
    SPECIAL_TOKENS: dict[str, int] = field(default_factory=lambda: {"<pad>": 0, "<eos>": 1, "<unk>": 2})
    NUM_WORKERS: int = 4
    DEVICE: str = "cuda"

    HUMAN_PREFIX: str = "人类："
    AI_PREFIX: str = "AI："

    MODEL_PATH: str = "~/.swarmclone/llm/MiniLM2/models/sft/sft.json"
