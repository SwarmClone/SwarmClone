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

from typing import Any, Dict
from core.base_module import BaseModule
from core.routing import RequestType


class Echo(BaseModule):
    """Simple echo module for testing API routes"""
    
    async def init(self) -> None:
        """Initialize the echo module"""
        self.log_prefix = f"[{self.name.upper()}]"
        
        # Register config with API routes
        self.register_config_api(
            config_key="echo_prefix",
            default_value="ECHO: ",
            private=False
        )
        
        # Register API endpoints
        self.register_api_endpoint(
            request_type=RequestType.GET,
            path="/echo",
            endpoint=self.handle_echo_get,
            name="echo_get",
            description="Echo GET request"
        )
        
        self.register_api_endpoint(
            request_type=RequestType.POST,
            path="/echo",
            endpoint=self.handle_echo_post,
            name="echo_post",
            description="Echo POST request"
        )
        
        self.register_api_endpoint(
            request_type=RequestType.GET,
            path="/status",
            endpoint=self.handle_status,
            name="status",
            description="Get module status"
        )
        
        print(f"{self.log_prefix} Module initialized with API endpoints")
    
    async def handle_echo_get(self, message: str = "Hello"):
        """Handle GET echo request"""
        prefix = self.config_manager.get(self.name, "echo_prefix", "ECHO: ") if self.config_manager else "ECHO: "
        return {
            "message": f"{prefix}{message}",
            "method": "GET",
            "success": True
        }
    
    async def handle_echo_post(self, data: Dict[str, Any]):
        """Handle POST echo request"""
        prefix = self.config_manager.get(self.name, "echo_prefix", "ECHO: ") if self.config_manager else "ECHO: "
        return {
            "message": f"{prefix}{data}",
            "method": "POST",
            "success": True
        }
    
    async def handle_status(self):
        """Handle status request"""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "running": self.is_running,
            "status": "operational"
        }
    
    async def run(self) -> None:
        """Main module loop"""
        print(f"{self.log_prefix} Module running")
        while self.is_running:
            if await self.sleep_or_stop(5.0):
                print(f"{self.log_prefix} Still running...")
    
    async def pause(self) -> None:
        print(f"{self.log_prefix} Module paused")
    
    async def cleanup(self) -> None:
        print(f"{self.log_prefix} Cleaning up")
        if self.message_bus:
            await self.message_bus.unsubscribe(self.name)
    
    async def _register_message_handlers(self) -> None:
        pass