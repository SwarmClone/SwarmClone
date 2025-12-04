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

import json
from pathlib import Path
from typing import Any, Callable, Dict

from fastapi import APIRouter, HTTPException

from core.logger import log


class ConfigEventBus:
    # This is the event bus for processing configuration changes
    def __init__(self):

        # str: event_type, Dict[str, Callable]: module_name to callback
        self._subscribers: Dict[str, Dict[str, Callable]] = {} # type: ignore

    # Only the module subscribed to the same event_type can receive the specific config changes
    # This takes into account that one change in config may require 
    # more then one module to deal with it
    def subscribe(self, module_name: str, event_type: str, callback: Callable[[Any], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = {}
        self._subscribers[event_type][module_name] = callback
    
    def publish(self, event_type: str, config_data: Any) -> None:
        if event_type in self._subscribers:
            for module_name, callback in self._subscribers[event_type].items():
                try:
                    callback(config_data)
                except Exception as e:
                    log.error(f"Error notifying module {module_name} for event {event_type}: {e}")


class ConfigManager:
    # ConfigManager can load and save configuration data from/to a JSON file
    # It provides an event bus for modules to subscribe to configuration changes
    def __init__(self, config_file: Path = Path("config.json")):
        self.config_file = config_file
        self.config_data: Dict[str, Any] = {}
        self.event_bus = ConfigEventBus()
        self._load_config()

    def _load_config(self) -> None:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                log.info(f"Configuration loaded from {self.config_file}")
            except json.JSONDecodeError as e:
                log.error(f"Error loading configuration: {e}")
                self.config_data = {}
        else:
            self.config_data = {}
            self._save_config()
            log.info(f"Created new configuration file at {self.config_file}")

    def _save_config(self) -> None:
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)    # four space indentation
            log.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            log.error(f"Error saving configuration: {e}")
    
    def get(self, config_key: str, default: Any = None) -> Any:
        return self.config_data.get(config_key, default)
    
    def set(self, config_key: str, value: Any) -> None:
        self.config_data[config_key] = value
        self._save_config()
        self.event_bus.publish(config_key, value)

    def subscribe(self, module_name: str, event_type: str, callback: Callable[[Dict], None]) -> None:
        self.event_bus.subscribe(module_name, event_type, callback)
    
    def setup_fastapi_routes(self, app: Any) -> None:
        router = APIRouter(prefix="/config")

        @router.get("/")
        async def get_all_config():
            return self.config_data
        
        @router.get("/{config_key}")
        async def get_config(config_key: str):
            if config_key not in self.config_data:
                raise HTTPException(status_code=404, detail="Config key not found")
            return {config_key: self.config_data[config_key]}
        
        @router.post("/{config_key}")
        async def set_config(config_key: str, value: Any):
            self.set(config_key, value)
            return {"message": "Config updated successfully"}
        
        app.include_router(router)