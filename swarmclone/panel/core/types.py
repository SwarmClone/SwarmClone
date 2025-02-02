from enum import Enum
from typing import Dict, Tuple, List
from loguru import logger as log

from . import config

class ModuleType(Enum):
    LLM = (0, "LLM", config.LLM_PORT)
    ASR = (1, "ASR", config.ASR_PORT)
    TTS = (2, "TTS", config.TTS_PORT)
    FRONTEND = (3, "FRONTEND", config.FRONTEND_PORT)
    CHAT = (4, "CHAT", config.CHAT_PORT)

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