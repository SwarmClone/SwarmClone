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

from typing import Any, Dict, List, Optional
from fastapi import FastAPI

from core import __version__
from core.logger import log
from core.routing import RouteRegistry, ModuleRouteBuilder, RouteInfo


class APIServer:
    """Simplified API server manager for modular route registration"""
    
    def __init__(self, app: Optional[FastAPI] = None):
        """
        Initialize the API server
        
        Args:
            app: FastAPI application instance. If None, creates a new one
        """
        if app is None:
            log.warning("No FastAPI instance provided to APIServer, creating a new one.")
            self._app = FastAPI()
        else:
            self._app = app
        
        self._registry = RouteRegistry()
        self._route_builders: Dict[str, ModuleRouteBuilder] = {}
        
        self._setup_base_routes()
        log.info("APIServer initialized")
    
    def _setup_base_routes(self):
        """Set up base routes for the API server"""
        
        @self._app.get("/")
        async def root():
            return {
                "message": "SwarmClone Backend API Server",
                "version": __version__,
                "status": "running",
                "module_count": len(self._route_builders)
            }
        
        @self._app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "version": __version__,
                "modules": list(self._route_builders.keys()),
                "total_routes": len(self.get_all_routes())
            }
        
        @self._app.get("/api/routes")
        async def list_all_routes():
            """List all registered API routes"""
            routes = []
            for module_name, _route_builder in self._route_builders.items():
                module_routes = self._registry.get_module_routes(module_name)
                for route in module_routes:
                    routes.append({
                        "module": module_name,
                        "path": f"/api/{module_name}{route.path}",
                        "methods": route.methods,
                        "name": route.name,
                        "description": route.description
                    })
            return {"routes": routes, "total": len(routes)}
    
    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application instance"""
        return self._app
    
    def register_module(self, module_name: str) -> ModuleRouteBuilder:
        """
        Register a module and get a route builder
        
        Args:
            module_name: Name of the module
            
        Returns:
            ModuleRouteBuilder instance for the registered module
            
        Raises:
            ValueError: If module_name is empty
        """
        if not module_name:
            raise ValueError("module_name cannot be empty")
        
        if module_name in self._route_builders:
            log.warning(f"Module '{module_name}' already registered, using existing route builder")
            return self._route_builders[module_name]
        
        # Get or create router for this module
        router = self._registry.get_or_create_router(module_name)
        
        # Create route builder
        route_builder = ModuleRouteBuilder(module_name, router, self._registry)
        self._route_builders[module_name] = route_builder
        
        # Include the router in the FastAPI app
        self._app.include_router(router)
        
        log.info(f"Registered module '{module_name}' with router prefix '/api/{module_name}'")
        return route_builder
    
    def get_route_builder(self, module_name: str) -> ModuleRouteBuilder:
        """
        Get the route builder for a specific module
        
        Args:
            module_name: Name of the module to get the route builder for
            
        Returns:
            ModuleRouteBuilder for the specified module
            
        Raises:
            KeyError: If module is not registered
        """
        if module_name not in self._route_builders:
            raise KeyError(f"Module '{module_name}' is not registered")
        return self._route_builders[module_name]
    
    def get_module_routes(self, module_name: str) -> List[RouteInfo]:
        """
        Get all routes registered for a module
        
        Args:
            module_name: Name of the module to get routes for
            
        Returns:
            List of RouteInfo objects
        """
        return self._registry.get_module_routes(module_name)
    
    def get_all_routes(self) -> List[RouteInfo]:
        """
        Get all registered routes
        
        Returns:
            List of RouteInfo objects
        """
        return self._registry.get_all_routes()
    
    def list_routes_debug(self) -> List[Dict[str, Any]]:
        """
        Debug method to list all registered FastAPI routes
        """
        routes_info = []
        
        for route in self._app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                routes_info.append({
                    "path": str(route.path), # type: ignore
                    "methods": list(route.methods), # type: ignore
                    "name": getattr(route, 'name', 'unknown'),
                    "endpoint": route.endpoint.__name__ if hasattr(route, 'endpoint') else 'unknown' # type: ignore
                })
            elif hasattr(route, 'path'):
                routes_info.append({
                    "path": str(route.path), # type: ignore
                    "methods": ["WEBSOCKET"],
                    "name": getattr(route, 'name', 'unknown'),
                    "endpoint": route.endpoint.__name__ if hasattr(route, 'endpoint') else 'unknown' # type: ignore
                })
        
        return routes_info