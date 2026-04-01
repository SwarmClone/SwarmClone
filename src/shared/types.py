# SwarmClone Backend - 共享类型定义

"""
本模块包含系统范围内共享的类型定义和数据类
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class ModuleCategory(str, Enum):
    """模块分类枚举"""
    CORE = "core"
    LIVE = "live"
    AGENT = "agent"
    VOICE = "voice"
    MOTION = "motion"
    MODEL = "model"


class ModuleState(str, Enum):
    """模块运行状态"""
    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"


class PlatformType(str, Enum):
    """直播平台类型"""
    BILIBILI = "bilibili"
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    DOUYIN = "douyin"
    HUYA = "huya"


class MessageType(str, Enum):
    """消息类型"""
    DANMAKU = "danmaku"
    GIFT = "gift"
    FOLLOW = "follow"
    JOIN = "join"
    COMMAND = "command"
    SYSTEM = "system"


@dataclass
class DanmakuMessage:
    """弹幕消息数据结构"""
    user_id: str
    username: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    platform: PlatformType = PlatformType.BILIBILI
    is_moderator: bool = False
    is_vip: bool = False
    medal_level: int = 0
    medal_name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "platform": self.platform.value,
            "is_moderator": self.is_moderator,
            "is_vip": self.is_vip,
            "medal_level": self.medal_level,
            "medal_name": self.medal_name
        }


@dataclass
class GiftMessage:
    """礼物消息数据结构"""
    user_id: str
    username: str
    gift_name: str
    gift_count: int
    gift_price: float  # 单价（电池/金瓜子等）
    total_price: float = field(init=False)
    timestamp: datetime = field(default_factory=datetime.now)
    platform: PlatformType = PlatformType.BILIBILI
    
    def __post_init__(self):
        self.total_price = self.gift_price * self.gift_count
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "gift_name": self.gift_name,
            "gift_count": self.gift_count,
            "gift_price": self.gift_price,
            "total_price": self.total_price,
            "timestamp": self.timestamp.isoformat(),
            "platform": self.platform.value
        }


@dataclass
class FollowMessage:
    """关注消息数据结构"""
    user_id: str
    username: str
    timestamp: datetime = field(default_factory=datetime.now)
    platform: PlatformType = PlatformType.BILIBILI
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "timestamp": self.timestamp.isoformat(),
            "platform": self.platform.value
        }


@dataclass
class AIResponse:
    """AI 响应数据结构"""
    content: str
    emotion: str = "neutral"
    action_suggestion: Optional[str] = None
    voice_params: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "emotion": self.emotion,
            "action_suggestion": self.action_suggestion,
            "voice_params": self.voice_params,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class TTSRequest:
    """TTS 请求数据结构"""
    text: str
    speaker_id: str = "default"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    emotion: str = "neutral"
    callback_event: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "speaker_id": self.speaker_id,
            "speed": self.speed,
            "pitch": self.pitch,
            "volume": self.volume,
            "emotion": self.emotion,
            "callback_event": self.callback_event
        }


@dataclass
class MotionCommand:
    """动作控制命令"""
    command_type: str  # "expression", "gesture", "lip_sync", etc.
    parameters: Dict[str, Any]
    duration: float = 0.0  # 持续时间（秒），0 表示立即完成
    priority: int = 0  # 优先级，数字越大优先级越高
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_type": self.command_type,
            "parameters": self.parameters,
            "duration": self.duration,
            "priority": self.priority
        }


@dataclass
class StreamStatus:
    """直播状态信息"""
    is_live: bool = False
    title: str = ""
    viewer_count: int = 0
    danmaku_count: int = 0
    gift_count: int = 0
    follow_count: int = 0
    start_time: Optional[datetime] = None
    platform: PlatformType = PlatformType.BILIBILI
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_live": self.is_live,
            "title": self.title,
            "viewer_count": self.viewer_count,
            "danmaku_count": self.danmaku_count,
            "gift_count": self.gift_count,
            "follow_count": self.follow_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "platform": self.platform.value
        }


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    full_name: str
    category: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    state: ModuleState = ModuleState.UNINITIALIZED
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "category": self.category,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "state": self.state.value,
            "enabled": self.enabled
        }


# 类型别名
ConfigValue = Any
EventHandler = callable
ModuleConfig = Dict[str, ConfigValue]
