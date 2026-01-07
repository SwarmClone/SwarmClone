from calendar import c
from ..core.config_manager import ConfigManager
from typing import Any, Callable

from ..shared.logger import log
from ..core.event_bus import global_event_bus, Event
#测试用
#目前的构想是
# Controller把两个总线进一步包装，整个core部分只对外暴露Controller（否则很多模块可能要把3个部分都导入一遍）
# eventbus的执行混乱问题，可以在Controller里尝试解决
class Controller:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self):
        if Controller._initialized:
            log.debug(f"Controller has already been initialized !")
            return
        self.config_manager: ConfigManager = ConfigManager()
        self.event_bus = global_event_bus
        Controller._initialized = True

    def subscribe(self, modulename:str, config_events: dict[str, Callable[[Any], None]], message_events: dict[str, Callable[[Event], None]]) -> None:
        """
        订阅事件,支持配置变更事件和消息事件

        Args:
            config_events (dict): 订阅配置事件的模块名称
            message_events (dict): 订阅消息事件的模块名称
        """
        for event_name, callback in config_events.items():
            self.config_manager.event_bus.subscribe(modulename, event_name, callback)
        for event_name, callback in message_events.items():
            self.event_bus.subscribe(event_name, callback)

    def configure_change(self,data:dict[str,Any]):
        #测试用的设置更改推送接口
        #后续可能会改成别的形式
        errors:dict[str,str] = {}
        for event_type, config_data in data.items():
            try:
                self.config_manager.event_bus.publish(event_type, config_data)
            except RuntimeError as e:
                errors[event_type] = str(e)
        if errors:
            raise RuntimeError(f"Failed to apply some config changes: {errors}")
            
    async def event_message_publish(self, data:Event):
        #测试用的消息推送接口
        #后续可能会改成别的形式
        await self.event_bus.publish(data)