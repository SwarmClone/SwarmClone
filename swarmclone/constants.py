from enum import Enum

class MessageType(Enum):
    SIGNAL = "Signal"
    DATA = "Data"

class ModuleRoles(Enum):
    # 输出模块
    LLM = "LLM"
    TTS = "TTS"
    FRONTEND = "Frontend"
    PARAM_CONTROLLER = "Parameter Controller"

    # 输入模块
    ASR = "ASR"
    CHAT = "Chat"

    # 其他模块
    PLUGIN = "Plugin"

    # 主控（并非模块，但是为了向其他模块发送消息，必须要有角色）
    CONTROLLER = "Controller"

    # 模型服务提供者
    PRIMARY_PROVIDER = "Primary Provider"
    SECONDARY_PROVIDER = "Secondary Provider"

    # 未指定（仅用于基类，任何未指定角色的模块在注册时都会引发错误）
    UNSPECIFIED = "Unspecified"

class LLMState(Enum):
    IDLE = "Idle"
    GENERATING = "Generating"
    WAITING4TTS = "Waiting for TTS"
    WAITING4ASR = "Waiting for ASR"
    SINGING = "Singing"

class Providers(Enum):
    PRIMARY = "Primary Provider"
    SECONDARY = "Secondary Provider"

__all__ = [
    "MessageType",
    "ModuleRoles",
    "LLMState",
    "Providers"
]
