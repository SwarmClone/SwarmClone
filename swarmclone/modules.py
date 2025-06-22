from __future__ import annotations # 为了延迟注解评估
import asyncio
import time
import random
from typing import Any
from uuid import uuid4
from .constants import *
from .messages import *
from .config import Config

class ModuleBase:
    def __init__(self, module_role: ModuleRoles, name: str, config: Config):
        self.name: str = name
        self.role: ModuleRoles = module_role
        self.task_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=128)
        self.results_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=128)
        self.config: Config = config
    
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

class LLMBase(ModuleBase):
    def __init__(self, name: str, config: Config):
        super().__init__(ModuleRoles.LLM, name, config)
        self.state: LLMState = LLMState.IDLE
        self.history: list[dict[str, str]] = []
        self.generated_text: str = ""
        self.generate_task: asyncio.Task[Any] | None = None
        self.chat_maxsize: int = 20
        self.chat_size_threshold: int = 10
        self.chat_queue: asyncio.Queue[ChatMessage] = asyncio.Queue(maxsize=self.chat_maxsize)
        self.asr_timeout: int = 60 # 应该没有人说话一分钟不停
        self.tts_timeout: int = 60 ## TODO：是否应该加入设置项？
        self.idle_start_time: float = time.time()
        self.waiting4asr_start_time: float = time.time()
        self.waiting4tts_start_time: float = time.time()
        self.asr_counter = 0 # 有多少人在说话？
        self.about_to_sing = False # 是否准备播放歌曲？
        self.song_id: str = ""
    
    def _switch_to_generating(self):
        self.state = LLMState.GENERATING
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
        self.waiting4asr_start_time = time.time()
        self.asr_counter = 1 # 等待第一个人
    
    def _switch_to_idle(self):
        self.state = LLMState.IDLE
        self.idle_start_time = time.time()
    
    def _switch_to_waiting4tts(self):
        self.history += [
            {'role': 'user', 'content': self.generated_text}
        ]
        self.generated_text = ""
        self.generate_task = None
        self.state = LLMState.WAITING4TTS
        self.waiting4tts_start_time = time.time()
    
    def _switch_to_singing(self):
        self.state = LLMState.SINGING
        self.about_to_sing = False
        self.history += [
            {'role': 'system', 'content': f'你唱了一首名为{self.song_id}的歌。'}
        ]
            
    async def run(self):
        assert isinstance((idle_timeout := self.config.llm.idle_time), float | int), idle_timeout

        while True:
            try:
                task = self.task_queue.get_nowait()
                print(self.state, task)
            except asyncio.QueueEmpty:
                task = None
            
            if isinstance(task, ChatMessage):
                # 若小于一定阈值则回复每一条信息，若超过则逐渐降低回复概率
                if (qsize := self.chat_queue.qsize()) < self.chat_size_threshold:
                    prob = 1
                else:
                    prob = 1 - (qsize - self.chat_size_threshold) / (self.chat_maxsize - self.chat_size_threshold)
                if random.random() < prob:
                    try:
                        self.chat_queue.put_nowait(task)
                    except asyncio.QueueFull:
                        pass
            if isinstance(task, StartSinging):
                self.about_to_sing = True
                self.song_id = task.get_value(self)["song_id"]

            match self.state:
                case LLMState.IDLE:
                    if isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                    elif self.about_to_sing:
                        self._switch_to_singing()
                    elif not self.chat_queue.empty():
                        try:
                            chat = self.chat_queue.get_nowait().get_value(self) # 逐条回复弹幕
                            self.history.append({'role': 'chat', 'content': f'{chat["user"]}：{chat["content"]}'}) ## TODO：可能需要一次回复多条弹幕
                            self._switch_to_generating()
                        except asyncio.QueueEmpty:
                            pass
                    elif time.time() - self.idle_start_time > idle_timeout:
                        self.history.append({'role': 'system', 'content': '请随便说点什么吧！'})
                        self._switch_to_generating()

                case LLMState.GENERATING:
                    if isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                    if self.generate_task is not None and self.generate_task.done():
                        self._switch_to_waiting4tts()

                case LLMState.WAITING4ASR:
                    if time.time() - self.waiting4asr_start_time > self.asr_timeout:
                        self._switch_to_idle() # ASR超时，回到待机
                    if isinstance(task, ASRMessage):
                        message_value = task.get_value(self)
                        speaker_name = message_value["speaker_name"]
                        content = message_value["message"]
                        self.history.append({
                            'role': 'user',
                            'content': f"{speaker_name}：{content}"
                        })
                        self.asr_counter -= 1 # 有人说话完毕，计数器-1
                    if isinstance(task, ASRActivated):
                        self.asr_counter += 1 # 有人开始说话，计数器+1
                    if self.asr_counter <= 0: # 所有人说话完毕，开始生成
                        self._switch_to_generating()

                case LLMState.WAITING4TTS:
                    if time.time() - self.waiting4tts_start_time > self.tts_timeout:
                        self._switch_to_idle() # 太久没有TTS完成信息，说明TTS生成失败，回到待机
                    if isinstance(task, AudioFinished):
                        self._switch_to_idle()
                    elif isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                
                case LLMState.SINGING:
                    if isinstance(task, FinishedSinging):
                        self._switch_to_idle()

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
        yield str(""), {"like": 0., "disgust": 0., "anger": 0., "happy": 0., "sad": 0., "neutral": 1.}

class LLMDummy(LLMBase):
    def __init__(self, config: Config):
        super().__init__("LLMDummy", config)

    async def iter_sentences_emotions(self):
        sentences = ["This is a test sentence.", f"I received user prompt {self.history[-1]['content']}"]
        for sentence in sentences:
            yield sentence, {'like': 0, 'disgust': 0, 'anger': 0, 'happy': 0, 'sad': 0, 'neutral': 1.}

class FrontendDummy(ModuleBase):
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.FRONTEND, "FrontendDummy", config)

    async def process_task(self, task: Message | None) -> Message | None:
        if task is not None:
            print(f"{self} received {task}")
        return None

class ControllerDummy(ModuleBase):
    """给Controller直接发送消息用的马甲，没有实际功能"""
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.CONTROLLER, "ControllerDummy", config)
    