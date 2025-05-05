import asyncio
import json
import aiohttp
from swarmclone.config import config
from ..modules import ModuleRoles, ModuleBase
from ..messages import *

class frontend2(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.FRONTEND, "Frontend2")
        self.urldict:dict[str,str] = {
                "unity": f"http://{config.panel.server.host}:{config.panel.frontend.port}/",
                #"flask": f"http://{config.panel.server.host}:5000/"
        }

    async def run(self):
        loop = asyncio.get_running_loop()
        while True:
            try:
                task = self.task_queue.get_nowait()
            except asyncio.QueueEmpty:
                task = None
            for address, url in self.urldict.items():
                loop.create_task(self.process_task(url, task))
            await asyncio.sleep(0.01)
        
    async def process_task(self, url:str, task: Message | None):
        if(await self.is_url_accessible(url)):
                headers = {
                    'source': task.source.role.value,
                    'message_type': task.message_type.value
                }
                message = self.load(task)
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=message["json"] ,data=message["data"]) as response:
                        print(f"Response status code: {response.status}")
                        print(f"Response content: {await response.text()}")
        else:
            print(f"{url} 不可访问")
            
    async def is_url_accessible(self, url: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, allow_redirects=True, timeout=5.0) as response:
                    return response.status == 200
        except aiohttp.ClientError:
            return False
        except asyncio.TimeoutError:
            return False
    
    def load(self, task:Message) -> dict[str, str|bytes]:
        dict = {**task.kwargs}
        massage = {}
        if(not isinstance(task, TTSAudio)):
            massage["data"] = dict["data"]
            del dict["data"]
        else:
            massage["data"] = None
        massage["json"] = (json.dumps(dict).replace(config.panel.server.requests_separator, "") + # 防止在不应出现的地方出现分隔符
        config.panel.server.requests_separator)
        return(massage)
    
