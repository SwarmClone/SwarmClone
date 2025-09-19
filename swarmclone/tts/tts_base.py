from swarmclone.module_bootstrap import *
import asyncio

class TTSBase(ModuleBase):
    role: ModuleRoles = ModuleRoles.TTS
    def __init__(self, config: ModuleConfig | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.processed_queue: asyncio.Queue[Message] = asyncio.Queue(128)

    async def run(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self.preprocess_tasks())
        while True:
            task = await self.processed_queue.get()
            if isinstance(task, LLMMessage): # 是一个需要处理的句子
                id = task.get_value(self).get("id", None)
                content = task.get_value(self).get("content", None)
                emotions = task.get_value(self).get("emotion", None)
                assert isinstance(id, str)
                assert isinstance(content, str)
                assert isinstance(emotions, dict)
                await self.results_queue.put(await self.generate_sentence(id, content, emotions))

    async def preprocess_tasks(self) -> None:
        while True:
            task = await self.task_queue.get()
            if isinstance(task, ASRActivated):
                while not self.processed_queue.empty():
                    self.processed_queue.get_nowait() # 确保没有句子还在生成
            else:
                await self.processed_queue.put(task)

    async def generate_sentence(self, id: str, content: str, emotions: dict[str, float]) -> TTSAlignedAudio:
        raise NotImplementedError
