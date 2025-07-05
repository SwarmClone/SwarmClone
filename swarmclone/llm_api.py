import asyncio
import re
import os
import torch
import openai
from openai.types.chat import (
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionSystemMessageParam
)
from transformers import ( # type: ignore
    AutoModelForSequenceClassification,
    AutoTokenizer
)
from .config import Config
from .modules import *
from .messages import *
from .utils import download_model

def split_text(s: str, separators: str="。？！～.?!~\n\r") -> list[str]: # By DeepSeek
    # 构建正则表达式模式
    separators_class = ''.join(map(re.escape, separators))
    pattern = re.compile(rf'([{separators_class}]+)')
    
    # 分割并处理结果
    parts = pattern.split(s)
    result = []
    
    # 合并文本与分隔符（成对处理）
    for text, delim in zip(parts[::2], parts[1::2]):
        if (cleaned := (text + delim).lstrip()):
            result.append(cleaned)
    
    # 处理未尾未配对内容（保留后置空格）
    if len(parts) % 2:
        if (last_cleaned := parts[-1].lstrip()):
            result.append(last_cleaned)
    
    return result

class LLMOpenAI(LLMBase):
    def __init__(self, config: Config):
        super().__init__("LLMOpenAI", config)
        assert isinstance((classifier_model_path := config.llm.emotionclassification.model_path), str)
        assert isinstance((stop_string := config.llm.main_model.stop_string), str)
        self.stop_string = stop_string

        abs_classifier_path = os.path.expanduser(classifier_model_path)
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
            except Exception as e:
                print(e)
                choice = input("加载模型失败，是否下载模型？(Y/n)")
                if choice.lower() != "n":
                    assert isinstance((model_id := config.llm.emotionclassification.model_id), str)
                    assert isinstance((model_source := config.llm.emotionclassification.model_source), str)
                    download_model(model_id, model_source, abs_classifier_path)
        
        assert isinstance((model_id := config.llm.main_model.model_id), str)
        self.model_id = model_id
        assert isinstance((model_source := config.llm.main_model.model_source), str)
        assert model_source.startswith("openai+"), "`LLMOpenAI`只支持使用openai风格API的模型"
        assert isinstance((api_key := config.llm.main_model.api_key), str) and api_key, "请设置API key"
        self.url = model_source[7:] # 去掉openai+
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=self.url
        )
        assert isinstance((temperature := config.llm.main_model.temperature), float) and temperature >= 0 and temperature <= 1
        self.temperature = temperature
    
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
    
    def dict2message(self, message: dict[str, str]):
        match message:
            case {'role': 'user', 'content': content}:
                return ChatCompletionUserMessageParam(role="user", content=content)
            case {'role': 'assistant', 'content': content}:
                return ChatCompletionAssistantMessageParam(role="assistant", content=content)
            case {'role': 'system', 'content': content}:
                return ChatCompletionSystemMessageParam(role="system", content=content)
            case _:
                raise ValueError(f"Invalid message: {message}")
    
    async def iter_sentences_emotions(self):
        generating_sentence = ""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=[self.dict2message(message) for message in self.history],
                stream=True,
                temperature=self.temperature
            )
            async for delta in response:
                t = delta.choices[0].delta.content
                generating_sentence += (t or "")
                self.generated_text += (t or "")
                if (sentences := split_text(generating_sentence))[:-1]:
                    for sentence in sentences:
                        if (sentence := sentence.strip()):
                            yield sentence, await self.get_emotion(sentence)
                    generating_sentence = sentences[-1]
        finally: # 被中断或者生成完毕
            yield generating_sentence, await self.get_emotion(generating_sentence)
