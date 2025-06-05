import asyncio
import json
import base64
from typing import Any
from .config import Config
from .modules import ModuleRoles, ModuleBase
from .messages import *

class FrontendSocket(ModuleBase):
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.FRONTEND, "FrontendSocket", config)
        self.clientdict: dict[int, asyncio.StreamWriter] = {}
        self.server: asyncio.Server | None = None

    async def run(self):
        assert isinstance((host := self.config.panel.server.host), str)
        assert isinstance((port := self.config.panel.frontend.port), int)
        loop = asyncio.get_running_loop()
        self.server = await asyncio.start_server(
            self.handle_client,
            host, 
            port
        )
        loop.create_task(self.SendToFrontend())
        async with self.server:
            await self.server.serve_forever()
    
    async def SendToFrontend(self):
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
        assert isinstance((separator := self.config.panel.server.requests_separator), str)
        massage = (
            json.dumps(d).replace(separator, "") + # 防止在不应出现的地方出现分隔符
            separator
        )
        return massage
