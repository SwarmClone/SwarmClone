import asyncio
import re
import os
import queue
import torch
from transformers import ( # type: ignore
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    TextIteratorStreamer,
    StoppingCriteriaList,
    StopStringCriteria
)
from .config import config
from .modules import *
from .messages import *

def split_text(s, separators="。？！～.?!~\n\r") -> list[str]: # By DeepSeek
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

class LLMMiniLM2(LLMBase):
    def __init__(self):
        super().__init__("LLMMiniLM2")

        successful = False
        abs_model_path = os.path.expanduser(config.llm.minilm2.model_path)
        abs_classifier_path = os.path.expanduser(config.llm.emotionclassification.model_path)
        while not successful: # 加载大语言模型
            try:
                print(f"正在从{abs_model_path}加载语言模型……")
                model = AutoModelForCausalLM.from_pretrained(
                    abs_model_path,
                    torch_dtype="auto",
                    trust_remote_code=True
                ).to(config.llm.device).bfloat16() # 防止爆内存
                tokenizer = AutoTokenizer.from_pretrained(
                    abs_model_path,
                    padding_side="left",
                    trust_remote_code=True
                )
                successful = True
            except Exception as e:
                print(e)
                choice = input("加载模型失败，是否下载模型？(Y/n)")
                if choice.lower() != "n":
                    from modelscope.hub.snapshot_download import snapshot_download # type: ignore
                    snapshot_download(
                        repo_id=config.llm.minilm2.model_id,
                        repo_type="model",
                        local_dir=abs_model_path
                    )

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
            except Exception as e:
                print(e)
                choice = input("加载模型失败，是否下载模型？(Y/n)")
                if choice.lower() != "n":
                    from huggingface_hub import snapshot_download # type: ignore
                    snapshot_download(
                        repo_id=config.llm.emotionclassification.model_id,
                        repo_type="model",
                        local_dir=abs_classifier_path
                    )

        self.model = model
        self.tokenizer = tokenizer
        self.classifier_model = classifier_model
        self.classifier_tokenizer = classifier_tokenizer
        self.device = config.llm.device
    
    @torch.no_grad()
    async def get_emotion(self, text: str) -> dict[str, float]:
        print(text)
        labels = ['neutral', 'like', 'sad', 'disgust', 'anger', 'happy']
        ids = self.classifier_tokenizer([text], return_tensors="pt")['input_ids']
        """
        probs = (
            (await asyncio.to_thread(self.classifier_model, input_ids=ids))
            .logits
            .softmax(dim=-1)
            .squeeze()
        )
        """
        logits: torch.Tensor = (await asyncio.to_thread(self.classifier_model, input_ids=ids)).logits.squeeze()
        return dict(zip(labels, logits.softmax(dim=-1).tolist()))
    
    @torch.no_grad()
    async def iter_sentences_emotions(self):
        text = self.tokenizer.apply_chat_template(self.history, tokenize=False, add_generation_prompt=True)
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
                    [StopStringCriteria(self.tokenizer, "\n" * 3)]
                )
            )
        )
        generating_sentence = ""
        try:
            while True: # 等待第一个token防止后续生成被阻塞
                try:
                    t = next(streamer)
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                except queue.StopIteration:
                    break
                generating_sentence += t
                self.generated_text += t
                if (sentences := split_text(generating_sentence))[:-1]:
                    for sentence in sentences:
                        if (sentence := sentence.strip()):
                            yield sentence, await self.get_emotion(sentence)
                    generating_sentence = sentences[-1]
        finally: # 被中断或者生成完毕
            yield generating_sentence, await self.get_emotion(generating_sentence)
            if not generation_task.done():
                generation_task.cancel()
