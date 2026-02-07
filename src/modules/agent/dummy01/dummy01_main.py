import asyncio
import time
import threading

from utils.logger import log
from core.event_bus import EventBus
from core.api_server import APIServer
from core.base_module import BaseModule
from core.config_manager import ConfigManager


class Dummy01Module(BaseModule):
    """虚拟模块01 - 代理模块"""

    def __init__(self, name: str,
                 config_manager: ConfigManager,
                 api_server: APIServer,
                 event_bus: EventBus):
        super().__init__(name, config_manager, api_server, event_bus)
        self.message_count = None

    async def initialize(self):
        """初始化模块"""
        log.info(f"初始化模块: {self.name}")

        # 注册配置
        self.register_config("prefix", "[D01] ")
        self.register_config("auto_reply", True)

        # 注册API路由
        await self.add_route("/echo", module_category="agent",
                       methods=["POST"], handler=self.handle_echo)
        await self.add_route("/status", module_category="agent",
                       methods=["GET"], handler=self.handle_status)

        # 订阅事件
        await self.subscribe("dummy01.task", self.handle_task)
        await self.subscribe("sample02.process", self.handle_sample02_process)

        # 状态
        self.message_count = 0

    def start(self):
        """启动模块"""
        log.info(f"启动模块: {self.name}")

        # 启动定期消息
        thread = threading.Thread(target=self._periodic_messages, daemon=True)
        thread.start()

    def _periodic_messages(self):
        """定期发送消息"""
        counter = 0
        while True:
            try:
                time.sleep(2)
                counter += 1

                asyncio.run(self.publish("dummy01.message", {
                    "count": counter,
                    "message": f"定期消息 #{counter}",
                    "from": self.name,
                    "timestamp": time.time()
                }))

                self.message_count += 1

            except Exception as e:
                log.error(f"[{self.name}] 定期消息错误: {e}")
                time.sleep(1)

    async def stop(self):
        """停止模块"""
        await super().stop()
        log.info(f"[{self.name}] 已停止，共发送 {self.message_count} 条消息")

    # === API处理器 ===
    def handle_echo(self, request):
        """处理/echo请求"""
        data = request.json if request.is_json else {}

        message = data.get("message", "")
        prefix = self.get_config("prefix")

        return {
            "echo": f"{prefix}{message}",
            "processed_by": self.name,
            "timestamp": time.time()
        }

    def handle_status(self, request):
        """处理/status请求"""
        return {
            "module": self.name,
            "message_count": self.message_count,
            "auto_reply": self.get_config("auto_reply"),
            "prefix": self.get_config("prefix")
        }

    # === 事件处理器 ===
    async def handle_task(self, event):
        """处理任务事件"""
        data = event.data
        log.info(f"[{self.name}] 收到任务: {data}")

        # 处理任务
        result = {
            "task_id": data.get("task_id", 0),
            "processed_by": self.name,
            "result": f"任务处理完成",
            "original": data,
            "timestamp": time.time()
        }

        # 发布结果
        await self.publish("dummy01.result", result)

        # 同时发送给sample01
        await self.publish("sample01.message", {
            "from": self.name,
            "task_result": result
        })

        return result

    def handle_sample02_process(self, event):
        """处理sample02处理结果"""
        data = event.data
        log.info(f"[{self.name}] 收到sample02处理结果: {data}")

        # 转发给dummy02
        asyncio.run(self.publish("dummy02.process", {
            "source": self.name,
            "data": data
        }))

        return {"forwarded": True, "timestamp": time.time()}