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
from contextlib import asynccontextmanager
import signal
from typing import Dict, Any

from fastapi import FastAPI

from core.logger import log
from core.controller import Controller
from core.api_server import get_api_server
from core import __version__


class Application:
    """Main application class that manages the entire lifecycle"""
    
    def __init__(self):
        self.controller: Controller = None  # type: ignore
        self.api_server = get_api_server()
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self) -> None:
        """Initialize the application"""
        log.info(f"Initializing SwarmClone Backend v{__version__}...")
        
        # Create controller
        self.controller = Controller()
        
        # Load modules
        self.controller.load_modules()
        
        # Initialize modules (this will register API routes)
        await self.controller.initialize_modules()
        
        log.info("Application initialized")
        
    async def start(self) -> None:
        """Start the application"""
        log.info("Starting application...")
        
        # Start modules
        await self.controller.start_modules()
        
        log.info(f"SwarmClone Backend v{__version__} started successfully")
        
    async def stop(self) -> None:
        """Stop the application gracefully"""
        log.info("Stopping application...")
        
        if self.controller:
            await self.controller.stop_modules()
            
        log.info("Application stopped")
        
    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        loop = asyncio.get_event_loop()
        
        def signal_handler():
            log.info("Received shutdown signal")
            self._shutdown_event.set()
            
        try:
            loop.add_signal_handler(signal.SIGINT, signal_handler)
            if hasattr(signal, 'SIGTERM'):
                loop.add_signal_handler(signal.SIGTERM, signal_handler)
        except (NotImplementedError, RuntimeError):
            # Fallback for Windows
            signal.signal(signal.SIGINT, lambda s, f: signal_handler())
            if hasattr(signal, 'SIGTERM'):
                signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
                
    def create_fastapi_app(self) -> FastAPI:
        """Create and configure FastAPI application using the API server's app"""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Lifespan context manager for FastAPI"""
            # Inject controller into API server's app state
            self.api_server.app.state.controller = self.controller
            
            await self.initialize()
            self.api_server.print_all_routes()
            await self.start()
            
            yield
            
            await self.stop()
        
        app = self.api_server.app
        app.lifespan = lifespan
        
        self._add_system_endpoints(app)
        
        return app
        
    def _add_system_endpoints(self, app: FastAPI) -> None:
        """Add system-level endpoints to the FastAPI app"""
        
        @app.get("/system/status")
        async def system_status() -> Dict[str, Any]:
            """Get system status"""
            if not hasattr(app.state, 'controller') or not app.state.controller:
                return {
                    "status": "initializing",
                    "version": __version__,
                    "message": "System is starting up"
                }
                
            controller = app.state.controller
            enabled_modules = [m for m in controller.modules.values() if m.enabled]
            running_modules = [m for m in controller.modules.values() if m.is_running]
            
            return {
                "status": "running",
                "version": __version__,
                "modules": {
                    "total": len(controller.modules),
                    "enabled": len(enabled_modules),
                    "running": len(running_modules)
                },
                "uptime": getattr(controller, 'uptime', 0)
            }
            
        @app.get("/system/modules")
        async def list_modules() -> Dict[str, Any]:
            """List all modules with their status"""
            if not hasattr(app.state, 'controller') or not app.state.controller:
                return {"modules": [], "message": "System is starting up"}
                
            controller = app.state.controller
            modules_info = []
            
            for name, module in controller.modules.items():
                category = getattr(module, 'category', 'modules')
                api_path = f"/api/{category}/{name}"
                
                modules_info.append({
                    "name": name,
                    "category": category,
                    "enabled": module.enabled,
                    "running": module.is_running,
                    "api_path": api_path,
                    "description": getattr(module, '__doc__', '')
                })
                
            return {
                "modules": modules_info,
                "total": len(modules_info)
            }
            
        @app.get("/system/health")
        async def health_check() -> Dict[str, Any]:
            """Health check endpoint"""
            return {
                "status": "healthy",
                "version": __version__,
                "timestamp": asyncio.get_event_loop().time()
            }