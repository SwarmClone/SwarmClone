from enum import Enum
from typing import Dict, Tuple, List

from config.global_config import global_config

class ModuleType(Enum):
    LLM = (0, "LLM", global_config.llm.port)
    ASR = (1, "ASR", global_config.asr.port)
    TTS = (2, "TTS", global_config.tts.port)
    FRONTEND = (3, "FRONTEND", global_config.unity_frontend.port)
    CHAT = (4, "CHAT", global_config.chat.port)

    def __init__(self, idx: int, name: str, port: int):
        self.idx = idx
        self.display_name = name
        self.port = port

CONNECTION_TABLE: Dict[ModuleType, Tuple[List[ModuleType], List[ModuleType]]] = {
    ModuleType.LLM: (
        [ModuleType.TTS, ModuleType.FRONTEND],
        [ModuleType.TTS, ModuleType.FRONTEND]
    ),
    ModuleType.ASR: (
        [ModuleType.LLM, ModuleType.TTS, ModuleType.FRONTEND],
        [ModuleType.LLM, ModuleType.FRONTEND]
    ),
    ModuleType.TTS: (
        [ModuleType.LLM, ModuleType.FRONTEND],
        [ModuleType.LLM, ModuleType.FRONTEND]
    ),
    ModuleType.CHAT: ([], [ModuleType.LLM, ModuleType.FRONTEND])
}