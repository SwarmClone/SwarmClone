from __future__ import annotations # 为了延迟注解评估

from typing import TYPE_CHECKING, Any
from .constants import MessageType, ModuleRoles

if TYPE_CHECKING:
    from .module_manager import ModuleBase  # 使用延迟导入解决循环依赖

class Message:
    def __init__(self, message_type: MessageType,
                 source: ModuleBase, destinations: list[ModuleRoles],
                 **kwargs: Any):
        self.message_type: MessageType = message_type # 消息类型，数据型/信号型
        self.kwargs: dict[str, Any] = kwargs # 消息内容
        self.source: ModuleBase = source # 消息来源，发送者对象
        self.destinations: list[ModuleRoles] = destinations # 消息目标，发送到哪几个角色中 ## TODO：支持精确到模块的消息目标
        print(f"{source} -> {self} -> {destinations}")
    
    def __repr__(self):
        kwrepr = "{"
        for k, v in self.kwargs.items():
            if len(repr(v)) > 50:
                v = repr(v)[:50] + "..."
            kwrepr += f"{k}: {v}, "
        kwrepr = kwrepr[:-2] + "}"
        return f"{self.message_type.value} {kwrepr}"
    
    def get_value(self, getter: ModuleBase) -> dict[str, Any]:
        if not getter.role in self.destinations:
            print(f"{getter} <x {self} (-> {[destination.value for destination in self.destinations]})")
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
    语音识别信息
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
    def __init__(self, source: ModuleBase, content: str, id: str, emotion: dict[str, float]):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.FRONTEND, ModuleRoles.TTS],
            content=content,
            id=id,
            emotion=emotion
        )

class AudioFinished(Message):
    """
    音频播放完毕信号
    """
    def __init__(self, source: ModuleBase):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.LLM],
            name="AudioFinished"
        )
 
class TTSAlignedAudio(Message):
    """
    TTS 音频
    .id：消息的 id（uuid）
    .audio_data：bytes 音频数据
    .align_data：对齐数据
    """
    def __init__(self, 
                 source: ModuleBase, 
                 id: str, 
                 audio_data: bytes, 
                 align_data: list[dict[str, str | float]]
                 ):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.FRONTEND],
            id=id,
            data=audio_data,
            align_data=align_data
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

class SongInfo(Message):
    """
    歌曲信息
    """
    def __init__(self, source: ModuleBase, song_id: str, song_path: str, subtitle_path: str):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.FRONTEND, ModuleRoles.LLM],
            song_id=song_id,
            song_path=song_path,
            subtitle_path=subtitle_path
        )

class ReadyToSing(Message):
    """
    开始播放歌曲
    """
    def __init__(self, source: ModuleBase, song_id: str):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.FRONTEND],
            song_id=song_id
        )

class FinishedSinging(Message):
    """
    完成播放歌曲
    """
    def __init__(self, source: ModuleBase):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.LLM]
        )
