from enum import Enum

class MessageType(Enum):
    SIGNAL = "Signal"
    DATA = "Data"

class ModuleRoles(Enum):
    # 输出模块
    LLM = "LLM"
    TTS = "TTS"
    FRONTEND = "Frontend"

    # 输入模块
    ASR = "ASR"
    CHAT = "Chat"

    # 其他模块
    PLUGIN = "Plugin"

    # 主控（并非模块，但是为了向其他模块发送消息，必须要有角色）
    CONTROLLER = "Controller"

class LLMState(Enum):
    IDLE = "Idle"
    GENERATING = "Generating"
    WAITING4TTS = "Waiting for TTS"
    WAITING4ASR = "Waiting for ASR"
    SINGING = "Singing"
