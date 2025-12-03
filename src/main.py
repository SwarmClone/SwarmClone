from core.module_manager import Controller
import sys

from core.logger import log


def main():
    log.info("Starting SwarmCloneBackend...")
    controller = Controller()
    controller.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Program terminated by user")
        sys.exit(0)
    except Exception as e:
        log.error(f"Error: {e}")
        sys.exit(1)