import asyncio
import json
from bilibili_api import live, sync, Credential
 
from .config import config
from .modules import ModuleRoles, ModuleBase
from .messages import *

class BiliBiliChat(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.CHAT, "BiliBiliChat")
        self.credential = Credential(
            sessdata=config.chat.bilibili.credential.sessdata or None,
            bili_jct=config.chat.bilibili.credential.bili_jct or None,
            buvid3=config.chat.bilibili.credential.buvid3 or None,
            dedeuserid=config.chat.bilibili.credential.dedeuseride or None,
            ac_time_value=config.chat.bilibili.credential.ac_time_value or None
        )
        self.room = live.LiveDanmaku(config.chat.bilibili.live_room_id, credential=self.credential)
        self.register_chat()
    
    def register_chat(self):
        @self.room.on('DANMU_MSG')
        async def on_danmaku(event):
            # 收到弹幕
            print(f"{(user := event['data']['info'][2][1])}: {(msg := event['data']['info'][1])}")
            await self.results_queue.put(
                ChatMessage(
                    source=self,
                    user=user,
                    content=msg,
                )
                        
            )

    async def run(self):
        await self.room.connect()
