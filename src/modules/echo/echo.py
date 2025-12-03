import asyncio
from ..base_module import BaseModule
from typing import Any

from core.logger import log

class Echo(BaseModule):
    # Implementation of the echo module that simply echoes back messages
    def __init__(self, module_name: str):
        super().__init__(module_name)
        self.name = "echo"
        self.enabled = True
        self.prefix = "[ECHO]"
        # List of required configuration keys for this module
        self.required_configs = []

    async def _register_config_callbacks(self):
        # Register callbacks for configuration changes if needed
        pass

    async def init(self):
        # Initialize the module
        log.info(f"{self.prefix} Echo module initialized")
        # Register message handlers
        self._register_echo_handler()

    async def run(self):
        # Main entry point for module logic
        if self.enabled:
            log.info(f"{self.prefix} Echo module running")
            try:
                # Keep the module running until interrupted
                while True:
                    log.info(f"{self.prefix} Echo module is alive...")
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                log.info(f"{self.prefix} Echo module run task cancelled")

    async def pause(self):
        # Pause the module operations
        log.info(f"{self.prefix} Echo module paused")

    async def stop(self):
        # Cleanup and shutdown the module
        log.info(f"{self.prefix} Echo module stopped")

    def _register_echo_handler(self):
        # Register handlers for processing messages
        log.info(f"{self.prefix} Echo handler registered")

    def process_message(self, message: Any) -> Any:
        # Process and echo back incoming messages
        if self.enabled:
            response = f"{self.prefix} Echo: {message}"
            log.info(response)
            return response
        return None