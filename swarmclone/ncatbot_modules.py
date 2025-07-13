from ncatbot.core import BotClient, GroupMessage
from threading import Lock
from .constants import *
from .messages import *
from .modules import *
from .config import Config
import asyncio
import random


class NCatBotChat(ModuleBase):
    """从NCatBot获取消息并作为Chat信息发送给主控"""
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.CHAT, "NCatBotChat", config)
        lock = Lock()
        lock.acquire()
        self.bot = BotClient()
        assert isinstance((target_group_id := config.chat.ncatbot.target_group_id), str)
        self.target_group_id = target_group_id
        assert isinstance((bot_id := config.chat.ncatbot.bot_id), str)
        self.bot_id = bot_id
        assert isinstance((root_id := config.chat.ncatbot.root_id), str)
        self.root_id = root_id
        self.api = self.bot.run_blocking(bt_uin=bot_id, root=root_id)

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

class NCatBotFrontend(ModuleBase):
    """接受LLM的信息并发送到目标群中"""
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.FRONTEND, "NCatBotFrontend", config)
        self.llm_buffer = ""
    
    async def process_task(self, task: Message | None) -> Message | None:
        if isinstance(task, LLMMessage):
            self.llm_buffer += task.get_value(self).get("content", "")
        elif isinstance(task, LLMEOS) and self.llm_buffer:
            await asyncio.sleep(random.choice([0.1, 0.5, 0.7])) # 防止被发现是机器人然后封号
            await self.results_queue.put(NCatBotLLMMessage(self, self.llm_buffer.strip()))
            await self.results_queue.put(AudioFinished(self)) # 防止LLM等待不存在的TTS
            self.llm_buffer = ""

class NCatBotLLMMessage(Message):
    def __init__(self, source: NCatBotFrontend, content: str):
        super().__init__(MessageType.DATA, source, [ModuleRoles.CHAT], content=content)
