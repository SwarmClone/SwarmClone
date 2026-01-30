import time
import asyncio

from utils.logger import log
from core.event_bus import EventBus
from core.api_server import APIServer
from core.base_module import BaseModule
from core.config_manager import ConfigManager


class Sample02Module(BaseModule):
    """示例模块02 - 核心模块，处理请求"""

    def __init__(self, name: str,
                 config_manager: ConfigManager,
                 api_server: APIServer,
                 event_bus: EventBus):
        super().__init__(name, config_manager, api_server, event_bus)
        self.request_count = None

    def initialize(self):
        """初始化模块"""
        log.info(f"初始化模块: {self.name}")

        # 注册配置
        self.register_config("multiplier", 2)
        self.register_config("delay", 0.1)

        # 注册API路由
        self.add_route("/process", module_category="core",
                       methods=["POST"], handler=self.handle_process)
        self.add_route("/info", module_category="core",
                       methods=["GET"], handler=self.handle_info)

        # 订阅事件 - 修复：订阅正确的事件名称
        self.subscribe("sample02.process", self.handle_sample02_process)
        self.subscribe("sample01.request", self.handle_sample01_request)

        # 状态
        self.request_count = 0

    def start(self):
        """启动模块"""
        log.info(f"启动模块: {self.name}")
        log.info(f"[{self.name}] 已启动，乘数: {self.get_config('multiplier')}")

    async def stop(self):
        """停止模块"""
        await super().stop()
        log.info(f"[{self.name}] 已停止，共处理 {self.request_count} 个请求")

    # === API处理器 ===
    def handle_process(self, request):
        """处理/process请求"""
        data = request.json if request.is_json else {}

        self.request_count += 1
        value = data.get("value", 1)
        result = value * self.get_config("multiplier")

        return {
            "processed": True,
            "request_id": self.request_count,
            "input": value,
            "multiplier": self.get_config("multiplier"),
            "result": result,
            "timestamp": time.time()
        }

    def handle_info(self, request):
        """处理/info请求"""
        return {
            "module": self.name,
            "request_count": self.request_count,
            "multiplier": self.get_config("multiplier"),
            "delay": self.get_config("delay")
        }

    # === 事件处理器 ===
    async def handle_sample02_process(self, event):
        """处理sample02.process事件"""
        data = event.data
        log.info(f"[{self.name}] 收到sample02.process事件: {data}")

        # 增加请求计数
        self.request_count += 1

        # 模拟处理延迟
        delay = self.get_config("delay")
        if delay > 0:
            await asyncio.sleep(delay)

        # 处理数据
        value = data.get("value", 1)
        multiplier = self.get_config("multiplier")
        result = value * multiplier

        response = {
            "request_from": data.get("from", "unknown"),
            "processed_by": self.name,
            "request_id": self.request_count,
            "input": value,
            "multiplier": multiplier,
            "result": result,
            "timestamp": time.time()
        }

        # 发送回复给sample01
        await self.publish("sample02.reply", response)

        return response

    async def handle_sample01_request(self, event):
        """处理sample01的请求"""
        data = event.data
        log.info(f"[{self.name}] 收到sample01请求: {data}")

        # 模拟处理延迟
        await asyncio.sleep(self.get_config("delay"))

        value = data.get("value", 1)
        result = value * self.get_config("multiplier")

        response = {
            "request_from": data.get("from", "unknown"),
            "processed_by": self.name,
            "result": result,
            "timestamp": time.time()
        }

        # 回复给sample01
        await self.publish("sample02.reply", response)

        # 同时发送给dummy01
        await self.publish("dummy01.process", response)

        return response

    def handle_sample02_process_event(self, event):
        """处理sample02.process事件（备选同步处理器）"""
        log.info(f"{self.name} 处理sample02.process事件: {event.data}")
        # 处理逻辑
        result = {
            "processed": True,
            "data": event.data,
            "by": self.name
        }
        return result