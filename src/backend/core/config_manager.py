import json
from pathlib import Path
from typing import Any, Callable, Dict


from backend.shared.logger import log

class ConfigEventBus:
    """
    配置事件总线类
    用于处理配置更改事件的发布和订阅机制，允许模块在配置发生变更时收到通知
    """
    #配置总线应该不能有好几个吧。。
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if ConfigEventBus._initialized:
            log.debug(f"ConfigEventBus has already been initialized !")
            return
        # str: 配置名称, Dict[str, Callable]: 模块名对应回调函数
        self._subscribers: Dict[str, Dict[str, Callable]] = {}  # type: ignore
        ConfigEventBus._initialized = True

    # 只有当模块订阅了相同的配置名称时，才会收到该配置的变更通知
    # 这样的设计考虑到一个配置变更可能需要多个模块来处理
    def subscribe(self, module_name: str, event_type: str,
                  callback: Callable[[Any], None]) -> None:
        """
        订阅配置变更事件

        Args:
            module_name (str): 订阅事件的模块名称
            event_type (str): 配置事件名称，建议使用"模块名.配置键"的格式命名
            callback (Callable[[Any], None]): 当配置发生变更时调用的回调函数
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = {}
        self._subscribers[event_type][module_name] = callback
        log.debug(f"Module {module_name} subscribed to event {event_type}")

    def publish(self, event_type: str, config_data: Any) -> None:
        """
        发布配置变更事件

        Args:
            event_type (str): 要发布的配置事件类型
            config_data (Any): 新的配置数据，会传递给所有订阅该事件的模块
        """
        if event_type in self._subscribers:
            log.debug(f"Publishing event {event_type} to {len(self._subscribers[event_type])} modules")
            for module_name, callback in self._subscribers[event_type].items():
                try:
                    callback(config_data)
                except Exception as e:
                    log.error(f"Error notifying module {module_name} for event {event_type}: {e}")
                    raise RuntimeError(f"failed to notify module {module_name} for event {event_type}") from e
global_config_event_bus = ConfigEventBus()

class ConfigManager:
    """
    配置管理器类
    负责管理应用程序的配置数据，支持从JSON文件加载和保存配置，
    并提供事件总线机制以通知模块配置变更
    """
    def __init__(self, config_file: Path = Path("config.json")):
        self.config_file = config_file
        self.config_data: Dict[str, Any] = {}
        self.event_bus = ConfigEventBus()
        self._load_config()

    def _load_config(self) -> None:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict):
                        self.config_data = loaded_data
                    elif loaded_data is None:
                        self.config_data = {}
                        log.warning(f"Empty JSON file {self.config_file}, using empty config")
                    else:
                        # 如果不是字典，转换一下
                        self.config_data = dict(loaded_data)
                log.info(f"Configuration loaded from {self.config_file}")
            except Exception as e:
                log.error(f"Error loading configuration: {e}")
                self.config_data = {}
        else:
            self.config_data = {}
            self._save_config()
            log.info(f"Created new configuration file at {self.config_file}")

    def _save_config(self) -> None:
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
            log.debug(f"Configuration saved to {self.config_file}")
        except Exception as e:
            log.error(f"Error saving configuration: {e}")

    def _ensure_module_exists(self, module_name: str) -> None:
        if module_name not in self.config_data:
            self.config_data[module_name] = {}
            self._save_config()

    def get(self, module_name: str, config_key: str, default: Any = None) -> Any:
        """
        获取指定模块的配置值

        Args:
            module_name (str): 模块名称
            config_key (str): 配置键
            default (Any): 如果配置不存在时返回的默认值

        Returns:
            Any: 配置值，如果不存在则返回默认值
        """
        if module_name in self.config_data and config_key in self.config_data[module_name]:
            return self.config_data[module_name][config_key]
        return default

    def set(self, module_name: str, config_key: str, value: Any) -> None:
        """
        设置指定模块的配置值，并将配置更变保存到配置文件中

        Args:
            module_name (str): 模块名称
            config_key (str): 配置键
            value (Any): 要设置的配置值
        """
        self._ensure_module_exists(module_name)

        old_value = None
        if config_key in self.config_data[module_name]:
            old_value = self.config_data[module_name][config_key]

        self.config_data[module_name][config_key] = value
        self._save_config()

        # 只有当配置值真正改变时才发布变更通知
        if old_value != value:
            event_type = f"{module_name}.{config_key}"
            self.event_bus.publish(event_type, value)
            log.debug(f"Config changed: {event_type} = {value}")

    def register(self, module_name: str, config_key: str,
                 default_value: Any, callback: Callable[[Any], None]) -> None:
        """
        注册配置项并设置回调函数以接收配置变更通知

        Args:
            module_name (str): 模块名称
            config_key (str): 配置键
            default_value (Any): 默认配置值
            callback (Callable[[Any], None]): 配置变更时的回调函数
        """
        event_type = f"{module_name}.{config_key}"
        self.event_bus.subscribe(module_name, event_type, callback)

        if not self.has_config(module_name, config_key):
            self.set(module_name, config_key, default_value)

    def has_config(self, module_name: str, config_key: str) -> bool:
        """
        检查指定模块是否具有指定的配置项

        Args:
            module_name (str): 模块名称
            config_key (str): 配置键

        Returns:
            bool: 如果配置项存在返回True，否则返回False
        """
        return (
                module_name in self.config_data and
                config_key in self.config_data[module_name]
        )
