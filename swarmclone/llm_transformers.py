import asyncio
import os
import queue
import torch
from dataclasses import dataclass, field
from transformers import (
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    TextIteratorStreamer,
    StoppingCriteriaList,
    StopStringCriteria
)
from .modules import *
from .messages import *
from .utils import *

available_devices = get_devices()

@dataclass
class LLMTransformersConfig(LLMBaseConfig):
    classifier_model_path: str = field(default="~/.swarmclone/llm/EmotionClassification/SWCBiLSTM", metadata={
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
        "options": [
            {"key": "Huggingface🤗", "value": "huggingface"},
            {"key": "ModelScope", "value": "modelscope"}
        ],
        "selection": True
    })
    model_path: str = field(default="~/.swarmclone/llm/MiniLM2/MiniLM2-nGPT-0.4b-instruct", metadata={
        "required": False,
        "desc": "模型路径"
    })
    model_id: str = field(default="", metadata={
        "required": True,
        "desc": "模型id"
    })
    model_source: str = field(default="modelscope", metadata={
        "required": False,
        "desc": "语言模型来源，仅支持huggingface或modelscope",
        "options": [
            {"key": "Huggingface🤗", "value": "huggingface"},
            {"key": "ModelScope", "value": "modelscope"}
        ],
        "selection": True
    })
    stop_string: str = field(default="\n\n\n", metadata={
        "required": False,
        "desc": "模型输出停止符"
    })
    temperature: float = field(default=0.5, metadata={
        "required": False,
        "desc": "模型温度",
        "min": 0.0,
        "max": 1.0,
        "step": 0.1
    })
    device: str = field(default=[*available_devices.keys()][0], metadata={
        "required": False,
        "desc": "模型运行设备",
        "selection": True,
        "options": [
            {"key": v, "value": k} for k, v in available_devices.items()
        ]
    })

class LLMTransformers(LLMBase):
    role: ModuleRoles = ModuleRoles.LLM
    config_class = LLMTransformersConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.config = self.config_class(**kwargs) if config is None else config
        self.stop_string = self.config.stop_string

        abs_model_path = os.path.expanduser(self.config.model_path)
        abs_classifier_path = os.path.expanduser(self.config.classifier_model_path)
        tries = 0
        while True: # 加载大语言模型
            try:
                print(f"正在从{abs_model_path}加载语言模型……")
                model = AutoModelForCausalLM.from_pretrained(
                    abs_model_path,
                    torch_dtype="auto",
                    trust_remote_code=True
                ).to(self.config.device).bfloat16() # 防止爆内存
                tokenizer = AutoTokenizer.from_pretrained(
                    abs_model_path,
                    padding_side="left",
                    trust_remote_code=True
                )
                self.model = model
                self.tokenizer = tokenizer  # 移除类型注解以兼容所有使用场景
                break
            except Exception:
                tries += 1
                if tries > 5:
                    raise
                download_model(self.config.model_id, self.config.model_source, abs_model_path)

        tries = 0
        while True: # 加载情感分类模型
            if tries > 5:
                raise Exception("模型加载失败")
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
                self.classifier_model = classifier_model
                self.classifier_tokenizer = classifier_tokenizer
                break
            except Exception:
                tries += 1
                if tries > 5:
                    raise
                download_model(
                    self.config.classifier_model_id,
                    self.config.classifier_model_source,
                    abs_classifier_path
                )
        
        self.device: str = self.config.device
        self.temperature: float = self.config.temperature
    
    @torch.no_grad()
    async def get_emotion(self, text: str) -> dict[str, float]:
        print(text)
        labels = ['neutral', 'like', 'sad', 'disgust', 'anger', 'happy']
        ids = self.classifier_tokenizer([text], return_tensors="pt")['input_ids']
        probs = (
            (await asyncio.to_thread(self.classifier_model, input_ids=ids))
            .logits
            .softmax(dim=-1)
            .squeeze()
        )
        return dict(zip(labels, probs.tolist()))
    
    @torch.no_grad()
    async def iter_sentences_emotions(self):
        text = self.tokenizer.apply_chat_template(self.history, tokenize=False, add_generation_prompt=True)
        assert isinstance(text, str)
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.device)
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=0)
        loop = asyncio.get_event_loop()
        generation_task = loop.create_task(
            asyncio.to_thread(
                self.model.generate,
                **model_inputs,
                max_new_tokens=512,
                streamer=streamer,
                stopping_criteria=StoppingCriteriaList(
                    [StopStringCriteria(self.tokenizer, self.stop_string)] if self.stop_string else []
                ),
                temperature=self.temperature
            )
        )
        generating_sentence = ""
        try:
            while True: # 等待第一个token防止后续生成被阻塞
                try:
                    t: str = next(streamer)
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                except StopIteration:
                    break
                generating_sentence += t
                self.generated_text += t
                if (sentences := split_text(generating_sentence))[:-1]:
                    for sentence in sentences:
                        if (sentence := sentence.strip()):
                            yield sentence, await self.get_emotion(sentence)
                    generating_sentence = sentences[-1]
        finally: # 被中断或者生成完毕
            if not generation_task.done():
                generation_task.cancel()
            yield generating_sentence, await self.get_emotion(generating_sentence)
