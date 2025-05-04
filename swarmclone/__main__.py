from .controller import Controller
from .modules import *
from .constants import *
from .tts_cosyvoice import TTSCosyvoice
from .Frontend import frontend

if __name__ == "__main__":
    controller = Controller()
    controller.register(frontend())
    controller.register(TTSCosyvoice())
    controller.register(LLMDummy())
    controller.register(ASRDummy())
    controller.start()
