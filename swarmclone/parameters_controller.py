import math
from typing import Callable
from torch.utils.data import dataset
from .constants import *
from .utils import *
from .modules import *
from .messages import *
from dataclasses import dataclass, field

available_actions = get_live2d_actions()
GLOBAL_REFRESH_RATE: int

class ActionCurve:
    """
    Live2D动作参数曲线
    参数控制格式
    [
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
        }, ...
    ]
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
    """Live2D模型动作"""
    def __init__(self, datas:list[dict[str, Any]]):
        self.curve: list[ActionCurve] = []
        for data in datas:
            self.curve.append(ActionCurve(data))


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
    role: ModuleRoles = ModuleRoles.PARAMETERS_CONTROLLER
    config_class = ParametersControllerConfig
    config: config_class
    
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        GLOBAL_REFRESH_RATE = self.config.refresh_rate
        self.actions: list[Action] = []
        self.parameters: dict[str, float] = {}
        for data in self.config.action:
            self.actions.append(Action(data))
        for action in self.actions:
            for curve in action.curve:
                if curve.paraname not in self.parameters:
                    self.parameters[curve.paraname] = 0
        self.active_action:list[Action] = []

    def update(self):
        for action in self.active_action:
            for curve in action.curve:
                if curve.paraname in self.parameters:
                    self.parameters[curve.paraname] = curve.updateparameter(self.parameters[curve.paraname])

def cosine_interpolation(a: float, b: float, t: float) -> float:
    # [0, 1] -> [0, pi] -cos-*-1-> [-1, 1] -/2-+0.5-> [0, 1]
    x = -math.cos(t * math.pi) / 2 + 0.5
    return a * (1 - x) + b * x

def quintic_interpolation(a: float, b: float, t: float) -> float:
    x = 6 * t ** 5 - 15 * t ** 4 + 10 * t ** 3
    return a * (1 - x) + b * x

def multioctave_perlin_noise(
    x: float,
    interpolation: Callable[[float, float, float], float],
    octaves: int | None = None,
    persistence: float | None = None,):
    total = 0
    if octaves is not None and persistence is not None:
        amplitudes = [persistence ** i for i in range(octaves)]
    else:
        raise ValueError("Either amplitudes or octaves and persistence must be provided.")
    total_amp = sum(amplitudes)
    highest_freq = 2 ** (octaves - 1)
    x = x / highest_freq
    for i in range(octaves):
        frequency = 2 ** i
        total += smooth_perlin_noise(x * frequency, interpolation) * amplitudes[i]
    return total / total_amp

def smooth_perlin_noise(x: float, interpolation: Callable[[float, float, float], float]):
    perm_table = [
        151,160,137,91,90,15,
		131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,
		190, 6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,
		88,237,149,56,87,174,20,125,136,171,168, 68,175,74,165,71,134,139,48,27,166,
		77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,
		102,143,54, 65,25,63,161, 1,216,80,73,209,76,132,187,208, 89,18,169,200,196,
		135,130,116,188,159,86,164,100,109,198,173,186, 3,64,52,217,226,250,124,123,
		5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,
		223,183,170,213,119,248,152, 2,44,154,163, 70,221,153,101,155,167, 43,172,9,
		129,22,39,253, 19,98,108,110,79,113,224,232,178,185, 112,104,218,246,97,228,
		251,34,242,193,238,210,144,12,191,179,162,241, 81,51,145,235,249,14,239,107,
		49,192,214, 31,181,199,106,157,184, 84,204,176,115,121,50,45,127, 4,150,254,
		138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180,
		151
    ]
    a: int = int(x)
    b = a + 1
    t = x - a
    value1 = (perm_table[a % 255] / 255 - 0.5) * 2
    value2 = (perm_table[b % 255] / 255 - 0.5) * 2
    return interpolation(value1, value2, t)