from abc import ABC, abstractmethod
from typing import Optional, Callable, Any

from core.api_server import APIServer
from core.config_manager import ConfigManager
from core.event_bus import EventBus
from utils.logger import log


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
        if callback is None:
            # 如果没有提供回调函数，就创建一个默认的
            callback = lambda value: log.debug(f"配置 {self.name}.{config_key} 变更为 {value}")

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

    def add_route(self, path: str, methods: list = None, handler: Callable = None) -> None:
        """
        为当前模块注册一个API路由，路径会自动添加模块名前缀

        :param path: 路由路径，不需要包含模块名前缀
        :param methods: HTTP方法列表，如 ['GET', 'POST']
        :param handler: 处理函数
        :return 无返回值
        """
        if methods is None:
            methods = ['GET']

        # 自动添加模块名前缀
        full_path = f"/{self.name}{path}"
        self.api_server.add_route(full_path, methods, handler)
        log.debug(f"已注册路由 {full_path}，方法: {methods}")

    def subscribe_event(self, event_name: str, callback: Callable[[Any], None]) -> None:
        """
        订阅一个事件，事件类型会自动添加模块名前缀

        :param event_name: 事件名称，不需要包含模块名前缀
        :param callback: 事件回调函数
        :return 无返回值
        """
        full_event_name = f"{self.name}.{event_name}"
        self.event_bus.subscribe(self.name, full_event_name, callback)
        log.debug(f"模块 {self.name} 已订阅事件 {full_event_name}")

    def publish_event(self, event_name: str, data: Any = None) -> None:
        """
        发布一个事件，事件类型会自动添加模块名前缀

        :param event_name: 事件类型，不需要包含模块名前缀
        :param data: 事件数据
        :return 无返回值
        """
        full_event_name = f"{self.name}.{event_name}"
        self.event_bus.publish(full_event_name, data)
        log.debug(f"模块 {self.name} 已发布事件 {full_event_name}")

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

    @abstractmethod
    def stop(self) -> None:
        """
        停止模块，子类需要实现此方法
        被调用后你需要停止模块运行并释放资源，并完成分内的清理工作
        """
        pass

    def setup(self) -> None:
        """
        调用 initialize 方法并将模块标记为已初始化
        """
        if not self._initialized:
            self.initialize()
            self._initialized = True
            log.info(f"模块 {self.name} 已初始化")
