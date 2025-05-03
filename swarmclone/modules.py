from __future__ import annotations # 为了延迟注解评估

import asyncio
import time
import abc
from enum import Enum
from uuid import uuid4
from .constants import *
from .messages import *

class ModuleBase(abc.ABC):
    def __init__(self, module_role: ModuleRoles, name: str):
        self.name = name
        self.role = module_role
        self.task_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=10)
        self.results_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=128)
    
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

class ASRDummy(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.ASR, "ASRDummy")
        self.timer = time.perf_counter()

    async def process_task(self, task: Message | None) -> Message | None:
        call_time = time.perf_counter()
        if call_time - self.timer > 10:
            self.timer = call_time
            await self.results_queue.put(ASRActivated(self))
            await self.results_queue.put(ASRMessage(self, f"{self}", "Hello, world!"))
        return None

class LLMBase(ModuleBase):
    def __init__(self, name: str):
        super().__init__(ModuleRoles.LLM, name)
        self.timer = time.perf_counter()
        self.state = LLMState.IDLE
        self.history: list[dict[str, str]] = []
        self.generated_text = ""
    
    async def run(self):
        generate_task: asyncio.Future | None = None
        while True:
            try:
                task = self.task_queue.get_nowait()
            except asyncio.QueueEmpty:
                task = None
            
            match self.state:
                case LLMState.IDLE:
                    if isinstance(task, ASRActivated):
                        self.state = LLMState.WAITING4ASR
                    elif time.perf_counter() - self.timer > 10:
                        self.state = LLMState.GENERATING
                        self.history += [
                            {'role': 'system', 'content': '请随便说点什么吧！'}
                        ]
                        generate_task = asyncio.create_task(
                            self.start_generating()
                        )
                case LLMState.GENERATING:
                    if isinstance(task, ASRActivated) and generate_task is not None:
                        generate_task.cancel()
                        self.history += [
                            {'role': 'assistant', 'content': self.generated_text}
                        ]
                        self.generated_text = ""
                        generate_task = None
                        self.state = LLMState.WAITING4ASR
                    elif isinstance(task, ASRActivated): # 真的有这种情况吗？
                        self.state = LLMState.WAITING4ASR
                    elif generate_task is not None and generate_task.done():
                        self.history += [
                            {'role': 'assistant', 'content': self.generated_text}
                        ]
                        self.generated_text = ""
                        generate_task = None
                        self.state = LLMState.WAITING4TTS
                case LLMState.WAITING4ASR:
                    if task is not None and isinstance(task, ASRMessage):
                        self.state = LLMState.GENERATING
                        self.history += [{
                            'role': 'user',
                            'content': f"{(value := task.get_value(self))['speaker_name']}：{value['message']}"
                        }]
                        generate_task = asyncio.create_task(
                            self.start_generating()
                        )
                case LLMState.WAITING4TTS:
                    if task is not None and isinstance(task, TTSFinished):
                        self.state = LLMState.IDLE
                        self.timer = time.perf_counter()
                    elif task is not None and isinstance(task, ASRActivated):
                        self.state = LLMState.WAITING4ASR
            await asyncio.sleep(0.1)
    
    async def start_generating(self) -> None:
        async for sentence, emotion in self.iter_sentences_emotions():
            self.generated_text += sentence
            await self.results_queue.put(
                LLMMessage(
                    self,
                    sentence,
                    str(uuid4()),
                    emotion
                )
            )
        await self.results_queue.put(LLMEOS(self))
    
    @abc.abstractmethod
    async def iter_sentences_emotions(self):
        """
        句子-感情迭代器
        使用yield返回：
        (句子: str, 感情: dict)
        句子：模型返回的单个句子（并非整个回复）
        情感：{
            'like': float,
            'disgust': float,
            'anger': float,
            'happy': float,
            'sad': float,
            'neutral': float
        }
        迭代直到本次回复完毕即可
        """

    async def process_task(self, task: Message | None) -> Message | None:
        ... # 不会被用到

class LLMDummy(LLMBase):
    def __init__(self):
        super().__init__(ModuleRoles.LLM, "LLMDummy")

    async def iter_sentences_emotions(self):
        sentences = ["This is a test sentence.", f"I received user prompt {self.history[-1]['content']}"]
        for sentence in sentences:
            yield sentence, {'like': 0, 'disgust': 0, 'anger': 0, 'happy': 0, 'sad': 0, 'neutral': 1}

    async def process_task(self, task: Message | None) -> Message | None:
        ... # 不会被用到

class FrontendDummy(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.FRONTEND, "FrontendDummy")

    async def process_task(self, task: Message | None) -> Message | None:
        if task is not None:
            print(f"{self} received {task}")
        return None
    
