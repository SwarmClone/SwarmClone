"""
主控——主控端的核心
"""
import uvicorn
import asyncio

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from .modules import *
from .constants import *

class Controller:
    def __init__(self):
        self.modules: dict[ModuleRoles, list[ModuleBase]] = {
            ModuleRoles.ASR: [],
            ModuleRoles.CHAT: [],
            ModuleRoles.FRONTEND: [],
            ModuleRoles.LLM: [],
            ModuleRoles.PLUGIN: [],
            ModuleRoles.TTS: [],
        }
        self.app = FastAPI(title="Zhiluo Controller")
        self.register_routes()
    
    def register(self, module: ModuleBase):
        assert module.role in self.modules, "不明的模块类型"
        match module.role:
            case ModuleRoles.LLM:
                if len(self.modules[module.role]) > 0:
                    raise RuntimeError("只能注册一个LLM模块")
        self.modules[module.role].append(module)
                   
    def register_routes(self):
        """ 注册Flask路由
        
        /:      根路由
        /api:   API路由
        """
        @self.app.get("/")
        async def index():
            return {"message": "Hello, Zhiluo!"}


        @self.app.post("/api")
        async def api(request: Request):
            try:
                data = await request.json()
            except Exception:
                return JSONResponse(
                    {"error": "Invalid JSON"},
                    status_code=400
                )
            
            if "module" not in data:
                return JSONResponse(
                    {"error": "Missing module field"},
                    status_code=400
                )

            module = data.get("module")
            
            if module == ModuleRoles.ASR.value:
                await self.handle_message(ASRActivated(self))
                message = ASRMessage(
                    source=ControllerDummy(),
                    speaker_name=data.get("speaker_name"),
                    message=data.get("content")
                )
                await self.handle_message(message)
            
            return {"status": "OK"}
    
    async def handle_message(self, message: Message):
        for destination in message.destinations:
            for module_destination in self.modules[destination]:
                await module_destination.task_queue.put(message)

    def start(self):
        loop = asyncio.get_event_loop()
        for (module_role, modules) in self.modules.items():
            for module in modules:
                loop.create_task(module.run())
                loop.create_task(self.handle_module(module))
                print(f"{module}已启动")
            if len(modules) > 0:
                print(f"{module_role.value}模块已启动")
                
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=5000,
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    
    async def handle_module(self, module: ModuleBase):
        while True:
            result: Message = await module.results_queue.get()
            await self.handle_message(result)
