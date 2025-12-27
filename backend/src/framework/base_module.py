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
from typing import Any, Callable, Dict, List

from config_manager import ConfigManager
from logger import *
from message import MessageBus


class BaseModule(ABC):
    """
    Base class for all modules using async/await pattern
    
    Each module runs in the same event loop but manages its own lifecycle
    """
    
    def __init__(self, module_name: str, category: str = 'modules'):
        self.name = module_name
        self.prefix = f"[{module_name.upper()}]"
        self.category = category
        self.enabled = True
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
        self.required_configs = []
        self.config: Dict[str, Any] = {}
        
        # Dependencies (injected by Controller)
        self.message_bus: Optional[MessageBus] = None
        self.config_manager: Optional[ConfigManager] = None

    @abstractmethod
    async def pre_init(self, config_manager: ConfigManager) -> None:
        """Called before module initialization for config setup"""
        pass
    
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
        info(f"{self.prefix} Module paused")

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
    
    async def start(self) -> None:
        """Start the module's main loop"""
        if not self.enabled:
            warning(f"{self.prefix} Module disabled, not starting")
            return
        
        self.is_running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_wrapper(), name=f"module_{self.name}")
        info(f"{self.prefix} Module started")
    
    async def _run_wrapper(self) -> None:
        """Wrapper around run() that handles cancellation and errors"""
        try:
            await self.run()
        except asyncio.CancelledError:
            info(f"{self.prefix} Module run task cancelled")
        except Exception as e:
            error(f"{self.prefix} Error in module run loop: {e}", exc_info=True)
        finally:
            self.is_running = False
            self._stop_event.set()
    
    async def stop(self) -> None:
        """Stop the module gracefully"""
        if not self.is_running:
            return
        
        info(f"{self.prefix} Stopping module...")
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
        info(f"{self.prefix} Module stopped")
    
    def _handle_config_change(self, config_data: Any) -> None:
        """Handle configuration changes - override in derived classes"""
        info(f"{self.prefix} Configuration changed: {config_data}")
    
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