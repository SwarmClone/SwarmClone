import time
import asyncio
import threading

from core.base_module import BaseModule
from utils.logger import log


class Sample01Module(BaseModule):
    """示例模块01 - 核心模块，简单循环通信"""

    def initialize(self):
        """初始化模块"""
        log.info(f"初始化模块: {self.name}")

        # 注册配置
        self.register_config("greeting", "你好，我是Sample01")
        self.register_config("interval", 0.5)
        self.register_config("max_messages", 20)

        # 注册API路由
        self.add_route("/hello", module_category="core",
                       methods=["GET"], handler=self.handle_hello)
        self.add_route("/ping", module_category="core",
                       methods=["GET"], handler=self.handle_ping_api)

        # 订阅事件
        self.subscribe("ping", self.handle_ping)
        self.subscribe("sample02.reply", self.handle_sample02_reply)
        self.subscribe("dummy01.message", self.handle_dummy01_message)
        self.subscribe("dummy02.response", self.handle_dummy02_response)

        # 状态
        self.counter = 0
        self.running = False

    def start(self):
        """启动模块"""
        log.info(f"启动模块: {self.name}")
        self.running = True
        self.counter = 0

        # 启动循环
        thread = threading.Thread(target=self._communication_loop, daemon=True)
        thread.start()

        log.info(f"[{self.name}] 启动成功，开始通信循环")

    def _communication_loop(self):
        """通信循环"""
        # 为这个线程创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self.running and self.counter < self.get_config("max_messages"):
                self.counter += 1
                log.info(f"[{self.name}] 开始第 {self.counter} 轮通信")

                # 向sample02发送请求
                try:
                    response = loop.run_until_complete(self.request(
                        "sample02.process",
                        {"value": self.counter, "from": self.name},
                        timeout=5.0
                    ))
                    if response:
                        log.info(f"[{self.name}] 收到sample02响应: {response}")
                    else:
                        log.warning(f"[{self.name}] sample02没有返回响应")
                except Exception as e:
                    log.error(f"[{self.name}] 请求sample02失败: {e}")

                # 向dummy01发送事件
                loop.run_until_complete(self.publish("dummy01.task", {
                    "from": self.name,
                    "task_id": self.counter,
                    "data": f"任务 #{self.counter}"
                }))

                # 向dummy02发送事件
                loop.run_until_complete(self.publish("dummy02.transform", {
                    "from": self.name,
                    "text": f"文本数据 {self.counter}"
                }))

                # 等待
                interval = self.get_config("interval")
                log.info(f"[{self.name}] 等待 {interval} 秒")
                time.sleep(interval)

        except Exception as e:
            log.error(f"[{self.name}] 通信循环错误: {e}")
        finally:
            # 清理事件循环
            if not loop.is_closed():
                loop.close()

    async def stop(self):
        """停止模块"""
        self.running = False
        await super().stop()
        log.info(f"[{self.name}] 已停止，共处理 {self.counter} 个循环")

    # === API处理器 ===
    def handle_hello(self, request):
        """处理/hello请求"""
        return {
            "message": self.get_config("greeting"),
            "counter": self.counter,
            "timestamp": time.time()
        }

    def handle_ping_api(self, request):
        """处理/ping请求"""
        return {
            "status": "ok",
            "module": self.name,
            "running": self.running,
            "counter": self.counter
        }

    # === 事件处理器 ===
    def handle_ping(self, event):
        """处理ping事件"""
        data = event.data
        if data.get("from") != self.name:
            log.info(f"[{self.name}] 收到ping: {data}")
            return {"pong": f"来自 {self.name}", "timestamp": time.time()}
        return None

    def handle_sample02_reply(self, event):
        """处理sample02回复"""
        log.info(f"[{self.name}] 收到sample02回复: {event.data}")
        return {"received": True, "timestamp": time.time()}

    def handle_dummy01_message(self, event):
        """处理dummy01消息"""
        log.info(f"[{self.name}] 收到dummy01消息: {event.data}")
        return {"ack": True, "timestamp": time.time()}

    def handle_dummy02_response(self, event):
        """处理dummy02响应"""
        log.info(f"[{self.name}] 收到dummy02响应: {event.data}")
        return {"final": True, "timestamp": time.time()}