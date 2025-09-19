from __future__ import annotations
from dataclasses import dataclass, field
from swarmclone.module_bootstrap import *
from swarmclone.chat.chat_qq import *
import asyncio
import random

@dataclass
class NCatBotFrontendConfig(ModuleConfig):
    sleeptime_min: int | float = field(default=0, metadata={
        "required": False,
        "desc": "模型回复随机延迟最小值",
        "min": 0,
        "max": 10,
        "step": 0.1
    })
    sleeptime_max: int | float = field(default=0, metadata={
        "required": False,
        "desc": "模型回复随机延迟最大值",
        "min": 0,
        "max": 10,
        "step": 0.1
    })

class NCatBotFrontend(ModuleBase):
    role: ModuleRoles = ModuleRoles.FRONTEND
    config_class = NCatBotFrontendConfig
    config: config_class
    """接受LLM的信息并发送到目标群中"""
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.llm_buffer = ""
    
    def get_sleep_time(self) -> float:
        return random.random() * (self.config.sleeptime_max - self.config.sleeptime_min) + self.config.sleeptime_min
    
    async def process_task(self, task: Message | None) -> Message | None:
        if isinstance(task, LLMMessage):
            self.llm_buffer += task.get_value(self).get("content", "")
        elif isinstance(task, LLMEOS) and self.llm_buffer:
            await asyncio.sleep(self.get_sleep_time()) # 防止被发现是机器人然后封号
            await self.results_queue.put(NCatBotLLMMessage(self, self.llm_buffer.strip()))
            await self.results_queue.put(AudioFinished(self)) # 防止LLM等待不存在的TTS
            self.llm_buffer = ""

__all__ = ["NCatBotFrontend"]
