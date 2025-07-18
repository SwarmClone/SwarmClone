from __future__ import annotations # 为了延迟注解评估
import asyncio
import time
import random
from typing import Any
from dataclasses import dataclass, field
from uuid import uuid4
from .constants import *
from .messages import *
from .module_manager import *

@dataclass
class LLMBaseConfig(ModuleConfig):
    chat_maxsize: int = field(default=20, metadata={
        "required": False,
        "desc": "弹幕接受数量上限",
        "min": 1,  # 最少接受 1 条弹幕
        "max": 1000
    })
    chat_size_threshold: int = field(default=10, metadata={
        "required": False,
        "desc": "弹幕逐条回复数量上限",
        "min": 1,  # 最少逐条回复 1 条
        "max": 100
    })
    do_start_topic: bool = field(default=False, metadata={
        "required": False,
        "desc": "是否自动发起对话"
    })
    idle_timeout: int | float = field(default=120, metadata={
        "required": False,
        "desc": "自动发起对话时间间隔",
        "min": 0.0,
        "max": 600,
        "step": 1.0  # 步长为 1
    })
    asr_timeout: int = field(default=60, metadata={
        "required": False,
        "desc": "语音识别超时时间",
        "min": 1,  # 最少 1 秒
        "max": 3600  # 最大 1 小时
    })
    tts_timeout: int = field(default=60, metadata={
        "required": False,
        "desc": "语音合成超时时间",
        "min": 1,  # 最少 1 秒
        "max": 3600  # 最大 1 小时
    })
    chat_role: str = field(default="user", metadata={
        "required": False,
        "desc": "弹幕对应的聊天角色"
    })
    asr_role: str = field(default="user", metadata={
        "required": False,
        "desc": "语音输入对应的聊天角色"
    })
    chat_template: str = field(default="{user}: {content}", metadata={
        "required": False,
        "desc": "弹幕的提示词模板"
    })
    asr_template: str = field(default="{user}: {content}", metadata={
        "required": False,
        "desc": "语音输入提示词模板"
    })
    system_prompt: str = field(default="""你是一只猫娘""", metadata={
        "required": False,
        "desc": "系统提示词"
    })  # TODO：更好的系统提示、MCP支持

class LLMBase(ModuleBase):
    role: ModuleRoles = ModuleRoles.LLM
    config_class = LLMBaseConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.state: LLMState = LLMState.IDLE
        self.history: list[dict[str, str]] = []
        self.generated_text: str = ""
        self.generate_task: asyncio.Task[Any] | None = None
        self.chat_maxsize: int = self.config.chat_maxsize
        self.chat_size_threshold: int = self.config.chat_size_threshold
        self.chat_queue: asyncio.Queue[ChatMessage] = asyncio.Queue(maxsize=self.chat_maxsize)
        self.do_start_topic: bool = self.config.do_start_topic
        self.idle_timeout: int | float = self.config.idle_timeout
        self.asr_timeout: int = self.config.asr_timeout
        self.tts_timeout: int = self.config.tts_timeout
        self.idle_start_time: float = time.time()
        self.waiting4asr_start_time: float = time.time()
        self.waiting4tts_start_time: float = time.time()
        self.asr_counter = 0 # 有多少人在说话？
        self.about_to_sing = False # 是否准备播放歌曲？
        self.song_id: str = ""
        self.chat_role = self.config.chat_role
        self.asr_role = self.config.asr_role
        self.chat_template = self.config.chat_template
        self.asr_template = self.config.asr_template
        if self.config.system_prompt:
            self._add_system_history(self.config.system_prompt)
    
    def _switch_to_generating(self):
        self.state = LLMState.GENERATING
        self.generated_text = ""
        self.generate_task = asyncio.create_task(self.start_generating())
    
    def _switch_to_waiting4asr(self):
        if self.generate_task is not None and not self.generate_task.done():
            self.generate_task.cancel()
        if self.generated_text:
            self._add_llm_history(self.generated_text)
        self.generated_text = ""
        self.generate_task = None
        self.state = LLMState.WAITING4ASR
        self.waiting4asr_start_time = time.time()
        self.asr_counter = 1 # 等待第一个人
    
    def _switch_to_idle(self):
        self.state = LLMState.IDLE
        self.idle_start_time = time.time()
    
    def _switch_to_waiting4tts(self):
        self._add_llm_history(self.generated_text)
        self.generated_text = ""
        self.generate_task = None
        self.state = LLMState.WAITING4TTS
        self.waiting4tts_start_time = time.time()
    
    def _switch_to_singing(self):
        self.state = LLMState.SINGING
        self.about_to_sing = False
        self._add_system_history(f'你唱了一首名为{self.song_id}的歌。')

    def _add_chat_history(self, user: str, content: str):
        self.history += [
            {'role': self.chat_role, 'content': self.chat_template.format(user=user, content=content)}
        ]
    
    def _add_asr_history(self, user: str, content: str):
        self.history += [
            {'role': self.asr_role, 'content': self.asr_template.format(user=user, content=content)}
        ]
    
    def _add_llm_history(self, content: str):
        self.history += [
            {'role': 'assistant', 'content': content}
        ]
    
    def _add_system_history(self, content: str):
        self.history += [
            {'role': 'system', 'content': content}
        ]
   
    async def run(self):
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
            if isinstance(task, SongInfo):
                self.about_to_sing = True
                self.song_id = task.get_value(self)["song_id"]

            match self.state:
                case LLMState.IDLE:
                    if isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                    elif self.about_to_sing:
                        await self.results_queue.put(
                            ReadyToSing(self, self.song_id)
                        )
                        self._switch_to_singing()
                    elif not self.chat_queue.empty():
                        try:
                            chat = self.chat_queue.get_nowait().get_value(self) # 逐条回复弹幕
                            self._add_chat_history(chat['user'], chat['content']) ## TODO：可能需要一次回复多条弹幕
                            self._switch_to_generating()
                        except asyncio.QueueEmpty:
                            pass
                    elif self.do_start_topic and time.time() - self.idle_start_time > self.idle_timeout:
                        self._add_system_history("请随便说点什么吧！")
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
                        self._add_asr_history(speaker_name, content)
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
    role: ModuleRoles = ModuleRoles.LLM
    def __init__(self, config: LLMBaseConfig | None = None, **kwargs):
        super().__init__(config, **kwargs)

    async def iter_sentences_emotions(self):
        sentences = ["This is a test sentence.", f"I received user prompt {self.history[-1]['content']}"]
        for sentence in sentences:
            yield sentence, {'like': 0, 'disgust': 0, 'anger': 0, 'happy': 0, 'sad': 0, 'neutral': 1.}

class FrontendDummy(ModuleBase):
    role: ModuleRoles = ModuleRoles.FRONTEND
    def __init__(self, config: ModuleConfig | None, **kwargs):
        super().__init__(config, **kwargs)

    async def process_task(self, task: Message | None) -> Message | None:
        if task is not None:
            print(f"{self} received {task}")
        return None

class ControllerDummy(ModuleBase):
    role: ModuleRoles = ModuleRoles.CONTROLLER
    """给Controller直接发送消息用的马甲，没有实际功能"""
