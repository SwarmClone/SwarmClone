"""
最基础的 Huggingface Transformers 本地模型服务
使用场景：
- 简易的本地模型服务
- 未被 Ollama 等模型推理框架支持的模型（如 MiniLM2 ）
"""
from swarmclone.module_bootstrap import *
import transformers as tf # TransFormers, not TensorFlow LOL
from typing import Any, cast

@dataclass
class ProviderTransformersConfig(ModuleConfig):
    """Transformers 模型配置"""
    model_path: str = field(default="models/MiniLM2", metadata={
        "required": True,
        "desc": "Transformers 模型位置"
    })
    temperature: float = field(default=0.7, metadata={
        "min": 0.0,
        "max": 1.0,
        "desc": "Transformers 模型温度参数"
    })
    max_new_tokens: int = field(default=1024, metadata={
        "min": 1,
        "max": 4096,
        "step": 1,
        "desc": "Transformers 模型单次最大生成 token 数"
    })

class PrimaryProviderTransformers(ModuleBase):
    role: ModuleRoles = ModuleRoles.PRIMARY_PROVIDER
    config_class = ProviderTransformersConfig
    config: config_class
    def __init__(self, config: ModuleConfig | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.model_path = self.config.model_path
        self.temperature = self.config.temperature
        self.tokenizer: tf.AutoTokenizer = tf.AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True
        )
        self.model: tf.PreTrainedModel = tf.AutoModelForCausalLM.from_pretrained(
            self.model_path,
            trust_remote_code=True
        )
        self.max_new_tokens = self.config.max_new_tokens
        self.generation_tasks: list[asyncio.Task[None]] = []
    
    async def run(self) -> None:
        try:
            while True:
                message: Message[Any] = await self.task_queue.get()
                if not isinstance(message, ProviderRequest):
                    continue # 不是需要处理的请求
                request_data = message.get_value(self)
                request_source = type(message.source) # 精准回复到请求源
                stream = request_data["stream"]
                messages = request_data["messages"]
                if stream:
                    task = asyncio.create_task(self.generate_stream(messages, request_source))
                else:
                    task = asyncio.create_task(self.generate(messages, request_source))
                self.generation_tasks.append(task)
        except asyncio.CancelledError:
            for task in self.generation_tasks:
                task.cancel()
            await asyncio.gather(*self.generation_tasks, return_exceptions=True)

    async def generate_stream(self, messages: list[dict[str, str]], request_source: type[ModuleBase]):
        inputs: tf.BatchEncoding = cast(tf.PreTrainedTokenizer, self.tokenizer).apply_chat_template( # pyright: ignore[reportAssignmentType, reportInvalidCast]
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        )
        streamer = tf.AsyncTextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        gen_task = asyncio.create_task(
            asyncio.to_thread(
                self.model.generate,
                **inputs,  # pyright: ignore[reportArgumentType]
                streamer=streamer,
                temperature=self.temperature,
                max_new_tokens=self.max_new_tokens
            )
        )
        try:
            async for token in streamer:
                await self.results_queue.put(ProviderResponseStream(
                    source=self,
                    delta=token,
                    end=False,
                    destination=request_source
                ))
            await self.results_queue.put(ProviderResponseStream(
                source=self,
                delta="",
                end=True,
                destination=request_source
            ))
        except asyncio.CancelledError:
            gen_task.cancel()
        
        try:
            await gen_task
        except asyncio.CancelledError:
            pass

    async def generate(self, messages: list[dict[str, str]], request_source: type[ModuleBase]):
        inputs: tf.BatchEncoding = cast(tf.PreTrainedTokenizer, self.tokenizer).apply_chat_template(  # pyright: ignore[reportInvalidCast, reportAssignmentType]
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        )
        outputs: tf.generation.utils.GenerateOutput = await asyncio.to_thread( # pyright: ignore[reportAssignmentType]
            self.model.generate,
            **inputs, # pyright: ignore[reportArgumentType]
            temperature=self.temperature,
            max_new_tokens=self.max_new_tokens,
            return_dict_in_generate=True # 此处已经确保返回值为 GenerateOutput
        )
        response = cast(tf.PreTrainedTokenizer, self.tokenizer).decode(  # pyright: ignore[reportInvalidCast]
            outputs[0][inputs["input_ids"].shape[1]:],  # pyright: ignore[reportAttributeAccessIssue]
            skip_special_tokens=True
        )
        await self.results_queue.put(ProviderResponseNonStream(
            source=self,
            content=response,
            destination=request_source
        ))

class SecondaryProviderTransformers(PrimaryProviderTransformers):
    role: ModuleRoles = ModuleRoles.SECONDARY_PROVIDER

__all__ = ["PrimaryProviderTransformers", "SecondaryProviderTransformers"]
