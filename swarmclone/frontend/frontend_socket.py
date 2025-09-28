import json
import base64
from typing import Any
from swarmclone.module_bootstrap import *

@dataclass
class FrontendSocketConfig(ModuleConfig):
    host: str = field(default="0.0.0.0", metadata={
        "required": False,
        "desc": "监听地址，默认监听所有地址，如需仅监听本地地址则设置为127.0.0.1"
    })
    port: int = field(default=8002, metadata={
        "required": False,
        "desc": "监听端口，最好不要改"
    })
    sep: str = field(default="%SEP%", metadata={
        "required": False,
        "desc": "消息分隔符，最好不要改"
    })

class FrontendSocket(ModuleBase):
    """连接到Unity前端的接口模块"""
    role: ModuleRoles = ModuleRoles.FRONTEND
    config_class = FrontendSocketConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.clientdict: dict[int, asyncio.StreamWriter] = {}
        self.server: asyncio.Server | None = None

    async def run(self):
        loop = asyncio.get_running_loop()
        self.server = await asyncio.start_server(
            self.handle_client,
            self.config.host,
            port=self.config.port
        )
        loop.create_task(self.send_to_frontend())
        async with self.server:
            await self.server.serve_forever()
    
    async def send_to_frontend(self):
        while True:
            task = await self.task_queue.get()
            print(type(task))
            to_remove = []
            message = self.load(task)
            for addr, client in self.clientdict.items():
                try:
                    client.write(message.encode('utf-8'))
                    await client.drain()
                    print(f"消息已发送给 {addr}")
                except ConnectionResetError:
                    print(f"客户端 {addr} 已断开连接")
                    client.close()
                    to_remove.append(addr)
            for addr in to_remove:
                del self.clientdict[addr]

    async def handle_client(self, reader:asyncio.StreamReader, writer:asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        print(f"客户端已连接：{addr}")
        self.clientdict[addr[1]] = writer
        while True:
            data = await reader.read(1024)
            print(f"消息来自：{addr}")
            if not data:
                break
            message = json.loads(data.decode(), object_hook=dict[str, Any])
            if message["message_type"] == "Signal":
                await self.results_queue.put(AudioFinished(self))

    def load(self, task: Message) -> str:
        d = {
            "message_type": task.message_type.value,
            "source": task.source.role.value,
            **task.get_value(self)
        }
        if isinstance(task, TTSAlignedAudio):
            assert isinstance(d["data"], bytes)
            d["data"] = base64.b64encode(d["data"]).decode('utf-8')
        massage = (
            json.dumps(d).replace(self.config.sep, "") + # 防止在不应出现的地方出现分隔符
            self.config.sep
        )
        return massage

__all__ = [
    "FrontendSocket"
]
