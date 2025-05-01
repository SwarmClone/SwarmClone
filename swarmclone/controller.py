"""
主控——主控端的核心
"""
import asyncio
from .modules import *

class Controller:
    def __init__(self):
        self.modules: dict[ModuleRoles, list[ModuleBase]] = {
            ModuleRoles.ASR: [],
            ModuleRoles.CHAT: [],
            ModuleRoles.FRONTEND: [],
            ModuleRoles.LLM: [],
            ModuleRoles.PLUGIN: [],
            ModuleRoles.TTS: [],
        }
    
    def register(self, module: ModuleBase):
        assert module.role in self.modules, "不明的模块类型"
        match module.role:
            case ModuleRoles.LLM:
                if len(self.modules[module.role]) > 0:
                    raise RuntimeError("只能注册一个LLM模块")
        self.modules[module.role].append(module)
    
    def start(self):
        loop = asyncio.get_event_loop()
        for (module_role, modules) in self.modules.items():
            for module in modules:
                loop.create_task(module.run())
                loop.create_task(self.handle_module(module))
                print(f"{module}已启动")
            else:
                print(f"{module_role.value}模块已启动")
        loop.run_forever()
    
    async def handle_module(self, module: ModuleBase):
        while True:
            result: Message = await module.results_queue.get()
            for destination in result.destinations:
                for module_destination in self.modules[destination]:
                    await module_destination.task_queue.put(result)
