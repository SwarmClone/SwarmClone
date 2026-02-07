# SwarmCloneBackend
# Copyright (c) 2026 SwarmClone <github.com/SwarmClone> and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, List

from utils.logger import log
from core.api_server import APIServer
from core.event_bus import EventBus, Event
from core.config_manager import ConfigManager


class BaseModule(ABC):
    """
    所有模块的基类，提供模块生命周期管理和配置管理的接口
    """
    def __init__(self, name: str,
                 config_manager: ConfigManager,
                 api_server: APIServer,
                 event_bus: EventBus):
        self.name = name
        self._initialized = False

        self.config_manager = config_manager
        self.api_server = api_server
        self.event_bus = event_bus

        # 存储注册的路由和事件处理器，用于后续清理
        self._routes: List[str] = []
        self._event_handlers: List[tuple] = []  # [(event_name, callback), ...]

        log.debug(f"模块 {self.name} 已创建")

    def register_config(self, config_key: str, default_value: Any,
                        callback: Optional[Callable[[Any], None]] = None) -> None:
        """
        为当前模块注册一个配置项（同步操作）

        :param config_key: 配置项的键名
        :param default_value: 配置项的默认值
        :param callback: 当配置值变化时调用的回调函数（可以是异步函数），可选
        """
        # 如果 callback 是异步函数，包装为同步调用
        if callback and asyncio.iscoroutinefunction(callback):
            def sync_wrapper(value):
                asyncio.create_task(callback(value))

            self.config_manager.register(self.name, config_key, default_value, sync_wrapper)
        else:
            self.config_manager.register(self.name, config_key, default_value, callback)
        log.debug(f"已注册配置 {self.name}.{config_key}，默认值为 {default_value}")

    def get_config(self, config_key: str, default: Any = None) -> Any:
        """
        通过配置项名称获取其对应的配置值（仅限当前模块！）
        """
        return self.config_manager.get(self.name, config_key, default)

    def set_config(self, config_key: str, value: Any) -> None:
        """
        设置模块的配置值
        """
        self.config_manager.set(self.name, config_key, value)

    async def add_route(self, path: str,
                        module_category: str = None,
                        methods: list = None,
                        handler: Callable = None) -> None:
        """
        为当前模块异步注册一个API路由，路径会自动添加模块名前缀。
        handler 可以是异步函数或同步函数。

        :param path: 路由路径，不需要包含模块名前缀，需要以"/"开头
        :param module_category: 路由分类，可选，会被添加在模块名前缀前面
        :param methods: HTTP方法列表，如 ['GET', 'POST']
        :param handler: 处理函数（支持 async def 或普通 def）
        """
        if methods is None:
            methods = ['GET']

        # 自动构建完整路径
        if module_category:
            full_path = f"/{module_category}/{self.name}{path}"
        else:
            full_path = f"/{self.name}{path}"

        await self.api_server.add_route(full_path, methods, handler)
        self._routes.append(full_path)
        log.debug(f"已注册路由 {full_path}，方法: {methods}")

    async def subscribe(self, event_name: str,
                        callback: Callable,
                        filter_func: Optional[Callable[[Event], bool]] = None) -> None:
        """
        异步订阅一个事件。callback 可以是异步函数。

        :param event_name: 事件名称
        :param callback: 事件发生时调用的回调函数（支持 async），接受 Event 对象
        :param filter_func: 事件过滤函数，返回 True 则处理该事件
        """
        self.event_bus.subscribe(event_name, callback, filter_func)
        self._event_handlers.append((event_name, callback))
        log.debug(f"模块 {self.name} 已订阅事件 {event_name}")

    async def publish(self, event_name: str, data: Any = None) -> None:
        """
        发布一个事件
        """
        event = Event(name=event_name, data=data, source=self.name)
        await self.event_bus.publish(event)
        log.debug(f"Module {self.name} published event: {event_name}, data: {data}")

    async def request(self, event_name: str, data: Any,
                      timeout: float = 5.0) -> Any:
        """
        请求-响应模式
        """
        log.debug(f"Module {self.name} requested an event session, data: {data}")
        return await self.event_bus.request(event_name, data, self.name, timeout)

    @abstractmethod
    async def initialize(self) -> None:
        """
        异步初始化模块，子类需要实现此方法。
        在此方法中进行 self.add_route 和 self.subscribe等操作。
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """
        启动模块，子类需要实现此方法。
        被调用时模块应正式开始工作。
        """
        pass

    async def stop(self) -> None:
        """
        停止模块，子类需要实现此方法
        如果没有其他需要清理的，可以直接 await super().stop() 然后结束
        被调用后你需要停止模块运行并释放资源，并完成分内的清理工作
        """
        # 异步清理所有路由
        for route in self._routes:
            await self.api_server.remove_route(route)
        self._routes.clear()

        # 异步取消所有事件订阅
        for event_name, callback in self._event_handlers:
            self.event_bus.unsubscribe(event_name, callback)
        self._event_handlers.clear()

        log.info(f"Module {self.name} stopped")

    async def setup(self) -> None:
        """
        异步调用 initialize 方法并将模块标记为已初始化
        """
        if not self._initialized:
            await self.initialize()
            self._initialized = True
            log.info(f"模块 {self.name} 已初始化")