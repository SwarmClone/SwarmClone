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

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from core.api_server import APIServer
from core.routing import RequestType
from core.logger import log
from core.message import MessageBus
from core.config_manager import ConfigManager


class BaseModule(ABC):
    """
    Base class for all modules using async/await pattern
    
    Each module runs in the same event loop but manages its own lifecycle
    """
    
    def __init__(self, module_name: str):
        self.name = module_name
        self.prefix = f"[{module_name.upper()}]"
        self.enabled = True
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
        self.required_configs = []
        self.config: Dict[str, Any] = {}
        
        # Dependencies (injected by Controller)
        self.message_bus: Optional[MessageBus] = None
        self.config_manager: Optional[ConfigManager] = None
        self.api_server: Optional[APIServer] = None
        self._route_builder = None  # Will be set during initialization

    @abstractmethod
    async def init(self) -> None:
        """Initialize the module - override in derived classes"""
        pass
    
    @abstractmethod
    async def run(self) -> None:
        """
        Main module loop - implement in derived classes

        Should periodically check self.is_running or self._stop_event
        to allow graceful shutdown
        """
        pass

    @abstractmethod
    async def pause(self) -> None:
        """Pause module operations - override in derived classes"""
        log.info(f"{self.prefix} Module paused")

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up module resources - override in derived classes"""
        # Unsubscribe from message bus
        if self.message_bus:
            await self.message_bus.unsubscribe(self.name)
    
    @abstractmethod
    async def _register_message_handlers(self) -> None:
        """Register message handlers - override in derived classes"""
        pass
    
    def _get_route_builder(self):
        """Get the route builder for this module"""
        if self._route_builder is None and self.api_server:
            self._route_builder = self.api_server.register_module(self.name)
        return self._route_builder
    
    def register_config_api(self, config_key: str, default_value: Any, 
                           callback: Callable[[Any], None] = None, # type: ignore
                           private: bool = False) -> None:
        """
        Register a config item and optionally create API routes
        
        Args:
            config_key: The configuration key
            default_value: Default value for the config
            callback: Callback function when config changes (optional)
            private: If True, no API routes will be created
        """
        if not self.config_manager:
            log.error(f"{self.prefix} Config manager not available")
            return
        
        # Create callback if not provided
        if callback is None:
            def default_callback(value):
                log.info(f"{self.prefix} Config '{config_key}' changed to: {value}")
            callback = default_callback
        
        # Register with config manager
        self.config_manager.register(self.name, config_key, default_value, callback)
        
        # Create API routes if not private
        if not private:
            route_builder = self._get_route_builder()
            if route_builder:
                try:
                    # GET route to retrieve config value
                    @route_builder.get(f"/config/{config_key}", name=f"get_{config_key}")
                    async def get_config():
                        """Get configuration value"""
                        value = self.config_manager.get(self.name, config_key, default_value) # type: ignore
                        return {
                            "module": self.name, 
                            "key": config_key, 
                            "value": value,
                            "success": True
                        }
                    
                    # POST route to update config value
                    @route_builder.post(f"/config/{config_key}", name=f"set_{config_key}")
                    async def set_config(value: Any):
                        """Update configuration value"""
                        self.config_manager.set(self.name, config_key, value) # type: ignore
                        return {
                            "module": self.name, 
                            "key": config_key, 
                            "value": value, 
                            "status": "updated",
                            "success": True
                        }
                    
                    log.info(f"{self.prefix} Created API routes for config: {config_key}")
                    
                except Exception as e:
                    log.error(f"{self.prefix} Failed to create API routes for config {config_key}: {e}")
            else:
                log.warning(f"{self.prefix} No route builder available, skipping API route creation for {config_key}")
    
    def register_api_endpoint(self, request_type: RequestType, path: str, 
                            endpoint: Callable, **kwargs) -> None:
        """
        Register an API endpoint for this module
        
        Args:
            request_type: HTTP method type
            path: API path (relative to module's base path)
            endpoint: Endpoint function
            **kwargs: Additional FastAPI route parameters
        """
        route_builder = self._get_route_builder()
        if not route_builder:
            log.error(f"{self.prefix} Route builder not available for registering API")
            return
        
        try:
            route_builder.add_route(request_type, path, endpoint, **kwargs)
            log.info(f"{self.prefix} Registered API endpoint: {request_type.value} {path}")
        except Exception as e:
            log.error(f"{self.prefix} Failed to register API endpoint {path}: {e}")
    
    async def start(self) -> None:
        """Start the module's main loop"""
        if not self.enabled:
            log.warning(f"{self.prefix} Module disabled, not starting")
            return
        
        self.is_running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_wrapper(), name=f"module_{self.name}")
        log.info(f"{self.prefix} Module started")
    
    async def _run_wrapper(self) -> None:
        """Wrapper around run() that handles cancellation and errors"""
        try:
            await self.run()
        except asyncio.CancelledError:
            log.info(f"{self.prefix} Module run task cancelled")
        except Exception as e:
            log.error(f"{self.prefix} Error in module run loop: {e}", exc_info=True)
        finally:
            self.is_running = False
            self._stop_event.set()
    
    async def stop(self) -> None:
        """Stop the module gracefully"""
        if not self.is_running:
            return
        
        log.info(f"{self.prefix} Stopping module...")
        self.is_running = False
        
        self._stop_event.set()
        
        # Cancel the task if it's running
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        await self.cleanup()
        log.info(f"{self.prefix} Module stopped")
    
    async def wait_for_stop(self) -> None:
        """Wait until stop is requested"""
        await self._stop_event.wait()
    
    async def sleep_or_stop(self, seconds: float) -> bool:
        """
        Sleep for specified seconds or until stop is requested
        
        Returns:
            True if sleep completed, False if stopped early
        """
        try:
            await asyncio.wait_for(
                self._stop_event.wait(),
                timeout=seconds
            )
            return False  # Stop was requested
        except asyncio.TimeoutError:
            return True  # Sleep completed
    
    async def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a message bus topic"""
        if self.message_bus:
            await self.message_bus.subscribe(self.name, topic, callback)
    
    async def publish(self, topic: str, message: Any) -> List[Any]:
        """Publish a message to the message bus"""
        if self.message_bus:
            return await self.message_bus.publish(topic, message)
        return []