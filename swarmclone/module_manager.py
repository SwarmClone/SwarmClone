from typing import Any
from .constants import *
from .messages import *
from dataclasses import dataclass
import asyncio

class ModuleManager(type):
    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        attrs["name"] = name
        new_class = super().__new__(cls, name, bases, attrs)
        if name != "ModuleBase" and attrs["role"] not in [ModuleRoles.CONTROLLER]:
            assert attrs["role"] != ModuleRoles.UNSPECIFIED, "请指定模块角色"
            print(f"Registering module {name}")
            module_classes[attrs["role"]][name] = new_class
        return new_class

ModuleType = ModuleManager

module_classes: dict[ModuleRoles, dict[str, ModuleType]] = {
    role: {} for role in ModuleRoles if role not in [ModuleRoles.UNSPECIFIED, ModuleRoles.CONTROLLER]
}

@dataclass
class ModuleConfig:
    """默认配置——没有配置项"""

class ModuleBase(metaclass=ModuleManager):
    role: ModuleRoles = ModuleRoles.UNSPECIFIED
    config_class = ModuleConfig
    name: str = "ModuleBase" # 会由metaclass自动赋值为类名
    def __init__(self, config: config_class | None = None, **kwargs):
        self.config = self.config_class(**kwargs) if config is None else config
        self.task_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=128)
        self.results_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=128)
        self.running = False
    
    async def run(self) -> None:
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

    async def process_task(self, task: Message | None) -> Message | None:
        """
        处理任务的方法，每个循环会自动调用
        返回None表示不需要返回结果，返回Message对象则表示需要返回结果，返回的对象会自动放入results_queue中。
        也可以选择手动往results_queue中put结果然后返回None
        """
