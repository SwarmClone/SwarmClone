import os
import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer
)
from uuid import uuid4
import time
import random
from typing import Any
from swarmclone.module_bootstrap import *

@dataclass
class LLMConfig(ModuleConfig):
    chat_maxsize: int = field(default=20, metadata={
        "required": False,
        "desc": "弹幕接受数量上限",
        "min": 1,  # 最少接受 1 条弹幕
        "max": 1000
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
    sys_role: str = field(default="system", metadata={
        "required": False,
        "desc": "指令对应的聊天角色"
    })
    chat_template: str = field(default="{user}: {content}", metadata={
        "required": False,
        "desc": "弹幕的提示词模板"
    })
    asr_template: str = field(default="{user}: {content}", metadata={
        "required": False,
        "desc": "语音输入提示词模板"
    })
    sys_template: str = field(default="{user}: {content}", metadata={
        "required": False,
        "desc": "指令提示词模板"
    })
    system_prompt: str = field(default=(
            "# 提示词开始\n"
            "## 人物设定\n"
            "你是一只十六岁的人工智能少女猫娘主播，名叫【xxxxx】，你的外观是【xxxx】。\n"
            "你现在的主人名叫【xxxx】，是【xxxxx】。\n"
            "你很关心你的主人。\n"
            "## 任务设定\n"
            "你将参与【xxxx】平台直播，与你的主人和观众对话。你的直播主要内容是【xxxxx】。\n"
            "如有提供工具，请合理使用。\n"
            "你将接收到“[用户名]：[内容]”的格式的消息，"
            "若[用户名]为你主人的名字，则说明是你的主人在向你说话，请优先回复；"
            "若[用户名]为“<系统>”，则说明是系统消息，请视为直接的指令；"
            "若[用户名]为“<记忆>”，则说明是记忆内容，请参考记忆内容进行回复。\n"
            "## 发言语气\n"
            "你以轻松可爱的语气进行对话，一些俏皮话和笑话是可以接受的，请记住你是一只猫娘。\n"
            "发言请保持简洁且口语化。最好不超过 30 字，请注意保持直播节奏。\n"
            "## 语言\n"
            "你使用中文进行交流，除非你的主人要求你使用别的语言。\n"
            "## 额外信息\n"
            f"当前时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
            "你的记忆：【xxxx】\n"
            "# 提示词结束\n"
            "\n"
            "以上为提示词模板，使用前请将【】内容替换为你希望的实际内容，也可自行撰写。启动前请删除这一行。"
        ), metadata={
        "required": False,
        "desc": "系统提示词",
        "multiline": True
    })
    classifier_model_path: str = field(default="./models/EmotionClassification/SWCBiLSTM", metadata={
        "required": False,
        "desc": "情感分类模型路径"
    })
    classifier_model_id: str = field(default="MomoiaMoia/SWCBiLSTM", metadata={
        "required": False,
        "desc": "情感分类模型id"
    })
    classifier_model_source: str = field(default="modelscope", metadata={
        "required": False,
        "desc": "情感分类模型来源，仅支持huggingface或modelscope",
        "selection": True,
        "options": [
            {"key": "Huggingface🤗", "value": "huggingface"},
            {"key": "ModelScope", "value": "modelscope"}
        ]
    })

class LLM(ModuleBase):
    role: ModuleRoles = ModuleRoles.LLM
    config_class = LLMConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.state: LLMState = LLMState.IDLE
        self.history: list[dict[str, str]] = []
        self.generated_text: str = ""
        self.generate_task: asyncio.Task[Any] | None = None
        self.chat_maxsize: int = self.config.chat_maxsize
        self.chat_buffer: list[dict[str, str]] = []
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
        self.sys_role = self.config.sys_role
        self.chat_template = self.config.chat_template
        self.asr_template = self.config.asr_template
        self.sys_template = self.config.sys_template
        if self.config.system_prompt:
            self._add_system_history(self.config.system_prompt)
        abs_classifier_path = os.path.expanduser(self.config.classifier_model_path)
        successful = False
        while not successful: # 加载情感分类模型
            try:
                print(f"正在从{abs_classifier_path}加载情感分类模型……")
                classifier_model = AutoModelForSequenceClassification.from_pretrained(
                    abs_classifier_path,
                    torch_dtype="auto",
                    trust_remote_code=True
                ).to("cpu")
                classifier_tokenizer = AutoTokenizer.from_pretrained(
                    abs_classifier_path,
                    padding_side="left",
                    trust_remote_code=True
                )
                successful = True
                self.classifier_model = classifier_model
                self.classifier_tokenizer = classifier_tokenizer
            except Exception:
                download_model(
                    self.config.classifier_model_id,
                    self.config.classifier_model_source,
                    abs_classifier_path
                )
        self.chat_count = 0
        self.provider_responses: asyncio.Queue[ProviderResponseStream] = asyncio.Queue()
    
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
        self._add_instruct_history(f'你唱了一首名为{self.song_id}的歌。')

    def _add_history(self, role: str, content: str, template: str | None = None, user: str | None = None):
        """统一的历史添加方法"""
        if template and user:
            formatted_content = template.format(user=user, content=content)
        else:
            formatted_content = content
        self.history.append({'role': role, 'content': formatted_content})

    def _add_multi_chat_history(self, messages: list[dict[str, str]]):
        message_text = "\n".join(
            self.chat_template.format(user=msg['user'], content=msg['content'])
            for msg in messages
        )
        self._add_history(self.chat_role, message_text)
    
    def _add_asr_history(self, user: str, content: str):
        self._add_history(self.asr_role, content, self.asr_template, user)
    
    def _add_llm_history(self, content: str):
        self._add_history('assistant', content)
    
    def _add_system_history(self, content: str):
        self._add_history('system', content)
    
    def _add_instruct_history(self, content: str):
        self._add_history(self.sys_role, content, self.sys_template, "<系统>")
    
    def _add_memory_history(self, content: str):
        self._add_history(self.sys_role, content, self.sys_template, "<记忆>")

    def _append_chat_buffer(self, user: str, content: str):
        self.chat_count += 1
        if len(self.chat_buffer) < self.chat_maxsize:
            self.chat_buffer.append({
                'user': user,
                'content': content
            })
        else:
            # 水池采样保证均匀抽取，同时保留时间顺序
            rand = random.randint(0, self.chat_count - 1)
            if rand < len(self.chat_buffer):
                self.chat_buffer.pop(rand)
                self.chat_buffer.append({
                    'user': user,
                    'content': content
                })

    async def run(self):
        while True:
            try:
                task = self.task_queue.get_nowait()
                print(self.state, task)
            except asyncio.QueueEmpty:
                task = None
            
            if isinstance(task, ProviderResponseStream):
                await self.provider_responses.put(task)
                continue # 直接转交给生成协程处理

            if isinstance(task, ChatMessage): ## TODO: 支持模型自主选择是否回复
                message = task.get_value(self)
                self._append_chat_buffer(message['user'], message['content'])
            if isinstance(task, MultiChatMessage):
                for msg in task.get_value(self)['messages']:
                    self._append_chat_buffer(msg['user'], msg['content'])
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
                    elif self.chat_buffer:
                        self._add_multi_chat_history(self.chat_buffer)
                        self.chat_buffer.clear()
                        self.chat_count = 0
                        self._switch_to_generating()
                    elif self.do_start_topic and time.time() - self.idle_start_time > self.idle_timeout:
                        self._add_instruct_history("请随便说点什么吧！")
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
        await self.results_queue.put(ProviderRequest(
            source=self,
            stream=True,
            messages=self.history,
            model=Providers.PRIMARY
        ))
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
    
    @torch.no_grad()
    async def get_emotion(self, text: str) -> Emotion:
        print(text)
        labels = ['neutral', 'like', 'sad', 'disgust', 'anger', 'happy']
        ids = self.classifier_tokenizer([text], return_tensors="pt")['input_ids']
        probs = (
            (await asyncio.to_thread(self.classifier_model, input_ids=ids))
            .logits
            .softmax(dim=-1)
            .squeeze()
        )
        emotion_dict = dict(zip(labels, probs.tolist()))
        # 创建符合Emotion TypedDict的对象，确保所有必需的键都存在
        return Emotion(
            neutral=emotion_dict.get("neutral", 0.0),
            like=emotion_dict.get("like", 0.0),
            sad=emotion_dict.get("sad", 0.0),
            disgust=emotion_dict.get("disgust", 0.0),
            anger=emotion_dict.get("anger", 0.0),
            happy=emotion_dict.get("happy", 0.0)
        )

    async def iter_sentences_emotions(self):
        text_buffer = ""
        while True:
            response = await self.provider_responses.get()
            response_data = response.get_value(self)
            if not response_data["end"]:
                text_buffer += response_data["delta"]
            if len(sentences := split_text(text_buffer)) > 1:
                for sentence in sentences[:-1]:
                    emotion = await self.get_emotion(sentence)
                    yield sentence, emotion
                text_buffer = sentences[-1]
            if response_data["end"]:
                emotion = await self.get_emotion(text_buffer)
                yield text_buffer, emotion
                break

__all__ = ["LLM"]
