"""
最基础的 OpenAI Chat Completion API 实现，不支持深度思考、工具调用等任何高级功能
使用场景：
- 本地 Ollama / vLLM 部署
- 尚未有独立实现的模型提供者
"""
import openai
from swarmclone.module_bootstrap import *

@dataclass
class ProviderOpenAIAPIConfig(ModuleConfig):
    """OpenAI API 配置"""
    api_base: str = field(default="https://api.openai.com/v1", metadata={
        "required": True,
        "desc": "OpenAI API 基础 URL"
    })
    api_key: str = field(default="sk-xxxxxxxx", metadata={
        "required": True,
        "desc": "OpenAI API 密钥"
    })
    model: str = field(default="gpt-3.5-turbo", metadata={
        "required": True,
        "desc": "OpenAI API 模型名称"
    })

class PrimaryProviderOpenAIAPI(ModuleBase):
    role: ModuleRoles = ModuleRoles.PRIMARY_PROVIDER
    config_class = ProviderOpenAIAPIConfig
    config: config_class
    def __init__(self, config: ModuleConfig | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.api_base = self.config.api_base
        self.api_key = self.config.api_key
        self.model = self.config.model
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
        )
        self.generation_tasks: list[asyncio.Task[None]] = []
    
    async def run(self) -> None:
        try:
            while True:
                message: Message = await self.task_queue.get()
                if not isinstance(message, ProviderRequest):
                    continue # 不是需要处理的请求
                request_data = message.get_value(self)
                request_source = type(message.source)
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

    async def generate_stream(self, messages: list[dict[str, str]], source: type[ModuleBase]):
        async for chunk in await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        ):
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            await self.results_queue.put(ProviderResponseStream(
                source=self,
                delta=delta,
                destination=source,
                end=False
            ))
        await self.results_queue.put(ProviderResponseStream(
            source=self,
            delta="",
            destination=source,
            end=True
        ))
    
    async def generate(self, messages: list[dict[str, str]], source: type[ModuleBase]):
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False,
        )
        await self.results_queue.put(ProviderResponseNonStream(
            source=self,
            content=response.choices[0].message.content,
            destination=source,
        ))            

__all__ = ["PrimaryProviderOpenAIAPI"]
