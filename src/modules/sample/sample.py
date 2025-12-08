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
from core.config_manager import ConfigManager
from core.logger import log


class SampleModule(BaseModule):
    """Sample module that demonstrates basic module functionality"""
    
    def __init__(self, module_name: str):
        super().__init__(module_name)
        self.echo_count = 0

    async def pre_init(self, config_manager: ConfigManager) -> None:
        await super().pre_init(config_manager)

        self.config_manager = config_manager
        await self._register_message_handlers()

        log.info(f"{self.prefix} Module Pre-initialized")
    
    async def init(self) -> None:
        await super().init()
        
        # Register message handlers
        await self.subscribe("echo.request", self._handle_echo_request)
        await self.subscribe("echo.*", self._handle_wildcard_echo)
        
    async def _register_message_handlers(self) -> None:
        """Register additional message handlers"""
        # This is called by base class init
        pass
    
    async def _handle_echo_request(self, message: Any) -> Any:
        """Handle echo request messages"""
        self.echo_count += 1
        response = f"{self.prefix} Module received echo request #{self.echo_count}: {message}"
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
            
            await self.publish("echo.request", f"{self.prefix} Echo #{iteration}")
            
            await self.publish("echo.123456", f"{self.prefix} Echo #111111111aaa{iteration}")
            
            completed = await self.sleep_or_stop(0.001)
            if not completed:
                log.info(f"{self.prefix} Stop requested, exiting run loop")
                break

    async def pause(self) -> None:
        pass
    
    async def cleanup(self) -> None:
        """Clean up echo module resources"""
        log.info(f"{self.prefix} Cleaned up after {self.echo_count} echoes")
        await super().cleanup()