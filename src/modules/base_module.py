from abc import ABC, abstractmethod
from typing import List


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

    async def pre_init(self, config_manager, file_manager, message_bus, event_bus):
        self.config_manager = config_manager
        self.file_manager = file_manager
        self.message_bus = message_bus
        self.event_bus = event_bus

        await self._register_config_callbacks()
        await self._check_and_init()

    async def _check_and_init(self):
        try:
            missing_configs = []
            for config in self.required_configs:
                if self.config_manager.get(config) is None:
                    missing_configs.append(config)
            
            if missing_configs:
                print(f"Module {self.module_name} is missing required configs: {missing_configs}")
                self.is_ready = False
            else:
                self.is_ready = True
                await self.init()
                self.is_init = True
                print(f"Module {self.module_name} initialized and ready.")
        except Exception as e:
            print(f"Error during initialization of module {self.module_name}: {e}")
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
    async def stop(self):
        # You must put your module cleanup code here
        pass