from bilibili_api import live,  Credential
 
from .config import Config
from .modules import ModuleRoles, ModuleBase
from .messages import *

class BiliBiliChat(ModuleBase):
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.CHAT, "BiliBiliChat", config)
        assert isinstance((sessdata := config.chat.bilibili.credential.sessdata), str)
        assert isinstance((bili_jct := config.chat.bilibili.credential.bili_jct), str)
        assert isinstance((buvid3 := config.chat.bilibili.credential.buvid3), str)
        assert isinstance((dedeuserid := config.chat.bilibili.credential.dedeuserid), str)
        assert isinstance((ac_time_value := config.chat.bilibili.credential.ac_time_value), str)
        
        self.credential: Credential = Credential(
            sessdata=sessdata or None,
            bili_jct=bili_jct or None,
            buvid3=buvid3 or None,
            dedeuserid=dedeuserid or None,
            ac_time_value=ac_time_value or None
        )
        assert isinstance(config.chat.bilibili.live_room_id, int)
        self.room: live.LiveDanmaku = live.LiveDanmaku(config.chat.bilibili.live_room_id, credential=self.credential)
        self.register_chat()
    
    def register_chat(self):
        @self.room.on('DANMU_MSG')
        async def on_danmaku(event: dict[str, Any]):
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
