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
from pydantic import BaseModel

from core.base_module import BaseModule
from core.config_manager import ConfigManager
from core.api_server import RequestType
from core.logger import log


class SampleRequest(BaseModel):
    """Sample request model for demonstration"""
    message: str
    count: int = 1


class SampleModule(BaseModule):
    """Sample module that demonstrates basic module functionality"""
    
    def __init__(self, module_name: str):
        super().__init__(module_name)
        self.config_item_1 = None

    async def pre_init(self, config_manager: ConfigManager) -> None:
        await super().pre_init(config_manager)

        self.config_manager = config_manager

        self.register_config_with_routes(
            config_key="config_item_1_test01",
            default_value="This is a test config item",
            callback=self.config_callback_01,
            private=False
        )
        
        self.register_config_with_routes(
            config_key="private_config_item",
            default_value="This is a private config item",
            callback=self.config_callback_02,
            private=True    # This config item will not be exposed via API
        )

        await self._register_message_handlers()

        self.echo_count = 0

        log.info(f"{self.prefix} Module Pre-initialized")
    
    async def init(self) -> None:
        await super().init()
        
        self.register_control_api(
            request_type=RequestType.GET,
            path="/",
            endpoint=self.get_module_info,
            summary="Get module information",
            description="Returns information about the sample module"
        )
        
        self.register_control_api(
            request_type=RequestType.POST,
            path="/echo",
            endpoint=self.echo_message,
            response_model=dict,
            summary="Echo a message",
            description="Echoes back the provided message"
        )
        
        self.register_control_api(
            request_type=RequestType.GET,
            path="/stats",
            endpoint=self.get_stats,
            summary="Get module statistics",
            description="Returns statistical information about the module"
        )
        
        log.info(f"{self.prefix} Module initialized with custom APIs")
        
    async def _register_message_handlers(self) -> None:
        # Register message handlers
        await self.subscribe("echo.request", self._handle_echo_request)
        await self.subscribe("echo.*", self._handle_wildcard_echo)
    
    async def _handle_echo_request(self, message: Any) -> Any:
        """Handle echo request messages"""
        self.echo_count += 1
        response = f"{self.prefix} Module received echo request #{self.echo_count}: {message}"
        log.info(response)
        return response
    
    async def _handle_wildcard_echo(self, message: Any) -> None:
        """Handle wildcard echo messages (no response)"""
        log.debug(f"{self.prefix} Wildcard echo: {message}")

    def config_callback_01(self, config_data: Any) -> None:
        """Handle config item 1 changes"""
        log.info(f"{self.prefix} Config item 1 changed: {config_data}")

    def config_callback_02(self, config_data: Any) -> None:
        """Handle config item 2 changes"""
        log.info(f"{self.prefix} Private config item changed: {config_data}")
    
    # API Endpoints
    async def get_module_info(self):
        """Get module information endpoint"""
        return {
            "module": self.name,
            "category": self.category,
            "enabled": self.enabled,
            "running": self.is_running,
            "echo_count": self.echo_count,
            "description": "Sample module demonstrating API registration"
        }
    
    async def echo_message(self, request: SampleRequest):
        """Echo message endpoint"""
        response = {
            "original_message": request.message,
            "count": request.count,
            "echoed": [f"{self.prefix}: {request.message}" for _ in range(request.count)]
        }
        
        await self.publish("echo.request", request.message)
        
        return response
    
    async def get_stats(self):
        """Get module statistics endpoint"""
        return {
            "echo_count": self.echo_count,
            "is_running": self.is_running,
            "config_item_value": self.config_manager.get(self.name, "config_item_1_test01", "default"), # type: ignore
            "status": "active" if self.is_running else "inactive"
        }
    
    async def run(self) -> None:
        """Main module loop"""
        log.info(f"{self.prefix} Sample module running")
        
        iteration = 0
        while self.is_running:
            iteration += 1
            
            if iteration % 50 == 0:
                await self.publish("echo.request", f"{self.prefix} Automatic echo #{iteration}")
            
            if iteration % 250 == 0:
                current_config = self.config_manager.get(self.name, "config_item_1_test01", "default") # type: ignore
                log.debug(f"{self.prefix} Current config: {current_config}")
            
            completed = await self.sleep_or_stop(0.01)
            if not completed:
                log.info(f"{self.prefix} Stop requested, exiting run loop")
                break

    async def pause(self) -> None:
        """Pause module operations"""
        log.info(f"{self.prefix} Module paused")
    
    async def cleanup(self) -> None:
        """Clean up sample module resources"""
        log.info(f"{self.prefix} Cleaned up after {self.echo_count} echoes")
        await super().cleanup()