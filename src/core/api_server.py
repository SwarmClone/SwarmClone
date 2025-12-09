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

from core import __version__
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


class APIServer:
    """Singleton API server manager for modular route registration"""
    
    _instance = None
    DEFAULT_API_PREFIX = "/api/{category}/{module_name}"
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, app: Optional[FastAPI] = None, api_prefix_format: Optional[str] = None, lifespan: Optional[Callable] = None):
        """
        Initialize the API server
        
        Args:
            app: FastAPI application instance. If None, creates a new one
            api_prefix_format: Format string for API paths. Defaults to "/api/{category}/{module_name}"
            lifespan: Optional lifespan function for FastAPI application
        """
        if hasattr(self, '_initialized'):
            if app is not None and app is not self._app:
                log.warning("APIServer already initialized. Provided app will be ignored.")
            return
        
        if app is None:
            self._app = FastAPI(lifespan=lifespan)
        else:
            self._app = app

        self._routers: Dict[str, APIRouter] = {}
        self._routes_registry: Dict[str, List[RouteInfo]] = {}
        self._api_prefix_format = api_prefix_format or self.DEFAULT_API_PREFIX
        self._initialized = True
        
        self._setup_base_routes()
        log.info(f"APIServer initialized with prefix format: {self._api_prefix_format}")
    
    def _setup_base_routes(self):
        """Set up base routes for the API server"""
        
        @self._app.get("/")
        async def root():
            return {
                "message": "SwarmClone Backend API Server",
                "version": __version__,
                "status": "running"
            }
        
        @self._app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "modules": list(self._routers.keys())
            }
    
    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application instance"""
        return self._app
    
    def register(self, category: str, module_name: str, prefix: str = None) -> "ModuleRouter": # type: ignore
        """
        Register a module router with the API server
        
        Args:
            category: Category of the module, e.g., "core", "gaming", "tools"
            module_name: Name of the module
            prefix: URL prefix for the module routes. 
                   If None, uses the configured API prefix format
                   
        Returns:
            ModuleRouter instance for the registered module
            
        Raises:
            ValueError: If module_name is empty
        """
        if not module_name:
            raise ValueError("module_name cannot be empty")
        
        if module_name in self._routers:
            log.warning(f"Module '{module_name}' already registered, using existing router")
            return ModuleRouter(category, module_name, self._routers[module_name], self)
        
        if prefix is None:
            prefix = self._api_prefix_format.format(category=category, module_name=module_name)
        
        router = APIRouter(prefix=prefix, tags=[f"{category}-{module_name}"])
        self._routers[module_name] = router
        self._routes_registry[module_name] = []
        
        self._app.include_router(router)
        
        log.info(f"Registered router for module '{module_name}' with prefix '{prefix}'")
        return ModuleRouter(category, module_name, router, self)
    
    def add_route(self, module_name: str, route_info: RouteInfo):
        """
        Add a route to the registry for a specific module
        
        Args:
            module_name: Name of the module to add the route to
            route_info: Information about the route to add
        """
        if module_name not in self._routes_registry:
            self._routes_registry[module_name] = []
        self._routes_registry[module_name].append(route_info)
    
    def get_routes(self, module_name: Optional[str] = None) -> List[RouteInfo]:
        """
        Get all routes registered for a module or all modules
        
        Args:
            module_name: Name of the module to get routes for. 
                        If None, returns all routes for all modules
                        
        Returns:
            List of RouteInfo objects
        """
        if module_name:
            return self._routes_registry.get(module_name, [])
        
        all_routes = []
        for routes in self._routes_registry.values():
            all_routes.extend(routes)
        return all_routes
    
    def get_router_handler(self, module_name: str) -> APIRouter:
        """
        Get the APIRouter handler for a specific module
        
        Args:
            module_name: Name of the module to get the router handler for
            
        Returns:
            APIRouter handler for the specified module
            
        Raises:
            KeyError: If module is not registered
        """
        if module_name not in self._routers:
            raise KeyError(f"Module '{module_name}' is not registered")
        return self._routers[module_name]


class ModuleRouter:
    """Wrapper for module-specific route registration"""
    
    def __init__(self, category: str, module_name: str, router: APIRouter, api_server: APIServer):
        self.category = category
        self.module_name = module_name
        self.router = router
        self.api_server = api_server
        
        # Create HTTP method decorators
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
                    name=endpoint.__name__,
                    description=endpoint.__doc__ or kwargs.get("description", ""),
                    tags=[self.module_name] + kwargs.get("tags", []),
                    response_model=kwargs.get("response_model")
                )
                self.api_server.add_route(self.module_name, route_info)
                
                log.debug(f"Registered {request_type.value} {path} for module '{self.module_name}'")
                return endpoint
            
            return wrapper
        
        return decorator
    
    def add(self, request_type: RequestType, path: str, endpoint: Callable, **kwargs):
        """
        Add a route to the module router
        
        Args:
            request_type: HTTP method or WebSocket
            path: URL path for the route
            endpoint: Function to handle the request
            **kwargs: Additional arguments for the route decorator
        """
        decorator = self._create_decorator(request_type)
        decorator(path, **kwargs)(endpoint)
    
    def list_routes(self) -> List[RouteInfo]:
        """List all routes registered in current module"""
        return self.api_server.get_routes(self.module_name)


# Global API server instance
api_server = APIServer()


def get_api_server() -> APIServer:
    """Get the global APIServer instance"""
    return api_server


def register_module(category: str, module_name: str, prefix: str = None) -> "ModuleRouter": # type: ignore
    """
    Register a module router with the APIServer
    
    Args:
        category: Category of the module, e.g. "core", "gaming", "tools"
        module_name: Name of the module, e.g. "llm", "tts"
        prefix: URL prefix for the module routes. 
               Defaults to configured API prefix format
               
    Returns:
        ModuleRouter instance for the registered module
    """
    return api_server.register(category, module_name, prefix)