from enum import Enum

class MessageType(Enum):
    SIGNAL = "SIGNAL"
    DATA = "DATA"

class ModuleRoles(Enum):
    # 输出模块
    LLM = "LLM"
    TTS = "TTS"
    FRONTEND = "FRONTEND"

    # 输入模块
    ASR = "ASR"
    CHAT = "CHAT"

    # 其他模块
    PLUGIN = "PLUGIN"

    # 主控（并非模块，但是为了向其他模块发送消息，必须要有角色）
    CONTROLLER = "CONTROLLER"
