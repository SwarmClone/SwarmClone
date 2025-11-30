from ..base_module import BaseModule

class Dummy(BaseModule):
    def __init__(self, config):
        super().__init__(config)
        self.name = "dummy"
        self.enabled = config.get("enabled", True)
        self.prefix = config.get("prefix", "[Dummy]")

    def initialize(self):
        print(f"{self.prefix} Dummy module initialized")

    def start(self):
        if self.enabled:
            print(f"{self.prefix} Dummy module started")
            self._register_echo_handler()

    def stop(self):
        print(f"{self.prefix} Dummy module stopped")

    def _register_echo_handler(self):
        print(f"{self.prefix} Dummy handler registered")

    def process_message(self, message):
        if self.enabled:
            response = f"{self.prefix} Dummy: {message}"
            print(response)
            return response
        return None
