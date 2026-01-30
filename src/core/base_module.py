import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, List

from core.api_server import APIServer
from core.config_manager import ConfigManager
from core.event_bus import EventBus, Event
from utils.logger import log


class BaseModule(ABC):
    """
    所有模块的基类，提供模块生命周期管理和配置管理的接口
    """
    def __init__(self, name: str,
                 config_manager: ConfigManager,
                 api_server: APIServer,
                 event_bus: EventBus):
        self._routes = None
        self.name = name
        self._initialized = False

        self.config_manager = config_manager
        self.api_server = api_server
        self.event_bus = event_bus

        self._routes: List[str] = []
        self._events: List[tuple] = []

        log.debug(f"模块 {self.name} 已创建")

    def register_config(self, config_key: str, default_value: Any,
                       callback: Optional[Callable[[Any], None]] = None) -> None:
        """
        为当前模块注册一个配置项

        :param config_key: 配置项的键名
        :param default_value: 配置项的默认值
        :param callback: 当配置值变化时调用的回调函数，可选
        :return 无返回值
        """
        self.config_manager.register(self.name, config_key, default_value, callback)
        log.debug(f"已注册配置 {self.name}.{config_key}，默认值为 {default_value}")

    def get_config(self, config_key: str, default: Any = None) -> Any:
        """
        配置项名称获取其对应的配置值（仅限当前模块！）

        :param config_key: 配置项的键名
        :param default: 如果配置项不存在，返回的默认值
        :return 配置值或默认值
        """
        return self.config_manager.get(self.name, config_key, default)

    def set_config(self, config_key: str, value: Any) -> None:
        """
        设置模块的配置值

        :param config_key: 配置项的键名
        :param value: 要设置的新值
        :return 无返回值
        """
        self.config_manager.set(self.name, config_key, value)

    def add_route(self, path: str,
                  module_category: str = None,
                  methods: list = None,
                  handler: Callable = None) -> None:
        """
        为当前模块注册一个API路由，路径会自动添加模块名前缀

        :param path: 路由路径，不需要包含模块名前缀，需要以“/”开头
        :param module_category: 路由分类，可选，会被添加在模块名前缀前面，即：“/<分类>/<模块名>/<你填写的path路径>”
        :param methods: HTTP方法列表，如 ['GET', 'POST']
        :param handler: 处理函数
        :return 无返回值
        """
        if methods is None:
            methods = ['GET']

        # 自动添加模块名前缀
        full_path = f"/{module_category}/{self.name}{path}"
        self.api_server.add_route(full_path, methods, handler)
        log.debug(f"已注册路由 {full_path}，方法: {methods}")

    def subscribe(self, event_name: str,
                        callback: Callable,
                        filter_func: Optional[Callable[[Event], bool]] = None) -> None:
        """
        订阅一个事件

        :param event_name: 事件名称
        :param callback: 事件发生时调用的回调函数，函数应接受一个 Event 对象作为参数
        :param filter_func: 事件过滤函数，用于筛选需要处理的事件，函数返回 True 则处理该事件，默认为 None（处理所有事件）
        :return 无返回值
        """
        self.event_bus.subscribe(event_name, callback, filter_func)
        log.debug(f"模块 {self.name} 已订阅事件 {event_name}")

    async def publish(self, event_name: str, data: Any = None) -> None:
        """
        发布一个事件

        :param event_name: 事件类型，不需要包含模块名前缀
        :param data: 事件数据
        :return 无返回值
        """
        event = Event(name=event_name, data=data, source=self.name)
        await self.event_bus.publish(event)
        log.debug(f"Module {self.name} published event: {event_name}, data: {data}")

    async def request(self, event_name: str, data: Any,
                      timeout: float = 5.0) -> Any:
        """
        请求-响应模式
        让发布者发出请求，并等待结果。

        :param event_name: 请求事件的名称
        :param data: 请求携带的数据
        :param timeout: 响应超时时间，单位为秒，默认为5.0秒
        :return:响应结果，如果超时则返回None
        """
        log.debug(f"Module {self.name} requested an event session, data: {data}")
        return await self.event_bus.request(event_name, data, self.name, timeout)

    @abstractmethod
    def initialize(self) -> None:
        """
        初始化模块，子类需要实现此方法
        """
        pass

    @abstractmethod
    def start(self) -> None:
        """
        启动模块，子类需要实现此方法
        这个韩式被调用就意味着他要正式开始工作了
        """
        pass

    async def stop(self) -> None:
        """
        停止模块，子类需要实现此方法
        如果没有其他需要清理的，可以直接 await super().stop() 然后结束
        被调用后你需要停止模块运行并释放资源，并完成分内的清理工作
        """
        # 清理路由
        for route in self._routes:
            self.api_server.remove_route(route)

        # 自动取消事件订阅
        for event_name, callback in self._events:
            self.event_bus.unsubscribe(event_name, callback)

        log.info(f"Module {self.name} stopped")

    def setup(self) -> None:
        """
        调用 initialize 方法并将模块标记为已初始化
        """
        if not self._initialized:
            self.initialize()
            self._initialized = True
            log.info(f"模块 {self.name} 已初始化")
