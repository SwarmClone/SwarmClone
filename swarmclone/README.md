## 模块开发模式：
```python
# my_module.py
from swarmclone.module_bootstrap import *
from dataclasses import dataclass, field
import asyncio

@dataclass
class MyModuleConfig(ModuleConfig):
    # 此处填写模块配置项
    # 模块配置项仅支持：字符串、数值、布尔值
    my_config: str = field(default="这是默认值", metadata={
        "required": True, # 是否必填？未提供则为False
        "desc": "这里是配置项介绍", # 配置项介绍，未提供则为空
        "selection": True, # 是否是选择项？未提供则为False
        "options": [ # 仅当为选择项时有用
            {"key": "这是一个预置项——显示的名称", "value": "这是默认值"} # value 是这个选项实际代表的内容，默认值必须被包含在某个选项内
        ]
    })
    my_number_config: int = field(default=1, metadata={
        "required": True,
        "desc": "这里是配置项介绍",
        "selection": False,
        "min": 1, # 最小最大值和步长，如果想要数值类型显示为滑条则可提供
        "max": 100, # 若未提供则仅显示输入框
        "step": 5 # 若无步长默认为1
    })
    my_float_config: float = field(default=1.0, metadata={
        "required": True,
        "desc": "这里是配置项介绍",
        "selection": False,
        "min": 1.0,
        "max": 100.0,
        "step": 5.0 # 若无步长默认为0.01
    })
    minimal_float_config: float = field(default=1.0) # 显示为一个小数输入框，默认值为1.0，无配置项介绍

class MyModule(ModuleBase):
    role: ModuleRoles = ModuleRoles.PLUGIN # 模型角色，可选项见constants.py
    config_class = MyModuleConfig # 声明配置类
    config: config_class # 不必须，声明配置类型，防止静态类型检查器报错
    def __init__(self, config: config_class | None = None, **kwargs): # 为了同时支持传入 config 和传入单独配置项两种方式
        super().__init__(config, **kwargs)
        # 模块初始化代码，将在模块被加载时运行
    
    async def run(self):
        # 模型启动后的主循环代码，不应主动退出
        # self.tasks_queue 是一个 asyncio.Queue ，外部发送来到 Message 对象会被放入队列，可通过 await self.tasks_queue.get() 等待获取
        # self.results_queue 是一个 asyncio.Queue ，你想发送的 Message 对象可通过 await self.results_queue.put() 放入队列
        # 几种基础 Message 对象的定义见 messages.py
        while True:
            await asyncio.sleep(1) # 主逻辑
```
以上示例并不完善，具体请见已有模块的定义。
只需在创建控制器时保证模块文件已被导入即可让此模块在 webui 中显示。
```python
# main.py
from swarmclone.controller import Controller
from my_module import *
if __name__ == "__main__":
    controller = Controller()
    controller.run()
```
也可选择将模块定义直接写入 plugins.py 中，这样直接使用 python -m swarmclone 即可使用此模块。
