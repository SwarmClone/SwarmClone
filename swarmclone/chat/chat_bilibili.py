from dataclasses import dataclass, field
from swarmclone.modules import *
from swarmclone.messages import *

@dataclass
class BiliBiliChatConfig(ModuleConfig):
    live_room_id: int = field(default=0, metadata={
        "required": True,
        "desc": "目标B站直播间ID"
    })
    sessdata: str = field(default="", metadata={
        "required": False,
        "desc": "见https://nemo2011.github.io/bilibili-api/#/get-credential，可不填"
    })
    bili_jct: str = field(default="", metadata={
        "required": False,
        "desc": "见https://nemo2011.github.io/bilibili-api/#/get-credential，可不填"
    })
    buvid3: str = field(default="", metadata={
        "required": False,
        "desc": "见https://nemo2011.github.io/bilibili-api/#/get-credential，可不填"
    })
    dedeuserid: str = field(default="", metadata={
        "required": False,
        "desc": "见https://nemo2011.github.io/bilibili-api/#/get-credential，可不填"
    })
    ac_time_value: str = field(default="", metadata={
        "required": False,
        "desc": "见https://nemo2011.github.io/bilibili-api/#/get-credential，可不填"
    })

class BiliBiliChat(ModuleBase):
    role: ModuleRoles = ModuleRoles.CHAT
    config_class = BiliBiliChatConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        try:
            from bilibili_api import live, Credential
        except ImportError:
            raise ImportError("请安装bilibili-api-python")
        self.credential: Credential = Credential(
            sessdata=self.config.sessdata or None,
            bili_jct=self.config.bili_jct or None,
            buvid3=self.config.buvid3 or None,
            dedeuserid=self.config.dedeuserid or None,
            ac_time_value=self.config.ac_time_value or None,
        )
        self.room: live.LiveDanmaku = live.LiveDanmaku(self.config.live_room_id, credential=self.credential)
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
