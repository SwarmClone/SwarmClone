from __future__ import annotations # 为了延迟注解评估

import asyncio
import time
import abc
from enum import Enum
from .constants import MessageType, ModuleRoles
from .messages import *

from swarmclone.tts_cosyvoice import TTSCosyvoice, TTSNetworkServer

class ModuleBase(abc.ABC):
    def __init__(self, module_role: ModuleRoles, name: str):
        self.name = name
        self.role = module_role
        self.task_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=10)
        self.results_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=10)
    
    async def run(self):
        while True:
            try:
                task = self.task_queue.get_nowait()
            except asyncio.QueueEmpty:
                task = None
            result = await self.process_task(task)
            if result is not None:
                await self.results_queue.put(result)
            await asyncio.sleep(0.1)

    def __repr__(self):
        return f"<{self.role} {self.name}>"

    @abc.abstractmethod
    async def process_task(self, task: Message | None) -> Message | None:
        """
        处理任务的方法，每个循环会自动调用
        返回None表示不需要返回结果，返回Message对象则表示需要返回结果，返回的对象会自动放入results_queue中。
        也可以选择手动往results_queue中put结果然后返回None
        """
        ...

class ASRDummy(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.ASR, "ASRDummy")
        self.timer = time.perf_counter()

    async def process_task(self, task: Message | None) -> Message | None:
        call_time = time.perf_counter()
        if call_time - self.timer > 1:
            self.timer = call_time
            await self.results_queue.put(ASRActivated(self))
            await self.results_queue.put(ASRMessage(self, f"{self}", "Hello, world!"))
        return None

class FrontendDummy(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.FRONTEND, "FrontendDummy")

    async def process_task(self, task: Message | None) -> Message | None:
        if task is not None:
            print(f"{self} received {task}")
        return None
    
