import asyncio
import json
import base64
 
from swarmclone.config import config
from ..modules import ModuleRoles, ModuleBase
from ..messages import *

class frontend(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.FRONTEND, "Frontend")
        self.clientdict:dict[int,asyncio.StreamWriter] = {}
        self.server = None

    async def run(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self.preprocess_tasks())
        self.server = await asyncio.start_server(self.handle_client,config.panel.server.host, config.panel.frontend.port)
        async with self.server:
            await self.server.serve_forever()
    
    async def preprocess_tasks(self):
        while(True):
            if(self.clientdict):
                task = await self.task_queue.get()
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
            else:
                await asyncio.sleep(0.01)

    def handle_client(self, reader:asyncio.StreamReader, writer:asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info('peername')
        print(f"客户端已连接：{addr}")
        self.clientdict[addr[1]]=writer
    
    def load(self, task:Message) -> str:
        dict = {
                "message_type": task.message_type.value,
                "source": task.source.role.value,
                **task.kwargs
            }
        if(isinstance(task, TTSAudio)):
            dict["data"] = base64.b64encode(dict["data"]).decode('utf-8')#UnicodeDecodeError: 'utf-8' codec can't decode byte 0x81 in position 1: invalid start byte
        massage = (json.dumps(dict).replace(config.panel.server.requests_separator, "") + # 防止在不应出现的地方出现分隔符
        config.panel.server.requests_separator)
        return(massage)
    
    async def process_task(self, task: Message | None) -> Message | None:
    # 不应被调用
        raise NotImplementedError