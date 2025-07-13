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
from .ncatbot_modules import *

if __name__ == "__main__":
    ## TODO：从命令行接收配置文件、模块列表等参数
    controller = Controller(config=Config())
    controller.register_module(ScheduledPlaylist)
    # controller.register_module(FrontendDummy)                # 只打印log到终端
    # controller.register_module(FrontendSocket)  # 使用Socket与swarmcloneunity配套
    # controller.register_module(LLMOpenAI)       # 使用OpenAI API比如DeepSeek就用这个
    controller.register_module(LLMTransformers)              # 使用本地模型比如Qwen3或MiniLM2就用这个
    # controller.register_module(BiliBiliChat)                 # 去配置文件里填写B站账号信息可以连接到B站读取弹幕
    # controller.register_module(ASRSherpa)       # ASR语音输入，配合SwarmClient使用
    # controller.register_module(TTSCosyvoice)    # TTS模型，仅在有swarmcloneunity时能正常播放
    controller.register_module(NCatBotChat)
    controller.register_module(NCatBotFrontend)
    controller.start()
