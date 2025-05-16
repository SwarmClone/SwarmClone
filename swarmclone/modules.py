from __future__ import annotations # 为了延迟注解评估

import asyncio
import time
import random
from enum import Enum
from uuid import uuid4
from .constants import *
from .messages import *

class ModuleBase:
    def __init__(self, module_role: ModuleRoles, name: str):
        self.name = name
        self.role = module_role
        self.task_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=128)
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
        if call_time - self.timer > 5:
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
        self.generate_task: asyncio.Task | None = None
        self.chat_maxsize = 20
        self.chat_size_threshold = 10
        self.chat_queue: asyncio.Queue[ChatMessage] = asyncio.Queue(maxsize=self.chat_maxsize)
    
    def _switch_to_generating(self, new_round: dict):
        self.state = LLMState.GENERATING
        self.history.append(new_round)
        self.generated_text = ""
        self.generate_task = asyncio.create_task(self.start_generating())
    
    def _switch_to_waiting4asr(self):
        if self.generate_task is not None and not self.generate_task.done():
            self.generate_task.cancel()
        if self.generated_text:
            self.history += [
                {'role': 'assistant', 'content': self.generated_text}
            ]
        self.generated_text = ""
        self.generate_task = None
        self.state = LLMState.WAITING4ASR
    
    def _switch_to_idle(self):
        self.state = LLMState.IDLE
        self.timer = time.perf_counter()
    
    def _switch_to_waiting4tts(self):
        self.history += [
            {'role': 'user', 'content': self.generated_text}
        ]
        self.generated_text = ""
        self.generate_task = None
        self.state = LLMState.WAITING4TTS
            
    async def run(self):
        while True:
            try:
                task = self.task_queue.get_nowait()
                print(self.state, task)
            except asyncio.QueueEmpty:
                task = None
            
            if isinstance(task, ChatMessage):
                if (qsize := self.chat_queue.qsize()) < self.chat_size_threshold:
                    prob = 1
                else:
                    prob = 1 - (qsize - self.chat_size_threshold) / (self.chat_maxsize - self.chat_size_threshold)
                if random.random() < prob:
                    try:
                        self.chat_queue.put_nowait(task)
                    except asyncio.QueueFull:
                        pass

            match self.state:
                case LLMState.IDLE:
                    if isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                    elif not self.chat_queue.empty():
                        try:
                            chat = self.chat_queue.get_nowait().get_value(self)
                            self._switch_to_generating({'role': 'chat', 'content': f'{chat["user"]}：{chat["content"]}'})
                        except asyncio.QueueEmpty:
                            pass
                    elif time.perf_counter() - self.timer > 10:
                        self._switch_to_generating({'role': 'system', 'content': '请随便说点什么吧！'})
                case LLMState.GENERATING:
                    if isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                    if self.generate_task is not None and self.generate_task.done():
                        self._switch_to_waiting4tts()
                case LLMState.WAITING4ASR:
                    if task is not None and isinstance(task, ASRMessage):
                        message_value = task.get_value(self)
                        speaker_name = message_value["speaker_name"]
                        content = message_value["message"]
                        self._switch_to_generating({
                            'role': 'user',
                            'content': f"{speaker_name}：{content}"
                        })
                case LLMState.WAITING4TTS:
                    if task is not None and isinstance(task, TTSFinished):
                        self._switch_to_idle()
                    elif task is not None and isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
            await asyncio.sleep(0.1) # 避免卡死事件循环
    
    async def start_generating(self) -> None:
        iterator = self.iter_sentences_emotions()
        try:
            async for sentence, emotion in iterator:
                self.generated_text += sentence
                await self.results_queue.put(
                    LLMMessage(
                        self,
                        sentence,
                        str(uuid4()),
                        emotion
                    )
                )
        except asyncio.CancelledError:
            await iterator.aclose()
        finally:
            await self.results_queue.put(LLMEOS(self))
    
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
        yield "", {"like": 0, "disgust": 0, "anger": 0, "happy": 0, "sad": 0, "neutral": 1}

class LLMDummy(LLMBase):
    def __init__(self):
        super().__init__("LLMDummy")

    async def iter_sentences_emotions(self):
        sentences = ["This is a test sentence.", f"I received user prompt {self.history[-1]['content']}"]
        for sentence in sentences:
            yield sentence, {'like': 0, 'disgust': 0, 'anger': 0, 'happy': 0, 'sad': 0, 'neutral': 1}

class FrontendDummy(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.FRONTEND, "FrontendDummy")

    async def process_task(self, task: Message | None) -> Message | None:
        if task is not None:
            print(f"{self} received {task}")
        return None

class ControllerDummy(ModuleBase):
    """给Controller直接发送消息用的马甲，没有实际功能"""
    def __init__(self):
        super().__init__(ModuleRoles.CONTROLLER, "ControllerDummy")
    