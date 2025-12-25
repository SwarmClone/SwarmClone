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

from typing import Any, Dict, List, Optional

from src.base_module import BaseModule
from src.config_manager import ConfigManager
from src.logger import log


class ExampleAPIModule(BaseModule):
    """Example API module that demonstrates dynamic route registration"""
    
    def __init__(self, module_name: str):
        super().__init__(module_name)
        self.config_manager: Optional[ConfigManager] = None
        self.registered_routes: List[str] = []
        self.counter: int = 0
        self.items: Dict[str, Any] = {}
    
    async def pre_init(self, config_manager: ConfigManager) -> None:
        await super().pre_init(config_manager)

        self.config_manager = config_manager

        await self._register_config_items()
        await self._register_message_handlers()

        log.info(f"{self.prefix} Module Pre-initialized")
    
    async def init(self) -> None:
        await super().init()
        
        # Register initial routes during initialization
        await self._register_initial_routes()
        
    async def _register_config_items(self) -> None:
        if self.config_manager:
            self.config_manager.register(
                self.name,
                "api_prefix",
                "/api/example",
                self._on_api_prefix_change
            )
    
    async def _register_message_handlers(self) -> None:
        # Register message handlers for internal communication
        await self.subscribe("example_api.update", self._handle_example_update)
    
    async def _register_initial_routes(self) -> None:
        """Register initial API routes"""
        api_prefix = "/api/example"
        
        # Route 1: Get example data
        async def get_example(request_data: Dict[str, Any]) -> Dict[str, Any]:
            self.counter += 1
            return {
                "message": "Hello from Example API",
                "counter": self.counter,
                "request_info": request_data
            }
        
        # Route 2: Get items list
        async def get_items(request_data: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "items": self.items,
                "count": len(self.items)
            }
        
        # Route 3: Add item (POST)
        async def add_item(request_data: Dict[str, Any]) -> Dict[str, Any]:
            body = request_data.get("body", {})
            item_id = body.get("id")
            item_data = body.get("data")
            
            if not item_id or not item_data:
                return {"error": "Missing id or data"}
            
            self.items[item_id] = item_data
            return {
                "message": "Item added successfully",
                "item_id": item_id,
                "item": item_data
            }
        
        # Register the routes
        routes_to_register = [
            {
                "path": f"{api_prefix}",
                "endpoint": get_example,
                "methods": ["GET"],
                "description": "Example API endpoint"
            },
            {
                "path": f"{api_prefix}/items",
                "endpoint": get_items,
                "methods": ["GET"],
                "description": "Get all items"
            },
            {
                "path": f"{api_prefix}/items",
                "endpoint": add_item,
                "methods": ["POST"],
                "description": "Add a new item"
            }
        ]
        
        # Publish messages to register routes
        for route in routes_to_register:
            result = await self.publish("api.register_route", {
                "path": route["path"],
                "callback": route["endpoint"],
                "methods": route["methods"]
            })
            
            if result.get("status") == "success":
                self.registered_routes.append(route["path"])
                log.info(f"{self.prefix} Registered route: {route['path']} - {route['description']}")
            else:
                log.error(f"{self.prefix} Failed to register route: {route['path']} - {result.get('message')}")
    
    async def _handle_example_update(self, message: Any) -> None:
        """Handle example update messages"""
        log.info(f"{self.prefix} Received update: {message}")
        self.counter += 1
    
    async def _on_api_prefix_change(self, config_data: Any) -> None:
        """Handle API prefix configuration changes"""
        log.info(f"{self.prefix} API prefix changed to: {config_data}")
        
        # This would be a good place to re-register routes with the new prefix
        # For demonstration purposes, we'll just log the change
    
    async def run(self) -> None:
        """Main module loop"""
        log.info(f"{self.prefix} Example API module running")
        
        iteration = 0
        
        while self.is_running:
            iteration += 1
            
            # Every 10 iterations, demonstrate dynamic route registration
            if iteration % 10 == 0:
                await self._demonstrate_dynamic_routes()
            
            # Every 5 iterations, publish an update
            if iteration % 5 == 0:
                await self.publish("example_api.update", {
                    "iteration": iteration,
                    "message": "Periodic update from Example API"
                })
            
            completed = await self.sleep_or_stop(1)
            if not completed:
                log.info(f"{self.prefix} Stop requested, exiting run loop")
                break
    
    async def _demonstrate_dynamic_routes(self) -> None:
        """Demonstrate dynamic route registration and removal"""
        dynamic_path = "/api/example/dynamic"
        
        # Create a dynamic route endpoint
        async def dynamic_endpoint(request_data: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "message": "This is a dynamic route",
                "timestamp": request_data.get("query", {}).get("t", "unknown"),
                "route_info": "This route was dynamically registered"
            }
        
        # Check if the dynamic route already exists
        if dynamic_path not in self.registered_routes:
            # Register the dynamic route
            result = await self.publish("api.register_route", {
                "path": dynamic_path,
                "callback": dynamic_endpoint,
                "methods": ["GET", "POST"]
            })
            
            if result.get("status") == "success":
                self.registered_routes.append(dynamic_path)
                log.info(f"{self.prefix} Dynamically registered route: {dynamic_path}")
        else:
            # Remove the dynamic route
            result = await self.publish("api.remove_route", {
                "path": dynamic_path
            })
            
            if result.get("status") == "success":
                self.registered_routes.remove(dynamic_path)
                log.info(f"{self.prefix} Dynamically removed route: {dynamic_path}")
    
    async def pause(self) -> None:
        pass
    
    async def cleanup(self) -> None:
        """Clean up resources and remove all registered routes"""
        log.info(f"{self.prefix} Cleaning up resources")
        
        # Remove all registered routes
        for route_path in self.registered_routes:
            await self.publish("api.remove_route", {
                "path": route_path
            })
            log.info(f"{self.prefix} Removed route: {route_path}")
        
        self.registered_routes.clear()
        self.items.clear()
        
        await super().cleanup()