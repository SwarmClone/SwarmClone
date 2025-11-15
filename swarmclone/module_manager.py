from typing import Any
from swarmclone.types import ConfigInfo
from swarmclone.constants import *
from swarmclone.messages import *
from dataclasses import dataclass
import asyncio

class ModuleManager(type):
    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        attrs["name"] = name
        new_class = super().__new__(cls, name, bases, attrs)
        if name != "ModuleBase" and attrs["role"] not in [ModuleRoles.CONTROLLER]:
            assert attrs["role"] != ModuleRoles.UNSPECIFIED, "请指定模块角色"
            print(f"Registering module {name}")
            module_classes[attrs["role"]][name] = new_class # type[ModuleBase] 就是 Self@ModuleManager # pyright: ignore[reportArgumentType]
        return new_class

@dataclass
class ModuleConfig:
    """默认配置——没有配置项"""

class ModuleBase(metaclass=ModuleManager):
    role: ModuleRoles = ModuleRoles.UNSPECIFIED
    config_class = ModuleConfig
    name: str = "ModuleBase" # 会由metaclass自动赋值为类名
    def __init__(self, config: config_class | None = None, **kwargs):
        self.config = self.config_class(**kwargs) if config is None else config
        self.task_queue: asyncio.Queue[Message[Any]] = asyncio.Queue(maxsize=128)
        self.results_queue: asyncio.Queue[Message[Any]] = asyncio.Queue(maxsize=128)
        self.running = False
        self.err: BaseException | None = None
    
    async def run(self) -> None:
        while True:
            try:
                task = self.task_queue.get_nowait()
            except asyncio.QueueEmpty:
                task = None
            result = await self.process_task(task)
            if result is not None:
                await self.results_queue.put(result)
            await asyncio.sleep(0.1)

    def __repr__(self):
        return f"<{self.role} {self.name}>"

    @classmethod
    def get_config_schema(cls) -> ConfigInfo:
        """
        获取模块的配置信息模式
        
        返回一个包含模块配置信息的字典，结构如下：
        {
            "module_name":【模块名字】
            "desc":【介绍】,
            "config":[
                {
                    "name":【配置项名字】
                    "type":【类型，int整数float小数（默认小数点后2位精度）str字符串bool布尔值（是/否）selection选择项】,
                    "desc":【介绍信息】,
                    "required":【布尔值，是否必填】,
                    "default":【默认值】,
                    "options":【可选项，仅对选择项有用，若为空则为无选项】,
                    "multiline":【是否为多行文本，默认不是】,
                    "min":【最小值】,
                    "max":【最大值】,
                    "step":【步长】 # 对于整数，默认为1，对于小数，默认为0.01,
                    "password": 【是否需要隐藏输入值，默认为否】
                },...
            ]
        }
        """
        from dataclasses import fields, MISSING
        from swarmclone.utils import escape_all
        
        config_info: ConfigInfo = {
            "module_name": cls.name,
            "desc": cls.__doc__ or "",
            "config": []
        }
        
        # 跳过占位模块
        if "dummy" in cls.name.lower():
            return config_info
            
        for field in fields(cls.config_class):
            name = field.name
            default = ""
            
            # 将各种类型转换为字符串表示
            _type: str
            raw_type = str(field.type)
            if "int" in raw_type and "float" not in raw_type:  # 只在一个参数只能是int而不能是float时确定其为int
                _type = "int"
            elif "float" in raw_type:
                _type = "float"
            elif "bool" in raw_type:
                _type = "bool"
            else:
                _type = "str"
            
            selection = field.metadata.get("selection", False)
            if selection:
                _type = "selection"  # 如果是选择项则不管类型如何
            
            required = field.metadata.get("required", False)
            desc = field.metadata.get("desc", "")
            options = field.metadata.get("options", [])
            
            if field.default is not MISSING and (default := field.default) is not None:
                pass
            elif field.default_factory is not MISSING and (default := field.default_factory()) is not None:
                pass
            else:  # 无默认值则生成对应类型的空值
                if _type == "str":
                    default = ""
                elif _type == "int":
                    default = 0
                elif _type == "float":
                    default = 0.0
                elif _type == "bool":
                    default = False
                elif _type == "selection":
                    default = options[0]["value"] if options else ""

            # 是否是多行文本？
            multiline = field.metadata.get("multiline", False)
                    
            if isinstance(default, str) and not multiline: # 多行文本不需要转义
                default = escape_all(default)  # 进行转义
            
            # 如果有的话，提供最大最小值和步长
            minimum = field.metadata.get("min")
            if minimum is not None:
                minimum = float(minimum)
            maximum = field.metadata.get("max")
            if maximum is not None:
                maximum = float(maximum)
            step = field.metadata.get("step")
            if step is not None:
                step = float(step)
            elif _type == "int":
                step = 1.0
            elif _type == "float":
                step = 0.01
            
            # 是否需要隐藏输入值？
            password = field.metadata.get("password", False)
            
            config_info["config"].append({
                "name": name,
                "type": _type,
                "desc": desc,
                "required": required,
                "default": default,
                "options": options,
                "min": minimum,
                "max": maximum,
                "step": step,
                "password": password,
                "multiline": multiline
            })
        
        return config_info

    async def process_task(self, task: Message[Any] | None) -> Message[Any] | None:
        """
        处理任务的方法，每个循环会自动调用
        返回None表示不需要返回结果，返回Message对象则表示需要返回结果，返回的对象会自动放入results_queue中。
        也可以选择手动往results_queue中put结果然后返回None
        """

module_classes: dict[ModuleRoles, dict[str, type[ModuleBase]]] = {
    role: {} for role in ModuleRoles if role not in [ModuleRoles.UNSPECIFIED, ModuleRoles.CONTROLLER]
}

__all__ = [
    "ModuleBase",
    "ModuleConfig",
    "module_classes",
    "ModuleManager"
]
