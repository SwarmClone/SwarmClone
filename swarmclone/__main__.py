from .controller import Controller
from .modules import *
from .constants import *
from .tts_cosyvoice import TTSCosyvoice
from .frontend_socket import FrontendSocket
from .llm_transformers import LLMTransformers
from .llm_api import LLMOpenAI
from .bilibili_chat import BiliBiliChat
from .asr import ASRSherpa
from .plugins import *

if __name__ == "__main__":
    ## TODO：从命令行接收配置文件、模块列表等参数
    controller = Controller(config=Config())
    controller.register_module(FrontendSocket)
    controller.register_module(TTSCosyvoice)
    controller.register_module(LLMOpenAI)
    controller.register_module(BiliBiliChat)
    controller.register_module(ASRSherpa)
    controller.register_module(ScheduledPlaylist)
    controller.start()
