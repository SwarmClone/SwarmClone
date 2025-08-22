from . import *

if __name__ == "__main__":

    output = print_with_margin(module_classes, title="模块列表")
    log.opt(raw=True).info(f"{output}")

    controller = Controller()
    controller.run()
