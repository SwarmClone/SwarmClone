from ..base_module import BaseModule

class Echo(BaseModule):
    def __init__(self, config):
        super().__init__(config)
        self.name = "echo"
        self.enabled = config.get("enabled", True)
        self.prefix = config.get("prefix", "[ECHO]")

    def initialize(self):
        print(f"{self.prefix} Echo module initialized")

    def start(self):
        if self.enabled:
            print(f"{self.prefix} Echo module started")
            self._register_echo_handler()

    def stop(self):
        print(f"{self.prefix} Echo module stopped")

    def _register_echo_handler(self):
        print(f"{self.prefix} Echo handler registered")

    def process_message(self, message):
        if self.enabled:
            response = f"{self.prefix} Echo: {message}"
            print(response)
            return response
        return None
