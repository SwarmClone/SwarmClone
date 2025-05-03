from .controller import Controller
from .modules import *
from .constants import *
from .tts_cosyvoice import TTSCosyvoice

if __name__ == "__main__":
    controller = Controller()
    controller.register(FrontendDummy())
    controller.register(TTSCosyvoice())
    controller.register(LLMDummy())
    controller.register(ASRDummy())
    controller.start()
