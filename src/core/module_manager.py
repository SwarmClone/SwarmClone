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

import importlib
import asyncio
import threading
from pathlib import Path

from core.config_manager import ConfigManager
from core.logger import log

class Controller(object):
    def __init__(self):
        self.modules = {}
        self.config_manager = ConfigManager()
        self.module_threads = {}
        self.module_tasks = {}
        self.module_loops = {}

    def load_modules(self):
        # Locate the modules directory
        modules_path = Path(__file__).resolve().parent.parent / 'modules'

        # All modules should be in a directory with the same name as the module name
        # e.g. modules/echo/echo.py
        # folder that start with two underscores is ignored
        for module_dir in modules_path.iterdir():
            if module_dir.is_dir() and not module_dir.name.startswith('__'):
                module_name = module_dir.name
                log.info(f"Loading module {module_name} in {modules_path}")

                try:
                    module = importlib.import_module(f'modules.{module_name}.{module_name}')
                    module_class = getattr(module, module_name.capitalize())

                    instance = module_class(module_name)
                    
                    # Save the module instance
                    self.modules[module_name] = instance

                except Exception as e:
                    log.error(f"Failed to load module {module_name}: {e}")

    async def _async_prepare_and_run_module(self, module_name, module_instance):
        # initialize the module
        log.info(f"Preparing module {module_name}...")
        await module_instance.pre_init(self.config_manager)
        if module_instance.is_ready:
            try:
                await module_instance.run()
            except Exception as e:
                log.error(f"Error running module {module_name}: {e}")

    def _module_thread_func(self, module_name, module_instance):

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.module_loops[module_name] = loop
        
        task = loop.create_task(self._async_prepare_and_run_module(module_name, module_instance))
        self.module_tasks[module_name] = task
        
        try:
            loop.run_until_complete(task)
        except Exception as e:
            log.error(f"Module thread error for {module_name}: {e}")
        finally:
            loop.close()

    def run(self):
        self.load_modules()
        log.info("Modules loaded: %s", list(self.modules.keys()))
        
         # Create a new thread for each module
        for module_name, module_instance in self.modules.items():
            thread = threading.Thread(
                target=self._module_thread_func,
                args=(module_name, module_instance),
                name=f"Module-{module_name}"
            )
            self.module_threads[module_name] = thread
            thread.daemon = True  # Allow the thread to exit when the main program exits
            thread.start()
            log.info(f"Started module {module_name} in separate thread")
        
        # Keep the main thread alive
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Shutting down...")
            self._stop_all_modules()
            log.info("All modules stopped.")

    def _stop_all_modules(self):
        for module_name, module_instance in self.modules.items():
            try:
                if hasattr(module_instance, 'stop') and module_name in self.module_loops:
                    loop = self.module_loops[module_name]
                    if not loop.is_closed() and loop.is_running():
                        stop_future = asyncio.run_coroutine_threadsafe(module_instance.stop(), loop)
                        try:
                            stop_future.result(timeout=5.0)
                            log.info(f"Called stop method for module {module_name}")
                        except Exception as e:
                            log.error(f"Error calling stop method for {module_name}: {e}")
            except Exception as e:
                log.error(f"Error preparing to stop module {module_name}: {e}")
        
        for module_name, module_instance in self.modules.items():
            try:
                # Cancel the running task if it exists
                if module_name in self.module_tasks:
                    task = self.module_tasks[module_name]
                    task.cancel()
                    log.info(f"Cancelled task for module {module_name}")
            except Exception as e:
                log.error(f"Error cancelling task for module {module_name}: {e}")
        
        for module_name, thread in self.module_threads.items():
            if thread.is_alive():
                thread.join(timeout=5.0)
                log.info(f"Module {module_name} thread stopped")
        
        self.module_loops.clear()
        self.module_tasks.clear()
        self.module_threads.clear()
        log.info("All module threads stopped.")
