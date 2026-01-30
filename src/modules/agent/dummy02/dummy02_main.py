import asyncio
import time

from core.base_module import BaseModule
from utils.logger import log


class Dummy02Module(BaseModule):
    """虚拟模块02 - 代理模块"""

    def initialize(self):
        """初始化模块"""
        log.info(f"初始化模块: {self.name}")

        # 注册配置
        self.register_config("suffix", " [D02处理]")
        self.register_config("enable_logging", True)

        # 注册API路由
        self.add_route("/transform", module_category="agent",
                       methods=["POST"], handler=self.handle_transform)

        # 订阅事件
        self.subscribe("dummy02.transform", self.handle_transform_event)
        self.subscribe("dummy02.process", self.handle_process_event)

        # 状态
        self.transform_count = 0

    def start(self):
        """启动模块"""
        log.info(f"启动模块: {self.name}")
        log.info(f"[{self.name}] 已启动，后缀: {self.get_config('suffix')}")

    async def stop(self):
        """停止模块"""
        await super().stop()
        log.info(f"[{self.name}] 已停止，共处理 {self.transform_count} 个转换")

    # === API处理器 ===
    def handle_transform(self, request):
        """处理/transform请求"""
        data = request.json if request.is_json else {}

        text = data.get("text", "")
        suffix = self.get_config("suffix")
        result = f"{text}{suffix}"

        self.transform_count += 1

        return {
            "transformed": True,
            "original": text,
            "result": result,
            "transform_id": self.transform_count,
            "timestamp": time.time()
        }

    # === 事件处理器 ===
    async def handle_transform_event(self, event):
        """处理转换事件"""
        data = event.data
        log.info(f"[{self.name}] 收到转换事件: {data}")

        text = data.get("text", "")
        suffix = self.get_config("suffix")
        result = f"{text}{suffix}"

        self.transform_count += 1

        response = {
            "original": data,
            "transformed": result,
            "transform_id": self.transform_count,
            "processed_by": self.name,
            "timestamp": time.time()
        }

        # 发送响应
        await self.publish("dummy02.response", response)

        # 记录日志
        if self.get_config("enable_logging"):
            log.info(f"[{self.name}] 记录转换: {response}")

        return response

    async def handle_process_event(self, event):
        """处理处理事件"""
        data = event.data
        log.info(f"[{self.name}] 收到处理事件: {data}")

        # 添加后缀
        suffix = self.get_config("suffix")
        processed = {
            **data.get("data", {}),
            "final_suffix": suffix,
            "finalized_by": self.name,
            "timestamp": time.time()
        }

        # 发布最终结果
        await self.publish("system.final_result", processed)

        return {"finalized": True, "timestamp": time.time()}