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
import signal

from logger import *
from module_manager import ModuleManager


class Controller:
    def __init__(self, config_file: str = "config.yml"):
        self.module_manager = ModuleManager(config_file)
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        self.uptime = 0
    
    def _setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown on all platforms.

        Handles:
        - SIGINT (Ctrl+C): Interrupt from keyboard
        - SIGTERM: Termination request

        Uses platform-appropriate methods:
        - Unix: asyncio.add_signal_handler() for thread safety
        - Windows: signal.signal() as fallback
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        signals_to_handle = []

        # SIGINT is available on all platforms
        if hasattr(signal, 'SIGINT'):
            signals_to_handle.append(signal.SIGINT)

        # SIGTERM is Unix-only, but we check for it
        if hasattr(signal, 'SIGTERM'):
            signals_to_handle.append(signal.SIGTERM)

        for sig in signals_to_handle:
            try:
                # Preferred method: thread-safe signal handler
                loop.add_signal_handler(sig, self._signal_handler)
                debug(f"Registered asyncio signal handler for {sig}")
            except (NotImplementedError, RuntimeError):
                # Fallback for Windows or if add_signal_handler fails
                # Use lambda to ignore signal number and frame
                signal.signal(sig, lambda s, f: self._signal_handler())
                debug(f"Registered fallback signal handler for {sig}")

    def _signal_handler(self) -> None:
        info("Shutdown signal received. Initiating graceful shutdown...")
        self._shutdown_event.set()

    async def run(self) -> None:
        self.is_running = True
        self._setup_signal_handlers()

        info("Controller starting...")

        try:
            self.module_manager.load_modules()
            await self.module_manager.initialize_modules()
            await self.module_manager.start_modules()

            enabled_count = len([m for m in self.module_manager.modules.values() if m.enabled])
            info(f"Controller running with {enabled_count} enabled modules")
            info("Press Ctrl+C to shutdown")

            await self._shutdown_event.wait()

            info("Shutdown initiated. Stopping modules...")

        except asyncio.CancelledError:
            info("Controller task was cancelled")
        except Exception as e:
            error(f"Controller encountered unexpected error: {e}", exc_info=True)
            await self.module_manager.stop_modules()
            raise
        finally:
            await self.module_manager.stop_modules()
            self.is_running = False
            info("Controller stopped")

    async def start(self) -> None:
        await self.run()
