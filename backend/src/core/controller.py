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

import sys
import signal
import asyncio
from importlib.util import spec_from_file_location, module_from_spec
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, List, Optional

from core.logger import log
from core.config_manager import ConfigManager
from core.message import MessageBus
from core.base_module import BaseModule


class ModuleConfigError(Exception):
    """Exception raised when module configuration is invalid"""
    pass


class Controller:
    def __init__(self, config_file: str = "config.yml"):
        pass
    
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
                log.debug(f"Registered asyncio signal handler for {sig}")
            except (NotImplementedError, RuntimeError):
                # Fallback for Windows or if add_signal_handler fails
                # Use lambda to ignore signal number and frame
                signal.signal(sig, lambda s, f: self._signal_handler())
                log.debug(f"Registered fallback signal handler for {sig}")

    def _signal_handler(self) -> None:
        log.info("Shutdown signal received. Initiating graceful shutdown...")
        self._shutdown_event.set()

    async def run(self) -> None:
        self.is_running = True
        self._setup_signal_handlers()

        log.info("Controller starting...")

        try:
            self.load_modules()
            await self.initialize_modules()
            await self.start_modules()

            enabled_count = len([m for m in self.modules.values() if m.enabled])
            log.info(f"Controller running with {enabled_count} enabled modules")
            log.info("Press Ctrl+C to shutdown")

            await self._shutdown_event.wait()

            log.info("Shutdown initiated. Stopping modules...")

        except asyncio.CancelledError:
            log.info("Controller task was cancelled")
        except Exception as e:
            log.error(f"Controller encountered unexpected error: {e}", exc_info=True)
            await self.stop_modules()
            raise
        finally:
            await self.stop_modules()
            self.is_running = False
            log.info("Controller stopped")

    async def start(self) -> None:
        await self.run()