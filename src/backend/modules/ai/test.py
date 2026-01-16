from src.backend.core.controller import Controller


from backend.core.event_bus import Event
from backend.shared.logger import log
from typing import Any

#测试各种功能的运行情况用的AI模块
class TestAI:
    def __init__(self, controller: Controller) -> None:
        self.name = "TestAI"
        controller.subscribe(
            module_name="ai",
            config_events={"ai": self.config_update},
            message_events={"chat": self.handle_chat_message}
        )
        self.controller: Controller = controller

    def config_update(self, new_config: Any) -> None:
        if new_config == "1":
            log.info(f"{self.name} received new config: {new_config}")
        else:
            raise ValueError("Invalid config value for TestAI")

    async def handle_chat_message(self, data: Event) -> None:
        await self.controller.event_message_publish(Event(name="rep", source="ai", data={"reply": f"Echo: {data.data}"}))

def factory(controller: Controller) -> TestAI:
    return TestAI(controller)