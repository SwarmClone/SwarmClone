from __future__ import annotations # 为了延迟注解评估

import asyncio
import time
import abc
from enum import Enum

class ModuleRoles(Enum):
    # 输出模块
    LLM = "LLM"
    TTS = "TTS"
    FRONTEND = "FRONTEND"

    # 输入模块
    ASR = "ASR"
    CHAT = "CHAT"

    # 其他模块
    PLUGIN = "PLUGIN"

    # 主控（并非模块，但是为了向其他模块发送消息，必须要有角色）
    CONTROLLER = "CONTROLLER"

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

class MessageType(Enum):
    SIGNAL = "SIGNAL"
    DATA = "DATA"

class Message:
    def __init__(self, message_type: MessageType,
                 source: ModuleBase, destinations: list[ModuleRoles],
                 **kwargs):
        self.message_type = message_type
        self.kwargs = kwargs
        self.source = source
        self.destinations = destinations
        print(f"{source} -> {self} -> {destinations}")
    
    def __repr__(self):
        return f"{self.message_type.value} {self.kwargs}"
    
    def get_value(self, getter: ModuleBase) -> dict:
        if not getter in self.destinations:
            print(f"{getter} <x {self} (-> {self.destinations})")
            return {}
        print(f"{getter} <- {self}")
        return self.kwargs

class ASRActivated(Message):
    def __init__(self, source: ModuleBase):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.TTS, ModuleRoles.FRONTEND, ModuleRoles.LLM]
        )

class ASRMessage(Message):
    def __init__(self, source: ModuleBase, speaker_name: str, message: str):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.LLM, ModuleRoles.FRONTEND],
            speaker_name=speaker_name,
            message=message
        )
