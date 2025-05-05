from .controller import Controller
from .modules import *
from .constants import *
from .tts_cosyvoice import TTSCosyvoice
from .frontend_socket import FrontendSocket
from .llm_minilm2 import LLMMiniLM2

if __name__ == "__main__":
    controller = Controller()
    controller.register(FrontendSocket())
    controller.register(TTSCosyvoice())
    controller.register(LLMMiniLM2())
    controller.start()
