from .constants import *
from .utils import *
from .modules import *
from .messages import *
from dataclasses import dataclass, field

available_models = get_live2d_models()
@dataclass
class FrontendLive2DConfig(ModuleConfig):
    model: str = field(default=[*available_models.values()][0], metadata={
        "required": True,
        "desc": "Live2D模型",
        "selection": True,
        "options": [
            {"key": k, "value": v} for k, v in available_models.items()
        ]
    })

class FrontendLive2D(ModuleBase):
    """使用 live2d-py 和 PySide6 驱动的 Live2D 前端"""
    role: ModuleRoles = ModuleRoles.FRONTEND
    config_class = FrontendLive2DConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
