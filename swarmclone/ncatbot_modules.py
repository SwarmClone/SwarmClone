from __future__ import annotations
try:
    from ncatbot.core import BotClient, GroupMessage
    available = True
except ImportError:
    available = False
from threading import Lock
from dataclasses import dataclass, field
from .constants import *
from .messages import *
from .modules import *
import asyncio
import random

@dataclass
class NCatBotChatConfig(ModuleConfig):
    target_group_id: str = field(default="", metadata={
        "required": True,
        "desc": "模板群号"
    })
    bot_id: str = field(default="", metadata={
        "required": True,
        "desc": "机器人QQ号"
    })
    root_id: str = field(default="", metadata={
        "required": True,
        "desc": "管理员QQ号"
    })

class NCatBotChat(ModuleBase):
    role: ModuleRoles = ModuleRoles.CHAT
    config_class = NCatBotChatConfig
    """从NCatBot获取消息并作为Chat信息发送给主控"""
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        assert available, "NCatBotChat requires ncatbot to be installed"
        lock = Lock()
        lock.acquire()
        self.bot = BotClient()
        self.target_group_id = self.config.target_group_id
        self.bot_id = self.config.bot_id
        self.root_id = self.config.root_id
        self.api = self.bot.run_blocking(bt_uin=self.bot_id, root=self.root_id)

        # 注册回调事件
        self.bot.add_group_event_handler(self.on_group_msg)
    
    async def process_task(self, task: Message | None) -> Message | None:
        if isinstance(task, NCatBotLLMMessage):
            await self.api.post_group_msg(self.target_group_id, task.get_value(self)["content"])
    
    async def on_group_msg(self, msg: GroupMessage):
        do_accept = False
        text = ""
        sender = msg.sender
        if hasattr(sender, "card"):
            user = sender.card
        else:
            user = sender.nickname
        if hasattr(msg, "group_id") and msg.group_id == self.target_group_id:
            do_accept = True
        for msg_section in msg.message:
            match msg_section:
                # 仅在明确提到自己时进行回复
                case {'type': 'at', 'data': {'qq': at_qq}}:
                    do_accept = at_qq == self.bot_id
                case {'type': 'reply', 'data': {'qq': reply_qq}}:
                    do_accept = reply_qq == self.bot_id
                # 因不一定at在前还是后，无论是否提到自己都读取消息文本
                case {'type': 'text', 'data': {'text': content}}:
                    text += content
                case {'type': 'face', 'data': {'id': _face_id, 'raw': {
                        'faceIndex': _face_index, 'faceText': face_text, 'faceType': _face_type
                    }}}:
                    text += face_text
                case _: ...
        if do_accept and text:
            message = ChatMessage(
                source=self,
                user=user,
                content=text
            )
            await self.results_queue.put(message)
            text = ""

@dataclass
class NCatBotFrontendConfig(ModuleConfig):
    sleeptime_min: int | float = field(default=0, metadata={
        "required": False,
        "desc": "模型回复随机延迟最小值",
        "min": 0,
        "max": 10,
        "step": 0.1
    })
    sleeptime_max: int | float = field(default=0, metadata={
        "required": False,
        "desc": "模型回复随机延迟最大值",
        "min": 0,
        "max": 10,
        "step": 0.1
    })

class NCatBotFrontend(ModuleBase):
    role: ModuleRoles = ModuleRoles.FRONTEND
    config_class = NCatBotFrontendConfig
    config: config_class
    """接受LLM的信息并发送到目标群中"""
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.llm_buffer = ""
    
    def get_sleep_time(self) -> float:
        return random.random() * (self.config.sleeptime_max - self.config.sleeptime_min) + self.config.sleeptime_min
    
    async def process_task(self, task: Message | None) -> Message | None:
        if isinstance(task, LLMMessage):
            self.llm_buffer += task.get_value(self).get("content", "")
        elif isinstance(task, LLMEOS) and self.llm_buffer:
            await asyncio.sleep(self.get_sleep_time()) # 防止被发现是机器人然后封号
            await self.results_queue.put(NCatBotLLMMessage(self, self.llm_buffer.strip()))
            await self.results_queue.put(AudioFinished(self)) # 防止LLM等待不存在的TTS
            self.llm_buffer = ""

class NCatBotLLMMessage(Message):
    def __init__(self, source: NCatBotFrontend, content: str):
        super().__init__(MessageType.DATA, source, [ModuleRoles.CHAT], content=content)
