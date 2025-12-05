# SwarmCloneBackend
# Copyright (c) 2025 SwarmClone <github.com/SwarmClone> and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any

from core.base_module import BaseModule
from core.logger import log


class Dummy111(BaseModule):
    
    def __init__(self, module_name: str):
        super().__init__(module_name)
        self.echo_count = 0
    
    async def init(self) -> None:
        """Initialize the echo module"""
        await super().init()
        
        await self.subscribe("echo.request", self._handle_echo_request)
        await self.subscribe("echo.*", self._handle_wildcard_echo)
        
        log.info(f"{self.prefix} Echo handlers registered")
    
    async def _register_message_handlers(self) -> None:
        """Register additional message handlers"""
        # This is called by base class init
        pass
    
    async def _handle_echo_request(self, message: Any) -> Any:
        """Handle echo request messages"""
        self.echo_count += 1
        response = f"{self.prefix} Echo #{self.echo_count}: {message}"
        log.info(response)
        return response
    
    async def _handle_wildcard_echo(self, message: Any) -> None:
        """Handle wildcard echo messages (no response)"""
        log.debug(f"{self.prefix} Wildcard echo: {message}")
    
    async def run(self) -> None:
        """Main module loop"""
        log.info(f"{self.prefix} Echo module running")
        
        iteration = 0
        while self.is_running:
            iteration += 1
            
            # Demonstrate various log levels
            if iteration % 10 == 0:
                log.error(f"{self.prefix} This is a sample error log (iteration {iteration})")
            elif iteration % 7 == 0:
                log.critical(f"{self.prefix} This is a sample critical log (iteration {iteration})")
            elif iteration % 5 == 0:
                log.warning(f"{self.prefix} This is a sample warning log (iteration {iteration})")
            elif iteration % 3 == 0:
                log.debug(f"{self.prefix} This is a sample debug log (iteration {iteration})")
            else:
                log.info(f"{self.prefix} Echo module alive (iteration {iteration})")
            
            completed = await self.sleep_or_stop(0.001)
            if not completed:
                log.info(f"{self.prefix} Stop requested, exiting run loop")
                break
    
    async def cleanup(self) -> None:
        """Clean up echo module resources"""
        log.info(f"{self.prefix} Cleaned up after {self.echo_count} echoes")
        await super().cleanup()
    
    # Public API methods
    async def echo_message(self, message: Any) -> str:
        """Public method to echo a message"""
        return f"{self.prefix} {message}"