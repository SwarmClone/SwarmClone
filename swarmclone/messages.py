from __future__ import annotations # 为了延迟注解评估

import time
from typing import TYPE_CHECKING, Any, TypeVar, Generic, TypedDict, cast
from collections.abc import Mapping
from swarmclone.constants import *
from swarmclone.utils import *

if TYPE_CHECKING:
    from swarmclone.module_manager import ModuleBase  # 使用延迟导入解决循环依赖

T = TypeVar('T', bound=Mapping[str, Any])

class Message(Generic[T]):
    def __init__(self, message_type: MessageType,
                 source: ModuleBase, destinations: list[ModuleRoles | type],
                 **kwargs: Any):
        self.message_type: MessageType = message_type # 消息类型，数据型/信号型
        self.kwargs: T = kwargs # 消息内容
        self.source: ModuleBase = source # 消息来源，发送者对象
        self.destinations: list[ModuleRoles | type] = destinations # 消息目标，发送到哪几个角色/模块中
        self.getters: list[dict[str, str | int]] = [] # 获取了信息的模块名
        print(f"{source} -> {self} -> {destinations}")
        self.send_time = int(time.time())
    
    def __repr__(self):
        kwrepr = "{"
        for k, v in self.kwargs.items():
            if len(repr(v)) > 50:
                v = repr(v)[:50] + "..."
            kwrepr += f"{k}: {v}, "
        kwrepr = kwrepr[:-2] + "}"
        return f"{self.message_type.value} {kwrepr}"
    
    def get_value(self, getter: ModuleBase | None = None) -> T:
        """
        获取消息内容，若指定了获取者，则检查获取者是否为有效的获取者，若有效则返回消息内容，否则返回空字典；若未指定获取者则跳过检查。
        """
        if getter is None:
            return self.kwargs
        
        getter_valid = False
        if getter.role in self.destinations:
            getter_valid = True
        else:
            for destination in self.destinations:
                getter_valid = isinstance(destination, type) and isinstance(getter, destination)
                if getter_valid:
                    break
        if not getter_valid:
            print(f"{getter} <x {self} (-> {[destination.value if isinstance(destination, ModuleRoles) else get_type_name(destination) for destination in self.destinations]})")
            return T()
        print(f"{getter} <- {self}")
        self.getters.append({
            'name': getter.name,
            'time': int(time.time())
        })
        return self.kwargs
    
    def __getitem__(self, key: str) -> Any:
        return self.get_value()[key]
    
    def __contains__(self, key: str) -> bool:
        return key in self.get_value()
    
    def __setitem__(self, key: str, value: Any):
        raise RuntimeError("消息内容不应被修改！")
    
    def __delitem__(self, key: str):
        raise RuntimeError("消息内容不应被修改！")
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.get_value().get(key, default)
    
    def get_dict_repr(self) -> dict[str, Any]:
        """
        {
            "message_name": "【信息名】",
            "send_time": 【发送时间戳，整数】,
            "message_type": "【信息类型，DATA或者SIGNAL】",
            "message_source": "【消息来源模块名】",
            "message_destinations": [
                "【消息目的地名】"
            ],
            "message": [
                {"key": "键", "value": "值"},...
            ],
            "getters": [
                {"name": "【获取者名】", "time": 【获取时间戳，整数】},...
            ]
        }
        """
        return {
            "message_name": get_type_name(self),
            "send_time": self.send_time,
            "message_type": self.message_type.value,
            "message_source": self.source.name,
            "message_destinations": [
                        destination.value
                    if isinstance(destination, ModuleRoles)
                    else
                        get_type_name(destination)
                for destination in self.destinations
            ],
            "message": [
                {"key": k, "value": repr(v)}
                for k, v in self.kwargs.items()
            ],
            "getters": self.getters
        }

class SIGContent(TypedDict):
    name: str

class ASRActivated(Message[SIGContent]):
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
class ASRcoutent(TypedDict):
    speaker_name: str
    message: str

class ASRMessage(Message[ASRcoutent]):
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

class LLMEOS(Message[SIGContent]):
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

class LLMcontent(TypedDict):
    content: str
    id: str
    emotion: dict[str, float]

class LLMMessage(Message[LLMcontent]):
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

class AudioFinished(Message[SIGContent]):
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

class TTSAlignedcontent(TypedDict):
    id: str
    data: bytes
    align_data: list[dict[str, str | float]]

class TTSAlignedAudio(Message[TTSAlignedcontent]):
    """
    TTS 音频
    .id：消息的 id（uuid）
    .audio_data：bytes 音频数据 !! 必须是 wav 格式 !!
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

class Chatcontent(TypedDict):
    user: str
    content: str

class ChatMessage(Message[Chatcontent]):
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
class MultiChatcontent(TypedDict):
    messages: list[Chatcontent] 

class MultiChatMessage(Message[MultiChatcontent]):
    """
    多用户聊天信息
    .messages: [
        {"user": "用户名", "content": "消息内容"},...
    ]
    """
    def __init__(self, source: ModuleBase, messages: list[Chatcontent]):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.LLM, ModuleRoles.FRONTEND],
            messages=messages
        )

class SongInfoContent(TypedDict):
    song_id: str
    song_path: str
    vocal_path: str
    subtitle_path: str
    
class SongInfo(Message[SongInfoContent]):
    """
    歌曲信息
    .song_id: 歌曲 id
    .song_path: 歌曲路径
    .vocal_path:  纯人声音频路径
    .subtitle_path: 字幕路径
    **所有音频必须是 wav 格式，字幕必须是 srt 格式**
    """
    def __init__(self, source: ModuleBase, song_id: str, song_path: str, vocal_path: str, subtitle_path: str):
        assert song_path.endswith('.wav'), "歌曲路径必须是 wav 格式"
        assert vocal_path.endswith('.wav'), "纯人声音频路径必须是 wav 格式"
        assert subtitle_path.endswith('.srt'), "字幕路径必须是 srt 格式"
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.FRONTEND, ModuleRoles.LLM],
            song_id=song_id,
            song_path=song_path,
            vocal_path=vocal_path,
            subtitle_path=subtitle_path
        )
class SingSigcontent(TypedDict):
    song_id: str

class ReadyToSing(Message[SingSigcontent]):
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

class FinishedSinging(Message[SIGContent]):
    """
    完成播放歌曲
    """
    def __init__(self, source: ModuleBase):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.LLM]
        )
class Actioncontent(TypedDict):
    action_ids: list[str]

class ActiveAction(Message[Actioncontent]):
    """
    激活一个动作
    .action_ids: 要激活的动作名称列表，名称即为 action 动作文件中的 name 属性
    """
    def __init__(self, source: ModuleBase, action_ids: list[str]):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.PARAM_CONTROLLER],
            action_ids = action_ids
        )
class ParametersUpdatecontent(TypedDict):
    updates: dict[str,float]

class ParametersUpdate(Message[ParametersUpdatecontent]):
    """
    更新参数
    .updates: 参数字典，键为参数名称，值为参数值
    """
    def __init__(self, source: ModuleBase, updates: dict[str,float]):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.FRONTEND],
            updates = updates
        )
class providerRequestcontent(TypedDict):
    messages: list[dict[str, str]]
    stream: bool

class ProviderRequest(Message[providerRequestcontent]):
    """
    向模型提供者发出一条请求
    .messages: 消息列表，每个消息为一个字典，包含 role 和 content 两个键
    .stream: 是否流式传输，默认 False
    .model: 模型选择，默认 Providers.PRIMARY
    """
    def __init__(
            self,
            source: ModuleBase,
            messages: list[dict[str, str]],
            stream: bool = False,
            model: Providers = Providers.PRIMARY
        ):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.PRIMARY_PROVIDER if model == Providers.PRIMARY else ModuleRoles.SECONDARY_PROVIDER],
            messages=messages,
            stream=stream
        )
class ProviderRequestcontent(TypedDict):
    content: str
    delta: str
    end: bool

class ProviderResponseNonStream(Message[ProviderRequestcontent]):
    """
    模型提供者的非流式响应
    .content: 模型提供者的响应内容
    """
    def __init__(
            self,
            source: ModuleBase,
            content: str,
            destination: type[ModuleBase] # 响应应当精准发给调用者而不是广播到某个角色
        ):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[destination],
            content=content
        )

class ProviderResponseStream(Message[ProviderRequestcontent]):
    """
    模型提供者的流式响应
    .delta: 模型提供者的增量响应内容
    .end: 响应是否结束
    """
    def __init__(
            self,
            source: ModuleBase,
            delta: str,
            end: bool,
            destination: type[ModuleBase] # 响应应当精准发给调用者而不是广播到某个角色
        ):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[destination],
            delta=delta,
            end=end
        )


__all__ = [
    "Message",
    "ASRActivated",
    "ASRMessage",
    "LLMEOS",
    "LLMMessage",
    "AudioFinished",
    "TTSAlignedAudio",
    "ChatMessage",
    "MultiChatMessage",
    "SongInfo",
    "ReadyToSing",
    "FinishedSinging",
    "ActiveAction",
    "ParametersUpdate",
    "ProviderRequest",
    "ProviderResponseNonStream",
    "ProviderResponseStream",
]