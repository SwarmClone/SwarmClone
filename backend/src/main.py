#!/usr/bin/env python3
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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio

from framework.controller import Controller
from framework.logger import *

__version__ = "0.4.0"

# def _add_system_endpoints(self, app: FastAPI) -> None:
#     """Add system-level endpoints"""

#     @app.get("/system/status")
#     async def system_status() -> Dict[str, Any]:
#         """Get system status"""
#         if not hasattr(app.state, 'controller') or not app.state.controller:
#             return {
#                 "status": "initializing",
#                 "version": __version__,
#                 "message": "System is starting up"
#             }

#         controller = app.state.controller
#         enabled_modules = [m for m in controller.modules.values() if m.enabled]
#         running_modules = [m for m in controller.modules.values() if m.is_running]

#         return {
#             "status": "running",
#             "version": __version__,
#             "modules": {
#                 "total": len(controller.modules),
#                 "enabled": len(enabled_modules),
#                 "running": len(running_modules)
#             },
#             "uptime": getattr(controller, 'uptime', 0)
#         }

#     @app.get("/system/modules")
#     async def list_modules() -> Dict[str, Any]:
#         """List all modules with their status"""
#         if not hasattr(app.state, 'controller') or not app.state.controller:
#             return {"modules": [], "message": "System is starting up"}

#         controller = app.state.controller
#         modules_info = []

#         for name, module in controller.modules.items():
#             category = getattr(module, 'category', 'modules')
#             api_path = f"/api/{category}/{name}"

#             modules_info.append({
#                 "name": name,
#                 "category": category,
#                 "enabled": module.enabled,
#                 "running": module.is_running,
#                 "api_path": api_path,
#                 "description": getattr(module, '__doc__', '')
#             })

#         return {
#             "modules": modules_info,
#             "total": len(modules_info)
#         }

#     @app.get("/system/health")
#     async def health_check() -> Dict[str, Any]:
#         """Health check endpoint"""
#         return {
#             "status": "healthy",
#             "version": __version__,
#             "timestamp": asyncio.get_event_loop().time()
#         }


async def run() -> None:
    controller = Controller()
    info(f"Starting SwarmClone Backend v{__version__}...")
    await controller.start()

def main():
    asyncio.run(run())

if __name__ == "__main__":
    main()