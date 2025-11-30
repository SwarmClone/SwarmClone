import importlib
from pathlib import Path

class Controller(object):
    def __init__(self):
        self.modules = {}
        self.api_server = None

    def load_modules(self, config_manager, file_manager, message_bus, event_bus):
        # Locate the modules directory
        modules_path = Path(__file__).resolve().parent.parent / 'modules'

        # All modules should be in a directory with the same name as the module name
        # e.g. modules/echo/echo.py
        # folder that start with two underscores is ignored
        for module_dir in modules_path.iterdir():
            if module_dir.is_dir() and not module_dir.name.startswith('__'):
                module_name = module_dir.name
                print(f"Loading module {module_name} in {modules_path}")

                try:
                    module = importlib.import_module(f'modules.{module_name}.{module_name}')
                    module_class = getattr(module, module_name.capitalize())

                    instance = module_class(config_manager, file_manager, message_bus, event_bus)
                    instance.initialize()
                    
                    # Save the module instance
                    # TODO: make it useful :(
                    self.modules[module_name] = instance

                except Exception as e:
                    print(f"Failed to load module {module_name}: {e}")

    def run(self):
        pass