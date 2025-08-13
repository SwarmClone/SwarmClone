import math
from typing import Callable
from .constants import *
from .utils import multioctave_perlin_noise, quintic_interpolation
from .modules import *
from .messages import *
from dataclasses import dataclass, field

available_actions = get_live2d_actions()
GLOBAL_REFRESH_RATE: int

class ActionCurve:
    """
    Live2D动作参数曲线
    每个参数曲线包含以下信息：
    {
        "paraname": str, 控制参数名称
        "duration": float, 持续时间，单位秒
        "target": float, 目标值基准值
        "noise": dict[str, float], 噪声参数
            {
                "amplitude": float, 噪声振幅
                "persistence": float, 噪声持续度
                
            }
        "pid": dict[str, float], PID控制参数
            {
                "p": float, 比例系数
                "i": float, 积分系数
                "d": float, 微分系数
            }
    }
    """
    def __init__(self, data: dict[str, Any]):
        self.paraname:str = data.get("paraname")
        self.duration:float = data.get("duration", -1)
        self.target:float = data.get("target")
        self.noise:dict[str,float] = data.get("noise", {"amplitude": 0, "persistence": 0})
        self.pid:dict[str,float] = data.get("pid", {"p": 0, "i": 0, "d": 0})
        self.duration_frame: int = int(self.duration * GLOBAL_REFRESH_RATE) if self.duration > 0 else -1

        self.framecount = 0
        self.pid_integral = 0
        self.pid_last_error = 0
    
    def updateparameter(self, current_value: float) -> float:
        """
        更新参数值
        :param current_value: 当前参数值
        :return: 更新后的参数值
        """
        self.framecount += 1
        error = self.target - current_value
        self.pid_integral += error
        self.pid_last_error = error
        pid_update = (
            self.pid["p"] * error +
            self.pid["i"] * self.pid_integral +
            self.pid["d"] * (error - self.pid_last_error))
        noise = multioctave_perlin_noise(
            x=self.framecount,
            interpolation=quintic_interpolation,
            persistence=self.noise["persistence"],) * self.noise["amplitude"]
        current_value += pid_update + noise
        return current_value

class Action:
    """
    Live2D模型动作
    每个动作包含多个参数曲线，单个动作文件如下
    {
        "name": str, 动作名称
        "priority": int, 优先级，数值越大优先级越高
        "curve": list[ActionCurve], 参数曲线列表
        [
            {curve1_data},
            {curve2_data},
            ...
        ]
    }
    curve1_data 和 curve2_data 的格式同 ActionCurve 中定义的格式
    """
    def __init__(self, action:dict[str, Any]):
        self.priority = action.get("priority", 0)
        self.name = action.get("name", "Unnamed Action")
        assert isinstance(self.priority, int), "优先级必须为整数"
        assert isinstance(self.name, str), "动作名称必须为字符串"
        self.curve: list[ActionCurve] = []
        for curve in action.get("curve", []):
            self.curve.append(ActionCurve(curve))
    
    def update_action(self,parameters: dict[str, float],zmap: dict[str, float] )  -> bool:
        is_updated = False
        for curve in self.curve:
            if not(curve.framecount == curve.duration_frame):
                is_updated = True
                if self.priority > zmap.get(curve.name, 0):
                    curve.updateparameter(parameters[curve.name])
                    zmap[curve.name] = self.priority
        if not is_updated:
            self.reset_action()
        return is_updated  

    def reset_action(self):
        for curve in self.curve:
            curve.framecount = 0
            curve.pid_integral = 0
            curve.pid_last_error = 0
    
    
        

@dataclass
class ParametersControllerConfig:
    action: str = field(default=[*available_actions.values()][0], metadata={
        "required": True,
        "desc": "Live2D模型动作文件",
        "selection": True,
        "options": [
            {"key": k, "value": v} for k, v in available_actions.items()
        ]
    })
    
    refresh_rate: int = field(default=20, metadata={
        "required": True,
        "desc": "刷新率（帧每秒）",
        "selection": True,
        "options": [
            {"key": "20", "value": 20}
        ]
    })

class ParametersController(ModuleBase):
    """Live2D模型参数控制器"""
    role: ModuleRoles = ModuleRoles.PLUGIN
    config_class = ParametersControllerConfig
    config: config_class
    
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        GLOBAL_REFRESH_RATE = self.config.refresh_rate
        self.actions: dict[str,Action] = []
        self.parameters: dict[str, float] = {}
        self.load_action_data()
        self.active_action:list[Action] = []

    def update_parameter(self):
        zmap: dict[str, float] = {}
        # 过滤出需要保留的action
        self.active_action = [action for action in self.active_action 
                         if action.update_action(self.parameters, zmap)]

    async def run(self) -> None:
        """
        收到的Message样式
        {
            message_type: "data",
            source: "..."
            destinations: ["PLUGIN"],
            action: "action_name"
        }
        """
        while True:
            try:
                task = self.task_queue.get_nowait()
                self.active_action.append(self.actions[task.get_value(self).get("action")])
                self.active_action.sort(key=lambda x: x.priority, reverse=True)
            except asyncio.QueueEmpty:
                pass
            self.update_parameter()
            self.results_queue.put_nowait(
                ParametersUpdate(self, self.parameters))
            await asyncio.sleep(1/GLOBAL_REFRESH_RATE)  # 等待下一帧


        
    def load_action_data(self):
        data:list[dict[str,Any]] = json.loads(self.config.action)
        for action in data:
            self.actions.append(action.get("name"),Action(data))
        for action in self.actions.values():
            for curve in action.curve:
                if curve.paraname not in self.parameters:
                    self.parameters[curve.paraname]= 0


