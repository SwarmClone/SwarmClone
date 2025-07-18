from .module_manager import module_classes
from .controller import Controller
from .modules import *
from .constants import *
from .tts_cosyvoice import TTSCosyvoice
from .frontend_socket import FrontendSocket
from .llm_transformers import LLMTransformers
from .llm_api import LLMOpenAI
from .bilibili_chat import BiliBiliChat
from .asr import ASRSherpa
from .frontend_live2d import FrontendLive2D
from .plugins import *
from .ncatbot_modules import *

if __name__ == "__main__":
    print(f"{module_classes=}")
    controller = Controller()
    controller.run()
    pass
