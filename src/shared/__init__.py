# SwarmClone Backend - 共享模块

"""
本包包含系统范围内共享的类型定义、常量和工具函数
"""

from shared.types import (
    ModuleCategory,
    ModuleState,
    PlatformType,
    MessageType,
    DanmakuMessage,
    GiftMessage,
    FollowMessage,
    AIResponse,
    TTSRequest,
    MotionCommand,
    StreamStatus,
    ModuleInfo,
    ConfigValue,
    EventHandler,
    ModuleConfig,
)

from shared.constants import (
    SYSTEM_NAME,
    SYSTEM_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    Events,
    ConfigKeys,
    ErrorCodes,
    Platforms,
    Emotions,
    Defaults,
    Paths,
)

__all__ = [
    # 类型
    "ModuleCategory",
    "ModuleState",
    "PlatformType",
    "MessageType",
    "DanmakuMessage",
    "GiftMessage",
    "FollowMessage",
    "AIResponse",
    "TTSRequest",
    "MotionCommand",
    "StreamStatus",
    "ModuleInfo",
    "ConfigValue",
    "EventHandler",
    "ModuleConfig",
    
    # 常量
    "SYSTEM_NAME",
    "SYSTEM_VERSION",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "Events",
    "ConfigKeys",
    "ErrorCodes",
    "Platforms",
    "Emotions",
    "Defaults",
    "Paths",
]
