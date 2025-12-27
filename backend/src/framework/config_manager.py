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
from pathlib import Path
from typing import Any, Callable, Dict

from fastapi import APIRouter, HTTPException
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from logger import log


class ConfigEventBus:
    # This is the event bus for processing configuration changes
    def __init__(self):
        # str: event_type, Dict[str, Callable]: module_name to callback
        self._subscribers: Dict[str, Dict[str, Callable]] = {}  # type: ignore

    # Only the module subscribed to the same event_type can receive the specific config changes
    # This takes into account that one change in config may require 
    # more than one module to deal with it
    def subscribe(self, module_name: str, event_type: str, callback: Callable[[Any], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = {}
        self._subscribers[event_type][module_name] = callback
        log.debug(f"Module {module_name} subscribed to event {event_type}")

    def publish(self, event_type: str, config_data: Any) -> None:
        if event_type in self._subscribers:
            log.debug(f"Publishing event {event_type} to {len(self._subscribers[event_type])} modules")
            for module_name, callback in self._subscribers[event_type].items():
                try:
                    callback(config_data)
                except Exception as e:
                    log.error(f"Error notifying module {module_name} for event {event_type}: {e}")


class ConfigManager:
    # ConfigManager can load and save configuration data from/to a YAML file
    # It provides an event bus for modules to subscribe to configuration changes
    def __init__(self, config_file: Path = Path("config.yml")):
        self.config_file = config_file
        self.yaml = YAML()
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.yaml.preserve_quotes = True
        self.config_data: CommentedMap = CommentedMap()  # Keep comments in config file
        self.event_bus = ConfigEventBus()
        self._load_config()

    def _load_config(self) -> None:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_data = self.yaml.load(f)
                    if isinstance(loaded_data, CommentedMap):
                        self.config_data = loaded_data
                    elif loaded_data is None:
                        self.config_data = CommentedMap()
                        log.warning(f"Empty YAML file {self.config_file}, using empty config")
                    else:
                        # 如果不是CommentedMap，转换一下
                        self.config_data = CommentedMap(loaded_data)
                        log.info(f"Configuration loaded from {self.config_file}")
            except Exception as e:
                log.error(f"Error loading configuration: {e}")
                self.config_data = CommentedMap()
        else:
            self.config_data = CommentedMap()
            self._save_config()
            log.info(f"Created new configuration file at {self.config_file}")

    def _save_config(self) -> None:
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.yaml.dump(self.config_data, f)
            log.debug(f"Configuration saved to {self.config_file}")
        except Exception as e:
            log.error(f"Error saving configuration: {e}")

    def _ensure_module_exists(self, module_name: str) -> None:
        if module_name not in self.config_data:
            self.config_data[module_name] = CommentedMap()
            self._save_config()

    def get(self, module_name: str, config_key: str, default: Any = None) -> Any:
        if module_name in self.config_data and config_key in self.config_data[module_name]:
            return self.config_data[module_name][config_key]
        return default

    def set(self, module_name: str, config_key: str, value: Any) -> None:
        self._ensure_module_exists(module_name)
        
        old_value = None
        if config_key in self.config_data[module_name]:
            old_value = self.config_data[module_name][config_key]
        
        self.config_data[module_name][config_key] = value
        self._save_config()

        # Only publish update event if value actually changed
        if old_value != value:
            event_type = f"{module_name}.{config_key}"
            self.event_bus.publish(event_type, value)
            log.debug(f"Config changed: {event_type} = {value}")

    def register(self, module_name: str, config_key: str,
                 default_value: Any, callback: Callable[[Any], None]) -> Any:
        event_type = f"{module_name}.{config_key}"
        self.event_bus.subscribe(module_name, event_type, callback)

        if not self.has_config(module_name, config_key):
            self.set(module_name, config_key, default_value)

        return default_value

    def has_config(self, module_name: str, config_key: str) -> bool:
        # Check if the module has the config key
        return (
            module_name in self.config_data and
            config_key in self.config_data[module_name]
        )

    def get_module_configs(self, module_name: str) -> CommentedMap:
        # Get all configs for a specific module
        self._ensure_module_exists(module_name)
        return self.config_data[module_name]

    def setup_fastapi_routes(self, app: Any) -> None:
        router = APIRouter(prefix="/config", tags=["config"])

        @router.get("/")
        async def get_all_config():
            return dict(self.config_data)

        @router.get("/modules/{module_name}")
        async def get_module_config(module_name: str):
            module_config = self.get_module_configs(module_name)
            return {module_name: dict(module_config)}

        @router.get("/modules/{module_name}/{config_key}")
        async def get_config(module_name: str, config_key: str):
            if not self.has_config(module_name, config_key):
                raise HTTPException(
                    status_code=404,
                    detail=f"Config '{config_key}' not found in module '{module_name}'"
                )
            return {config_key: self.get(module_name, config_key)}

        @router.post("/modules/{module_name}/{config_key}")
        async def set_config(module_name: str, config_key: str, value: Any):
            self.set(module_name, config_key, value)
            return {
                "message": f"Config '{config_key}' updated successfully",
                "module": module_name,
                "config_key": config_key,
                "value": value
            }

        app.include_router(router)