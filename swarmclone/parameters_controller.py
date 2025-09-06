from swarmclone.constants import *
from swarmclone.utils import multioctave_perlin_noise, quintic_interpolation
from swarmclone.modules import *
from swarmclone.messages import *
from dataclasses import dataclass, field

available_actions = get_live2d_actions()

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
    def __init__(self, data: dict[str, Any], refresh_rate: int):
        try:
            self.paraname:list[str] = data["paraname"]
            self.duration:float = data["duration"]
            self.target:float = data["target"]
            self.noise:dict[str,float] = data["noise"]
            self.pid:dict[str,float] = data["pid"]
            self.duration_frame: int = int(self.duration * refresh_rate) if self.duration > 0 else -1
        except KeyError as e:
            raise ValueError(f"ActionCurve 初始化失败，缺少必要字段: {e}")
        self.framecount = 0
        self.pid_integral = 0
        self.pid_last_error = 0
    
    def updateparameter(self, current_value: float, bias:int) -> float:
        """
        更新参数值
        :param current_value: 当前参数值
        :return: 更新后的参数值
        """
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
            persistence=self.noise["persistence"],
            bias=bias) * self.noise["amplitude"]
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
    def __init__(self, action:dict[str, Any], refresh_rate: int):
        self.priority = action.get("priority", 0)
        self.name = action.get("name", "Unnamed Action")
        assert isinstance(self.priority, int), "优先级必须为整数"
        assert isinstance(self.name, str), "动作名称必须为字符串"
        self.curves: list[ActionCurve] = []
        for curve in action.get("curve", []):
            self.curves.append(ActionCurve(curve, refresh_rate))
    
    def update_action(self,parameters: dict[str, float],zmap: dict[str, float] )  -> bool:
        is_updated = False
        for i, curve in enumerate(self.curves):
            if not(curve.framecount == curve.duration_frame):
                curve.framecount += 1
                for param in curve.paraname:
                    if self.priority > zmap.get(param, 0):
                        is_updated = True
                        parameters[param] = curve.updateparameter(parameters[param],i)
                        zmap[param] = self.priority
        if not is_updated:
            self.reset_action()
        return is_updated  

    def reset_action(self):
        for curve in self.curves:
            curve.framecount = 0
            curve.pid_integral = 0
            curve.pid_last_error = 0

@dataclass
class ParametersControllerConfig(ModuleConfig):
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
        "desc": "刷新频率",
        "min": 1,
        "max": 60,
        "step": 1
    })

class ParametersController(ModuleBase):
    """Live2D模型参数控制器"""
    role: ModuleRoles = ModuleRoles.PARAM_CONTROLLER
    config_class = ParametersControllerConfig
    config: config_class
    
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.actions: dict[str, Action] = {}
        self.parameters: dict[str, float] = {}
        self.load_action_data()
        self.active_actions: list[Action] = []

    def update_parameter(self):
        zmap: dict[str, float] = {}
        # 过滤出需要保留的action
        self.active_actions = [action for action in self.active_actions 
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
                self.active_actions.append(self.actions[task.get("action_ids")])
                self.active_actions.sort(key=lambda x: x.priority, reverse=True)
            except asyncio.QueueEmpty:
                pass
            self.update_parameter()
            await self.results_queue.put(
                ParametersUpdate(self, self.parameters))
            await asyncio.sleep(1/self.config.refresh_rate)  # 等待下一帧
        
    def load_action_data(self):
        with open(self.config.action, 'r', encoding='utf-8') as f:
            data: list[dict[str, Any]] = json.load(f)
        for action in data:
            self.actions[action["name"]] = Action(action, self.config.refresh_rate)
        for action in self.actions.values():
            for curve in action.curves:
                for para in curve.paraname:
                    self.parameters[para]= 0
