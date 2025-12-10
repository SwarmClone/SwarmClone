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

from core.api_server import get_api_server
from core.logger import log
from core.config_manager import ConfigManager
from core.message import MessageBus
from core.base_module import BaseModule


class ModuleConfigError(Exception):
    """Exception raised when module configuration is invalid"""
    pass


class Controller:
    def __init__(self, config_file: str = "config.yml"):
        self.modules: Dict[str, BaseModule] = {}
        self.message_bus = MessageBus()
        self.config_manager = ConfigManager(Path(config_file))
        self.api_server = None

        self.is_running = False
        self._shutdown_event = asyncio.Event()
        self._module_tasks: List[asyncio.Task] = []
    
    def _parse_module_ini(self, module_dir: Path) -> dict:
        """
        Parse the module.ini file in a module directory.
        The module.ini file should have the following format:

        [module]
        class_name = "MyClassName"
        entry = "my_module.py"
        
        Both class_name and entry are required fields.

        NOTE: In packaged environment, the 'entry' file will auto set to .pyd file or .so file.
        """
        config_file = module_dir / "module.ini"
        
        if not config_file.exists():
            raise ModuleConfigError(f"module.ini not found in {module_dir}")
        
        config = ConfigParser()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config.read_file(f)
            
            if not config.has_section('module'):
                raise ModuleConfigError(f"Missing [module] section in {config_file}")
            
            class_name = config.get('module', 'class_name', fallback='').strip()
            entry_file = config.get('module', 'entry', fallback='').strip()
            
            if not class_name:
                raise ModuleConfigError(f"Missing 'class_name' in {config_file}")
            
            if not entry_file:
                raise ModuleConfigError(f"Missing 'entry' in {config_file}")
            
            # Remove quotes if present
            if class_name.startswith('"') and class_name.endswith('"'):
                class_name = class_name[1:-1]
            
            if entry_file.startswith('"') and entry_file.endswith('"'):
                entry_file = entry_file[1:-1]
            
            # Validate entry file exists
            entry_path = module_dir / entry_file
            if not entry_path.exists():
                raise ModuleConfigError(f"Entry file not found: {entry_path}")
            if not entry_file.endswith('.py') \
                        and not entry_file.endswith('.pyd'):   # In unpackaged environment
                log.warning(f"Entry file {entry_file} doesn't have .py extension")
            
            return {
                'class_name': class_name,
                'entry_file': entry_file,
                'entry_path': entry_path
            }
            
        except UnicodeDecodeError as e:
            raise ModuleConfigError(f"Invalid encoding in {config_file}: {e}")
        except Exception as e:
            # ConfigParser might raise various exceptions for malformed files
            raise ModuleConfigError(f"Error parsing {config_file}: {e}")
        
    def _load_single_module(self, module_dir: Path) -> Optional[BaseModule]:
        module_name = module_dir.name
        
        try:
            config = self._parse_module_ini(module_dir)
            class_name = config['class_name']
            entry_file = config['entry_file']
            
            log.info(f"Loading module '{module_name}': class={class_name}, entry={entry_file}")
            
            entry_path = config['entry_path']
            abs_entry_path = entry_path.resolve()
            
            # Create a unique module name to avoid conflicts
            module_full_name = f"modules.{module_name}.{entry_path.stem}"
            
            # Add the module directory to sys.path to handle relative imports
            module_dir_str = str(module_dir.resolve())
            if module_dir_str not in sys.path:
                sys.path.insert(0, module_dir_str)
            
            spec = spec_from_file_location(module_full_name, abs_entry_path)
            
            if spec is None:
                log.error(f"Could not create module spec for {abs_entry_path}")
                return None
            
            if spec.loader is None:
                log.error(f"Module loader is None for {abs_entry_path}")
                return None
            
            module = module_from_spec(spec)
            
            # Set the __package__ attribute to handle relative imports
            module.__package__ = f"modules.{module_name}"
            
            sys.modules[spec.name] = module
            
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                log.error(f"Error executing module {abs_entry_path}: {e}")
                sys.modules.pop(spec.name, None)
                return None
            
            if not hasattr(module, class_name):
                available_classes = [attr for attr in dir(module) 
                                   if attr[0].isupper() and not attr.startswith('_')]
                log.error(
                    f"Class '{class_name}' not found in {entry_file}. "
                    f"Available classes: {available_classes}"
                )
                return None
            
            module_class = getattr(module, class_name)
            
            if not issubclass(module_class, BaseModule):
                log.error(f"Class {class_name} is not a subclass of BaseModule")
                return None
            
            module_instance = module_class(module_name)
            module_instance.message_bus = self.message_bus
            
            log.info(f"Successfully loaded module: {module_name}")
            return module_instance
            
        except ModuleConfigError as e:
            log.warning(f"Skipping module {module_name}: {e}")
            return None
        except Exception as e:
            log.error(f"Unexpected error loading module {module_name}: {e}", exc_info=True)
            return None
        
    def load_modules(self) -> None:
        """
        Discover and load all modules from the modules directory.
        
        Each module directory must contain a module.ini file that specifies:
        - class_name: The name of the class to instantiate
        - entry: The Python file containing the class
        
        This allows module directories to have descriptive names (including
        prefixes/suffixes) while keeping class names clean and readable.
        
        Example directory structure:
        modules/
        ├── echo/
        │   ├── module.ini    # class_name="Echo", entry="echo.py"
        │   └── echo.py       # Contains class Echo(BaseModule)
        └── api-v1/
            ├── module.ini    # class_name="ApiV1", entry="api_v1.py"
            └── api_v1.py     # Contains class ApiV1(BaseModule)
        """
        modules_path = Path(__file__).resolve().parent.parent / 'modules'
        
        if not modules_path.exists():
            log.warning(f"Modules directory not found: {modules_path}")
            modules_path.mkdir(parents=True, exist_ok=True)
            log.info(f"Created modules directory: {modules_path}")
            return
        
        log.info(f"Scanning for modules in: {modules_path}")
        
        loaded_count = 0
        for module_dir in modules_path.iterdir():
            # Skip non-directories and special directories
            if not module_dir.is_dir():
                continue
            
            # Skip directories starting with __ (Python special) or . (hidden)
            dir_name = module_dir.name
            if dir_name.startswith('__') or dir_name.startswith('.'):
                continue
            
            # Try to load the module
            module_instance = self._load_single_module(module_dir)
            if module_instance is not None:
                self.modules[dir_name] = module_instance
                loaded_count += 1
        
        log.info(f"Loaded {loaded_count} out of {len(list(modules_path.iterdir()))} module directories")
    
    async def initialize_modules(self) -> None:

        log.info(f"Initializing {len(self.modules)} modules...")
        
        for module_name, module in self.modules.items():
            try:
                # Pre-initialize with config manager
                await module.pre_init(self.config_manager)

                module.message_bus = self.message_bus
                module.config_manager = self.config_manager
                if self.api_server:
                    module.api_server = self.api_server
                
                # Initialize module-specific resources
                await module.init()
                
                log.info(f"Initialized module: {module_name}")
            except Exception as e:
                log.error(
                    f"Failed to initialize module {module_name}: {e}\n"
                    f"Module will be disabled.",
                    exc_info=True
                )
                module.enabled = False

    async def start_modules(self) -> None:
        log.info(f"Starting enabled modules...")
        
        enabled_count = 0
        for module_name, module in self.modules.items():
            if module.enabled:
                try:
                    await module.start()
                    enabled_count += 1
                    log.info(f"Started module: {module_name}")
                except Exception as e:
                    log.error(f"Failed to start module {module_name}: {e}", exc_info=True)
            else:
                log.info(f"Module {module_name} is disabled, skipping")
        
        log.info(f"Started {enabled_count} modules")
    
    async def stop_modules(self) -> None:
        log.info("Stopping all modules...")
        
        for module_name, module in reversed(list(self.modules.items())):
            try:
                await module.stop()
                log.info(f"Stopped module: {module_name}")
            except Exception as e:
                log.error(f"Error stopping module {module_name}: {e}")
        
        await self.message_bus.cleanup()
    
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