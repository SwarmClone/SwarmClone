"""
主控——主控端的核心
"""
import uvicorn
import asyncio

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse

from .modules import *
from .constants import *

from . import __version__

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
        """ 注册FastAPI路由
        
        /:      根路由
        /api:   API路由
        /assets: 静态资源路由
        /api/get_version: 获取版本信息
        """
        self.app.mount("/assets", StaticFiles(directory="panel/dist/assets"), name="assets")
        
        @self.app.get("/")
        async def root():
            return HTMLResponse(open("panel/dist/index.html").read())

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
                await self.handle_message(ASRActivated(ControllerDummy()))
                message = ASRMessage(
                    source=ControllerDummy(),
                    speaker_name=data.get("speaker_name"),
                    message=data.get("content")
                )
                await self.handle_message(message)
            
            return {"status": "OK"}
        
        @self.app.get("/api/get_version")
        async def get_version():
            response = JSONResponse({"version": __version__})
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response
    
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
            port=8000,
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        try:
            loop.run_until_complete(server.serve())
        except KeyboardInterrupt:
            print("关闭服务器...")
    
    async def handle_module(self, module: ModuleBase):
        while True:
            result: Message = await module.results_queue.get()
            await self.handle_message(result)
