import asyncio
from ..base_module import BaseModule
from typing import Any

from core.logger import log

class Dummy(BaseModule):
    # Implementation of the dummy module for testing purposes
    def __init__(self, module_name: str):
        super().__init__(module_name)
        self.name = "dummy"
        self.enabled = True
        self.prefix = "[Dummy]"
        # List of required configuration keys for this module
        self.required_configs = []

    async def _register_config_callbacks(self):
        # Register callbacks for configuration changes if needed
        pass

    async def init(self):
        # Initialize the module
        log.info(f"{self.prefix} Dummy module initialized")
        # Simulate initialization process
        self._register_echo_handler()

    async def run(self):
        # Main entry point for module logic
        if self.enabled:
            log.info(f"{self.prefix} Dummy module running")
            try:
                # Keep the module running until interrupted
                while True:
                    log.info(f"{self.prefix} Dummy module is alive...")
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                log.warning(f"{self.prefix} Dummy module run task cancelled")

    async def pause(self):
        # Pause the module operations
        log.info(f"{self.prefix} Dummy module paused")

    async def stop(self):
        # Cleanup and shutdown the module
        log.info(f"{self.prefix} Dummy module stopped")

    def _register_echo_handler(self):
        # Register handlers for processing messages or events
        log.info(f"{self.prefix} Dummy handler registered")

    def process_message(self, message: Any) -> Any:
        # Process incoming messages
        if self.enabled:
            response = f"{self.prefix} Dummy: {message}"
            log.info(response)
            return response
        return None