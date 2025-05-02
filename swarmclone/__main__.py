from .controller import Controller
from .modules import *
from .constants import *

if __name__ == "__main__":
    controller = Controller()
    controller.register(ASRDummy())
    controller.register(FrontendDummy())
    controller.start()
