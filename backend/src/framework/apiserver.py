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

import asyncio
import threading
from typing import Any, Callable, Dict, List, Optional

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import BaseRoute
from starlette.routing import Route

from base_module import BaseModule
from config_manager import ConfigManager
from logger import log


class APIServerModule(BaseModule):
    """API Server module that provides dynamic routing capabilities using Starlette"""
    
    def __init__(self, module_name: str):
        super().__init__(module_name)
        self.config_manager: Optional[ConfigManager] = None
        self.app: Optional[Starlette] = None
        self.server_thread: Optional[threading.Thread] = None
        self.server_running: bool = False
        self.server_loop: Optional[asyncio.AbstractEventLoop] = None
        self.routes_lock: threading.Lock = threading.Lock()
        self.routes: List[BaseRoute] = []
        self.port: int = 8000
        self.host: str = "0.0.0.0"
    
    async def pre_init(self, config_manager: ConfigManager) -> None:
        await super().pre_init(config_manager)

        self.config_manager = config_manager

        await self._register_config_items()
        await self._register_message_handlers()

        # Initialize Starlette app
        self._init_app()

        log.info(f"{self.prefix} Module Pre-initialized")
    
    async def init(self) -> None:
        await super().init()
        
    async def _register_config_items(self) -> None:
        if self.config_manager:
            self.port = self.config_manager.register(
                self.name,
                "port",
                8000,
                self._on_port_change
            )
            self.host = self.config_manager.register(
                self.name,
                "host",
                "0.0.0.0",
                self._on_host_change
            )
    
    async def _register_message_handlers(self) -> None:
        # Register message handlers for dynamic routing
        await self.subscribe("api.register_route", self._handle_register_route)
        await self.subscribe("api.remove_route", self._handle_remove_route)
        await self.subscribe("api.list_routes", self._handle_list_routes)
    
    def _init_app(self) -> None:
        """Initialize the Starlette application"""
        self.app = Starlette(
            routes=self.routes,
            lifespan=self._lifespan
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add default routes
        self._add_default_routes()
    
    def _add_default_routes(self) -> None:
        """Add default API routes"""
        # Root route
        async def root(request: Request) -> Response:
            return JSONResponse({
                "message": "SwarmClone API Server",
                "version": "0.1.0",
                "status": "running"
            })
        
        # Health check route
        async def health(request: Request) -> Response:
            return JSONResponse({"status": "healthy"})
        
        # Routes information
        async def list_routes(request: Request) -> Response:
            route_info = []
            with self.routes_lock:
                for route in self.routes:
                    route_info.append({
                        "path": getattr(route, "path", "unknown"),
                        "methods": getattr(route, "methods", [])
                    })
            return JSONResponse(route_info)
        
        # Add default routes
        self.add_route("/", root, methods=["GET"])
        self.add_route("/health", health, methods=["GET"])
        self.add_route("/api/routes", list_routes, methods=["GET"])
    
    async def _lifespan(self, app: Starlette) -> Any:
        """Starlette lifespan events"""
        log.info(f"{self.prefix} API Server lifespan starting")
        yield
        log.info(f"{self.prefix} API Server lifespan ending")
    
    def add_route(self, path: str, endpoint: Callable, methods: List[str] = ["GET"]) -> None:
        """Add a new route to the API server"""
        with self.routes_lock:
            # Check if route already exists
            for route in self.routes:
                if hasattr(route, "path") and route.path == path:
                    log.warning(f"{self.prefix} Route {path} already exists")
                    return
            
            # Create new route
            new_route = Route(path, endpoint=endpoint, methods=methods)
            self.routes.append(new_route)
            
            # Update app routes
            if self.app:
                self.app.routes = self.routes
            
            log.info(f"{self.prefix} Added route: {path} {methods}")
    
    def remove_route(self, path: str) -> bool:
        """Remove a route from the API server"""
        with self.routes_lock:
            for i, route in enumerate(self.routes):
                if hasattr(route, "path") and route.path == path:
                    del self.routes[i]
                    
                    # Update app routes
                    if self.app:
                        self.app.routes = self.routes
                    
                    log.info(f"{self.prefix} Removed route: {path}")
                    return True
            
            log.warning(f"{self.prefix} Route {path} not found")
            return False
    
    def list_routes(self) -> List[Dict[str, Any]]:
        """List all registered routes"""
        route_info = []
        with self.routes_lock:
            for route in self.routes:
                route_info.append({
                    "path": getattr(route, "path", "unknown"),
                    "methods": getattr(route, "methods", []),
                    "endpoint": str(getattr(route, "endpoint", "unknown"))
                })
        return route_info
    
    async def _handle_register_route(self, message: Dict[str, Any]) -> Dict[str, str]:
        """Handle message to register a new route"""
        try:
            path = message.get("path")
            methods = message.get("methods", ["GET"])
            callback = message.get("callback")
            
            if not path or not callback:
                return {"status": "error", "message": "Missing path or callback"}
            
            # Create a wrapper for the callback
            async def endpoint_wrapper(request: Request) -> Response:
                # Extract request data
                request_data = {}
                
                # Get query parameters
                request_data["query"] = dict(request.query_params)
                
                # Get path parameters
                request_data["path_params"] = request.path_params
                
                # Get headers
                request_data["headers"] = dict(request.headers)
                
                # Get body if available
                if request.method in ["POST", "PUT", "PATCH"]:
                    try:
                        request_data["body"] = await request.json()
                    except Exception:
                        request_data["body"] = {}
                
                # Call the callback
                try:
                    result = await callback(request_data)
                    if isinstance(result, dict):
                        return JSONResponse(result)
                    elif isinstance(result, str):
                        return PlainTextResponse(result)
                    else:
                        return JSONResponse({"result": result})
                except Exception as e:
                    log.error(f"{self.prefix} Error in route callback: {e}")
                    return JSONResponse({"error": str(e)}, status_code=500)
            
            # Add the route
            self.add_route(path, endpoint_wrapper, methods)
            return {"status": "success", "message": f"Route {path} registered"}
            
        except Exception as e:
            log.error(f"{self.prefix} Error registering route: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_remove_route(self, message: Dict[str, Any]) -> Dict[str, str]:
        """Handle message to remove a route"""
        try:
            path = message.get("path")
            if not path:
                return {"status": "error", "message": "Missing path"}
            
            removed = self.remove_route(path)
            if removed:
                return {"status": "success", "message": f"Route {path} removed"}
            else:
                return {"status": "error", "message": f"Route {path} not found"}
                
        except Exception as e:
            log.error(f"{self.prefix} Error removing route: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_list_routes(self, message: Any) -> List[Dict[str, Any]]:
        """Handle message to list all routes"""
        return self.list_routes()
    
    def _on_port_change(self, config_data: Any) -> None:
        """Handle port configuration changes"""
        log.info(f"{self.prefix} Port changed to: {config_data}")
        self.port = config_data
        # Restart server if running
        if self.server_running:
            self.stop_server()
            self.start_server()
    
    def _on_host_change(self, config_data: Any) -> None:
        """Handle host configuration changes"""
        log.info(f"{self.prefix} Host changed to: {config_data}")
        self.host = config_data
        # Restart server if running
        if self.server_running:
            self.stop_server()
            self.start_server()
    
    def start_server(self) -> None:
        """Start the HTTP server in a separate thread"""
        if self.server_running:
            log.warning(f"{self.prefix} Server already running")
            return
        
        if not self.app:
            log.error(f"{self.prefix} App not initialized")
            return
        
        def server_runner() -> None:
            """Server runner function"""
            try:
                self.server_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.server_loop)
                
                log.info(f"{self.prefix} Starting API server on {self.host}:{self.port}")
                
                # Run server with uvicorn
                uvicorn.run(
                    self.app,
                    host=self.host,
                    port=self.port,
                    loop="asyncio",
                    log_level="error"  # Disable uvicorn logs
                )
            except Exception as e:
                log.error(f"{self.prefix} Server error: {e}")
            finally:
                self.server_running = False
                log.info(f"{self.prefix} Server stopped")
        
        # Start server in a new thread
        self.server_thread = threading.Thread(target=server_runner, daemon=True)
        self.server_thread.start()
        self.server_running = True
        log.info(f"{self.prefix} API server started on {self.host}:{self.port}")
    
    def stop_server(self) -> None:
        """Stop the HTTP server"""
        if not self.server_running:
            log.warning(f"{self.prefix} Server not running")
            return
        
        self.server_running = False
        
        # Stop the server loop
        if self.server_loop:
            self.server_loop.call_soon_threadsafe(self.server_loop.stop)
        
        # Wait for thread to finish
        if self.server_thread:
            self.server_thread.join(timeout=5)
        
        log.info(f"{self.prefix} API server stopped")
    
    async def run(self) -> None:
        """Main module loop"""
        log.info(f"{self.prefix} API Server running")
        
        # Start the HTTP server
        self.start_server()
        
        while self.is_running:
            # Check server status
            if not self.server_running:
                log.warning(f"{self.prefix} Server unexpectedly stopped, restarting...")
                self.start_server()
            
            await self.sleep_or_stop(1)

    async def cleanup(self) -> None:
        """Clean up API server resources"""
        log.info(f"{self.prefix} Cleaning up API server")
        
        # Stop the server
        self.stop_server()
        
        await super().cleanup()