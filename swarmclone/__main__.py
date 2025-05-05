from .controller import Controller
from .modules import *
from .constants import *
from .tts_cosyvoice import TTSCosyvoice
from .frontend_socket import FrontendSocket

if __name__ == "__main__":
    controller = Controller()
    controller.register(FrontendSocket())
    controller.register(TTSCosyvoice())
    controller.register(LLMDummy())
    controller.register(ASRDummy())
    controller.start()
