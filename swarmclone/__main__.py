from . import *

if __name__ == "__main__":
    controller = Controller()
    controller.register(ASRDummy())
    controller.register(FrontendDummy())
    controller.start()
