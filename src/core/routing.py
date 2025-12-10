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

from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from core.logger import log


class RequestType(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    WEBSOCKET = "WEBSOCKET"


class RouteInfo(BaseModel):
    """Information about a registered route"""
    path: str
    endpoint: Callable
    methods: List[str]
    name: Optional[str] = None
    tags: List[str] = []
    description: Optional[str] = None
    response_model: Optional[Any] = None


class RouteRegistry:
    """Simple route registry for tracking registered routes"""
    
    def __init__(self):
        self.routes: Dict[str, List[RouteInfo]] = {}
        self._router_cache: Dict[str, APIRouter] = {}
    
    def register_route(self, module_name: str, route_info: RouteInfo):
        """Register a route for a module"""
        if module_name not in self.routes:
            self.routes[module_name] = []
        self.routes[module_name].append(route_info)
        log.debug(f"Registered route: {route_info.methods} /api/{module_name}{route_info.path}")
    
    def get_module_routes(self, module_name: str) -> List[RouteInfo]:
        """Get all routes for a module"""
        return self.routes.get(module_name, [])
    
    def get_all_routes(self) -> List[RouteInfo]:
        """Get all registered routes"""
        all_routes = []
        for routes in self.routes.values():
            all_routes.extend(routes)
        return all_routes
    
    def get_or_create_router(self, module_name: str, prefix: str = None) -> APIRouter: # type: ignore
        """Get or create an APIRouter for a module"""
        if module_name not in self._router_cache:
            router_prefix = prefix or f"/api/{module_name}"
            self._router_cache[module_name] = APIRouter(prefix=router_prefix, tags=[module_name])
        return self._router_cache[module_name]
    
    def include_routers(self, app: FastAPI):
        """Include all registered routers in the FastAPI app"""
        for router in self._router_cache.values():
            app.include_router(router)
        log.info(f"Included {len(self._router_cache)} routers in FastAPI app")


class ModuleRouteBuilder:
    """Builder for module-specific routes"""
    
    def __init__(self, module_name: str, router: APIRouter, registry: RouteRegistry):
        self.module_name = module_name
        self.router = router
        self.registry = registry
        
        # Create method decorators
        self.get = self._create_decorator(RequestType.GET)
        self.post = self._create_decorator(RequestType.POST)
        self.put = self._create_decorator(RequestType.PUT)
        self.delete = self._create_decorator(RequestType.DELETE)
        self.patch = self._create_decorator(RequestType.PATCH)
        self.head = self._create_decorator(RequestType.HEAD)
        self.options = self._create_decorator(RequestType.OPTIONS)
        self.websocket = self._create_decorator(RequestType.WEBSOCKET)
    
    def _create_decorator(self, request_type: RequestType):
        """Create a decorator for the specified HTTP method"""
        method_map = {
            RequestType.GET: self.router.get,
            RequestType.POST: self.router.post,
            RequestType.PUT: self.router.put,
            RequestType.DELETE: self.router.delete,
            RequestType.PATCH: self.router.patch,
            RequestType.HEAD: self.router.head,
            RequestType.OPTIONS: self.router.options,
            RequestType.WEBSOCKET: self.router.websocket,
        }
        
        method_func = method_map[request_type]
        
        def decorator(path: str, **kwargs):
            def wrapper(endpoint: Callable):
                # Register the route with FastAPI
                method_func(path, **kwargs)(endpoint)
                
                # Record route information
                route_info = RouteInfo(
                    path=path,
                    endpoint=endpoint,
                    methods=[request_type.value],
                    name=kwargs.get("name", endpoint.__name__),
                    description=kwargs.get("description", endpoint.__doc__ or ""),
                    tags=kwargs.get("tags", [self.module_name]),
                    response_model=kwargs.get("response_model")
                )
                self.registry.register_route(self.module_name, route_info)
                
                log.debug(f"Registered {request_type.value} route: {path} "
                         f"for module '{self.module_name}' (full path: /api/{self.module_name}{path})")
                return endpoint
            
            return wrapper
        
        return decorator
    
    def add_route(self, request_type: RequestType, path: str, endpoint: Callable, **kwargs):
        """Add a route to the module"""
        decorator = self._create_decorator(request_type)
        decorator(path, **kwargs)(endpoint)