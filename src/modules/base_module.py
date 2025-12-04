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

from abc import ABC, abstractmethod
from typing import List

from core.logger import log


class BaseModule(ABC):
    # This is the base class for all modules
    # If you want to create a new module, inherit from this class
    def __init__(self, module_name:str):
        self.module_name = module_name
        self.is_init = False
        self.is_ready = False
        # The list of required config keys for this module
        # Just key names, e.g. ["api_key", "model_name"]
        self.required_configs: List[str] = []

    # TODO； finish file_manager and message_bus
    async def pre_init(self, config_manager, file_manager = None, message_bus = None):
        self.config_manager = config_manager
        self.file_manager = file_manager
        self.message_bus = message_bus

        await self._register_config_callbacks()
        await self._check_and_init()

    async def _check_and_init(self):
        try:
            missing_configs = []
            for config in self.required_configs:
                if self.config_manager.get(config) is None:
                    missing_configs.append(config)
            
            if missing_configs:
                log.warning(f"Module {self.module_name} is missing required configs: {missing_configs}")
                self.is_ready = False
            else:
                self.is_ready = True
                await self.init()
                self.is_init = True
                log.info(f"Module {self.module_name} initialized and ready.")
        except Exception as e:
            log.error(f"Error during initialization of module {self.module_name}: {e}")
            self.is_ready = False

    async def _register_config_callbacks(self):
        # It's null by default, override in your module class if needed
        pass

    @abstractmethod
    async def init(self):
        # Initialize the module, it must override in your module class
        # After executing this function, it means that your module 
        # is ready to run at any time.
        # For example, the LLM module has connected to the LLM service successfully.
        pass

    @abstractmethod
    async def run(self):
        # This is the enrty point of your module logic
        pass

    @abstractmethod
    async def pause(self):
        # Pause the module, it must override in your module class
        # For example, the LLM module send a pause request to the LLM service (interrupt)
        pass
        
    @abstractmethod
    async def stop(self):
        # You must put your module cleanup code here
        pass