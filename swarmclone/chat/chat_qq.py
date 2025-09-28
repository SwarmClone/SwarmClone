from __future__ import annotations
from ncatbot.core import BotClient, GroupMessage
from swarmclone.module_bootstrap import *
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from swarmclone.frontend.frontend_qq import NCatBotFrontend

@dataclass
class NCatBotChatConfig(ModuleConfig):
    target_group_id: str = field(default="", metadata={
        "required": True,
        "desc": "目标群号"
    })
    bot_id: str = field(default="", metadata={
        "required": True,
        "desc": "机器人QQ号"
    })
    root_id: str = field(default="", metadata={
        "required": True,
        "desc": "管理员QQ号"
    })
    keyword1: str = field(default="", metadata={
        "required": False,
        "desc": "激活关键词1，在对话中包含这个词时会触发回复"
    })
    keyword2: str = field(default="", metadata={
        "required": False,
        "desc": "激活关键词2"
    })
    keyword3: str = field(default="", metadata={
        "required": False,
        "desc": "激活关键词3"
    })

class NCatBotChat(ModuleBase):
    role: ModuleRoles = ModuleRoles.CHAT
    config_class = NCatBotChatConfig
    """从NCatBot获取消息并作为Chat信息发送给主控"""
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.bot = BotClient()
        self.target_group_id = self.config.target_group_id
        self.bot_id = self.config.bot_id
        self.root_id = self.config.root_id
        self.api = self.bot.run_blocking(bt_uin=self.bot_id, root=self.root_id)
        self.keywords: list[str] = [self.config.keyword1, self.config.keyword2, self.config.keyword3]
        self.messages_buffer: list[dict[str, str]] = []

        # 注册回调事件
        self.bot.add_group_event_handler(self.on_group_msg)
    
    async def run(self) -> None:
        try:
            await super().run()
        finally:
            self.bot.clean_up()
            del self.bot
    
    async def process_task(self, task: Message | None) -> Message | None:
        if isinstance(task, NCatBotLLMMessage):
            await self.api.post_group_msg(self.target_group_id, task.get_value(self)["content"])
    
    async def on_group_msg(self, msg: GroupMessage):
        if (not hasattr(msg, "group_id")) or str(msg.group_id) != self.target_group_id:
            return # 不是目标群，不处理
        do_accept = False
        text = ""
        sender = msg.sender
        if hasattr(sender, "card"):
            user = sender.card
        else:
            user = sender.nickname
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
                    text += face_text if face_text is not None else ""
                case _: ...
        self.messages_buffer.append({"user": user, "content": text})
        do_accept = do_accept or any(
            (x and x in text)
            for x in self.keywords
        ) # 是否有提到自己
        if do_accept and text:
            message = MultiChatMessage(
                source=self,
                messages=self.messages_buffer
            )
            self.messages_buffer = []
            await self.results_queue.put(message)
            text = ""

class NCatBotLLMMessage(Message):
    def __init__(self, source: NCatBotFrontend, content: str):
        super().__init__(MessageType.DATA, source, [NCatBotChat], content=content)

__all__ = ["NCatBotLLMMessage", "NCatBotChat"]