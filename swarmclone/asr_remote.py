import json
import asyncio
from typing import Any
from .messages import *
from .modules import *
from .config import Config

class ASRRemote(ModuleBase):
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.ASR, "ASRRemote", config)
        self.server: asyncio.Server | None = None
        self.clientdict: dict[str, asyncio.StreamWriter] = {}
    
    async def run(self):
        assert isinstance(self.config.panel.server.host, str)
        assert isinstance(self.config.asr.port, int)
        
        self.server = await asyncio.start_server(
            self.handle_client,
            self.config.panel.server.host,
            self.config.asr.port,
            limit=10
        )
        async with self.server:
            await self.server.serve_forever()
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        print(f'ASR已连接：{addr}')
        self.clientdict[addr[1]] = writer
        loader = Loader(self.config)
        while True:
            data = await reader.read(1024)
            loader.update(data.decode())
            if (reqs := loader.get_requests()) and {'from':'asr', 'type': 'signal', 'payload':'ready'} in reqs:
                break
        writer.write(
            (json.dumps({
                'from': 'panel',
                'type': 'signal',
                'payload':'start'
            }) + "%SEP%").encode("utf-8")
        )
        await writer.drain()
        while True:
            data = await reader.read(1024)
            loader.update(data.decode())
            for req in loader.get_requests():    
                match req:
                    case {'from': 'asr', 'type': 'signal', 'payload': 'activate'}:
                        await self.results_queue.put(ASRActivated(self))
                    case {
                        "from": "asr",
                        "type": "data",
                        "payload": {
                            "user": user,
                            "content": content
                        }
                    }:
                        await self.results_queue.put(ASRMessage(self, user, content))
                    case _:
                        pass

class Loader: # loads的进一步封装
    def __init__(self, config: Config):
        assert isinstance(config.panel.server.requests_separator, str)
        self.sep: str = config.panel.server.requests_separator
        self.request_str: str = ""
        self.requests: list[dict[str, Any]] = []
    
    def update(self, request_str: str) -> None:
        self.request_str += request_str
        request_strings = self.request_str.split(self.sep)
        left = ""
        for i, request_string in enumerate(request_strings):
            if not request_string:
                continue
            try:
                self.requests.append(json.loads(request_string))
            except json.JSONDecodeError:
                if i == len(request_strings) - 1: # 最后一个请求被截断，留待下次更新
                    left = request_strings[-1]
                else:
                    print(f"Invalid JSON format: {request_string}")
        self.request_str = left
    
    def get_requests(self) -> list[dict[str, Any]]:
        requests, self.requests = self.requests, []
        return requests
