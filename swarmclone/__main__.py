from .controller import Controller
from .modules import *
from .constants import *
from .tts_cosyvoice import TTSCosyvoice
from .frontend_socket import FrontendSocket
from .llm_minilm2 import LLMMiniLM2
from .bilibili_chat import BiliBiliChat
from .asr_remote import ASRRemote
from .asr import ASRSherpa

if __name__ == "__main__":
    ## TODO：从命令行接收配置文件、模块列表等参数
    controller = Controller(config=Config())#("config/custom_settings.toml"))
    controller.register_module(FrontendSocket)
    # controller.register_module(TTSCosyvoice)
    # controller.register_module(LLMMiniLM2)
    # controller.register_module(BiliBiliChat)
    # controller.register_module(ASRRemote)
    controller.register_module(ASRSherpa)
    controller.start()
