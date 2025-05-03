from __future__ import annotations # 为了延迟注解评估

from enum import Enum
from typing import TYPE_CHECKING
from .constants import MessageType, ModuleRoles

if TYPE_CHECKING:
    from .modules import ModuleBase

class Message:
    def __init__(self, message_type: MessageType,
                 source: ModuleBase, destinations: list[ModuleRoles],
                 **kwargs):
        self.message_type = message_type
        self.kwargs = kwargs
        self.source = source
        self.destinations = destinations
        print(f"{source} -> {self} -> {destinations}")
    
    def __repr__(self):
        return f"{self.message_type.value} {self.kwargs}"
    
    def get_value(self, getter: ModuleBase) -> dict:
        if not getter.role in self.destinations:
            print(f"{getter} <x {self} (-> {self.destinations})")
            return {}
        print(f"{getter} <- {self}")
        return self.kwargs

class ASRActivated(Message):
    """
    语音活动激活信号，用于打断正在播放的语音和正在生成的回复
    """
    def __init__(self, source: ModuleBase):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.TTS, ModuleRoles.FRONTEND, ModuleRoles.LLM],
            name="ASRActivated"
        )

class ASRMessage(Message):
    """
    语音识别得到的信息
    .speaker_name: 说话人
    .message: 语音识别得到的信息
    """
    def __init__(self, source: ModuleBase, speaker_name: str, message: str):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.LLM, ModuleRoles.FRONTEND],
            speaker_name=speaker_name,
            message=message
        )

class LLMEOS(Message):
    """
    LLM 生成结束信号
    """
    def __init__(self, source: ModuleBase):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.FRONTEND, ModuleRoles.TTS],
            name="LLMEOS"
        )

class LLMMessage(Message):
    """
    LLM 生成的信息
    .content：生成的信息
    .id：消息的 id（uuid）
    .emotion：情感信息。含有like disgust anger happy sad neutral五个情感的概率
    """
    def __init__(self, source: ModuleBase, content: str, id: str, emotion: dict):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.FRONTEND, ModuleRoles.TTS],
            content=content,
            id=id,
            emotion=emotion
        )

class TTSFinished(Message):
    """
    TTS 结束信号
    """
    def __init__(self, source: ModuleBase):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.FRONTEND, ModuleRoles.LLM],
            name="TTSFinished"
        )

class TTSAlignment(Message):
    """
    TTS 对齐信息
    .id：消息的 id（uuid）
    .token：当前 token
    .duration：当前 token 的时长
    """
    def __init__(self, source: ModuleBase, id: str, token: str, duration: float):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.FRONTEND],
            id=id,
            token=token,
            duration=duration
        )

class TTSAudio(Message):
    """
    TTS 对齐信息
    .id：消息的 id（uuid）
    .audio_data：bytes 音频数据
    """
    def __init__(self, source: ModuleBase, id: str, audio_data: bytes):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.FRONTEND],
            id=id,
            data=audio_data
        )

class ChatMessage(Message):
    """
    聊天信息
    .user：用户名
    .content：消息内容
    """
    def __init__(self, source: ModuleBase, user: str, content: str):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.LLM, ModuleRoles.FRONTEND],
            user=user,
            content=content
        )
