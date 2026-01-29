from pathlib import Path
from typing import Any, Callable, Dict
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from utils.logger import log


class ConfigEventBus:
    def __init__(self):
        # str: 配置名称, Dict[str, Callable]: 需要订阅这个配置的模块和其对应的回调函数
        self._subscribers: Dict[str, Dict[str, Callable]] = {}  # type: ignore

    def subscribe(self, module_name: str, event_name: str, callback: Callable[[Any], None]) -> None:
        """
        订阅特定类型的配置变更事件。只有订阅了相同 event_name 的模块才能接收特定的配置更改。
        这考虑到配置中的一个更改可能需要多个模块来处理它。

        :param module_name: 订阅模块的名称，用于标识订阅者
        :param event_name: 事件名称字符串，用于区分不同类型的配置变更事件
        :param callback: 回调函数，当事件发生时被调用，回调函数收到的就是新的配置的值
        :return: 无返回值
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = {}
        self._subscribers[event_name][module_name] = callback
        log.debug(f"Module {module_name} subscribed to event {event_name}")

    def publish(self, event_name: str, config_data: Any) -> None:
        """
        发布配置更变事件给所有订阅该事件的模块
        :param event_name: 事件类型
        :param config_data: 配置数据，将传递给所有订阅该事件的模块
        :return:  无返回值
        """
        if event_name in self._subscribers:
            log.debug(f"Publishing event {event_name} to {len(self._subscribers[event_name])} modules")
            # 遍历所有订阅了该事件的模块
            for module_name, callback in self._subscribers[event_name].items():
                try:
                    callback(config_data)
                except Exception as e:
                    log.error(f"Error notifying module {module_name} for event {event_name}: {e}")


class ConfigManager:
    """
    ConfigManager 可以在 YAML 文件中加载和保存配置数据
    它为模块订阅配置更改提供了一个事件总线
    """
    def __init__(self, config_file: Path = Path("config.yml")):
        self.config_file = config_file
        self.yaml = YAML()
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.yaml.preserve_quotes = True
        self.config_data: CommentedMap = CommentedMap()  # Keep comments in config file
        self.event_bus = ConfigEventBus()
        self._load_config()

    def _load_config(self) -> None:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_data = self.yaml.load(f)
                    if isinstance(loaded_data, CommentedMap):
                        self.config_data = loaded_data
                    elif loaded_data is None:
                        self.config_data = CommentedMap()
                        log.warning(f"Empty YAML file {self.config_file}, using empty config")
                    else:
                        # 如果不是CommentedMap，转换一下
                        self.config_data = CommentedMap(loaded_data)
                log.info(f"Configuration loaded from {self.config_file}")
            except Exception as e:
                log.error(f"Error loading configuration: {e}")
                self.config_data = CommentedMap()
        else:
            self.config_data = CommentedMap()
            self._save_config()
            log.info(f"Created new configuration file at {self.config_file}")

    def _save_config(self) -> None:
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.yaml.dump(self.config_data, f)
            log.debug(f"Configuration saved to {self.config_file}")
        except Exception as e:
            log.error(f"Error saving configuration: {e}")

    def _ensure_module_exists(self, module_name: str) -> None:
        if module_name not in self.config_data:
            self.config_data[module_name] = CommentedMap()
            self._save_config()

    def get(self, module_name: str, config_key: str, default: Any = None) -> Any:
        """
        根据模块名和配置键值从配置数据中获取对应的配置值
        :param module_name:  模块名称，用于标识不同的配置模块
        :param config_key:  配置键名，用于在指定模块中查找具体的配置项
        :param default:  默认返回值，当指定的配置不存在时返回此值
        :return:  返回获取到的配置值，如果不存在则返回默认值
        """
        if module_name in self.config_data and config_key in self.config_data[module_name]:
            return self.config_data[module_name][config_key]
        return default

    def set(self, module_name: str, config_key: str, value: Any) -> None:
        """
        设置配置值，并发布配置更改事件
        :param module_name:  模块名称，指定要设置配置的模块
        :param config_key:  配置键名，指定要设置的配置项
        :param value:  配置值，要设置的值，可以是任意类型
        :return:  无返回值
        """
        self._ensure_module_exists(module_name)

        old_value = None
        if config_key in self.config_data[module_name]:
            old_value = self.config_data[module_name][config_key]

        self.config_data[module_name][config_key] = value
        self._save_config()

        # 只有当传入的配置值发生改变时才发布通知
        if old_value != value:
            event_name = f"{module_name}.{config_key}"
            self.event_bus.publish(event_name, value)
            log.debug(f"Config changed: {event_name} = {value}")

    def register(self, module_name: str, config_key: str,
                 default_value: Any, callback: Callable[[Any], None]) -> None:
        """
        注册一个配置键，当该配置键的值发生改变时，会调用 callback
        :param module_name:  模块名称，用于标识配置所属的模块
        :param config_key: 配置键的名称，用于标识具体的配置项
        :param default_value: 配置项的默认值，当配置项不存在时会使用此值
        :param callback: 回调函数，当配置值改变时会被调用，接收新的配置值作为参数
        :return:  无返回值
        """
        event_name = f"{module_name}.{config_key}"
        self.event_bus.subscribe(module_name, event_name, callback)

        if not self.has_config(module_name, config_key):
            self.set(module_name, config_key, default_value)

    def has_config(self, module_name: str, config_key: str) -> bool:
        """
        检查指定模块是否注册了某一个配置键
        :param module_name: 模块名
        :param config_key: 配置键名称
        :return: 是否注册了
        """
        return (
                module_name in self.config_data and
                config_key in self.config_data[module_name]
        )

    def get_module_configs(self, module_name: str) -> CommentedMap:
        """
        获取指定模块的所有配置
        :param module_name: 模块名
        :return: 一个 CommentedMap ，包含该模块注册的所有的配置键
        """
        self._ensure_module_exists(module_name)
        return self.config_data[module_name]