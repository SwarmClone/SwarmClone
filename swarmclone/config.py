from dataclasses import dataclass, field

@dataclass
class Config:
    SPECIAL_TOKENS: dict[str, int] = field(default_factory=lambda: {"<pad>": 0, "<eos>": 1, "<unk>": 2})
    NUM_WORKERS: int = 4
    DEVICE: str = "cuda"
    
    CONFIG_FILE = './dist/server.toml'

    # 网络配置
    PANEL_HOST: str = "localhost"
    LLM_PORT: int = 8000
    ASR_PORT: int = 8001
    TTS_PORT: int = 8002
    FRONTEND_PORT: int = 8003
    CHAT_PORT: int = 8004
    WEBSITE_PORT: int = 7620
    PANEL_PORT: int = 80
    REQUESTS_SEPARATOR: str = "%SEP%"

    # 模块配置
    START_ASR_COMMAND: list[str] = field(default_factory=lambda: ["python", "-m", "swarmclone.asr"])
    START_TTS_COMMAND: list[str] = field(default_factory=lambda: ["python", "-m", "swarmclone.tts"])
    START_LLM_COMMAND: list[str] = field(default_factory=lambda: ["python", "-m", "swarmclone.model_qwen"])
    START_FRONTEND_COMMAND: list[str] = field(default_factory=lambda: ["python", "-m", "swarmclone.frontend_dummy"])
    START_PANEL_COMMAND: list[str] = field(default_factory=lambda: ["python", "-m", "swarmclone.panel_dummy"])
