"""
主控——主控端的核心
"""
from starlette.responses import JSONResponse


import asyncio
from typing import Any
from dataclasses import asdict, fields, MISSING

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse

from .modules import *
from .constants import *
from .module_manager import module_classes
from .utils import *

from . import __version__

class Controller:
    def __init__(self, config_path: str | None = None):
        self.clear_modules()
        self.app: FastAPI = FastAPI(title="Zhiluo Controller")
        self.register_routes()
        self.module_tasks: list[asyncio.Task[Any]] = []
        self.handler_tasks: list[asyncio.Task[Any]] = []
        self.agent: ModuleBase = ControllerDummy()

    def add_module(self, module: ModuleBase):
        """
        添加模块
        module: 模块
        """
        match module.role:
            case ModuleRoles.LLM:
                if len(self.modules[module.role]) > 0:
                    raise RuntimeError("只能注册一个LLM模块")
            case ModuleRoles.UNSPECIFIED:
                raise ValueError("请指定模块类型")
            case _:
                pass
        assert module.role in self.modules, "不明的模块类型"
        self.modules[module.role].append(module)
    
    def clear_modules(self):
        self.modules: dict[ModuleRoles, list[ModuleBase]] = {
            role: [] for role in ModuleRoles if role not in [ModuleRoles.UNSPECIFIED, ModuleRoles.CONTROLLER]
        }

    def register_routes(self):
        """ 注册FastAPI路由
        
        /:      根路由(GET)
        /api:   API路由(POST)
        /assets: 静态资源路由(GET)
        /api/get_version: 获取版本信息(GET)
        /api/startup_param: 获取配置信息(GET)
        /api/start: 加载配置信息并启动(POST)
        /api/get_status: 获取状态(GET)
        """
        self.app.mount("/assets", StaticFiles(directory="panel/dist/assets"), name="assets")
        
        @self.app.get("/")
        async def root():
            return HTMLResponse(open("panel/dist/index.html").read())
        
        @self.app.get("/api/get_status")
        async def get_status():
            """
            [
                {
                    "role_name":【模块角色】,
                    "modules":[
                        {
                            "module_name":【模块名字】,
                            "running":【布尔值，是否运行】,
                            "loaded":【布尔值，是否加载】
                        },...
                    ]
                },...
            ]
            """
            # 找到所有模块类
            status = []
            for role, role_module_classes in module_classes.items():
                status.append({"role_name": role.value, "modules": []})
                for module_name, _module_class in role_module_classes.items():
                    status[-1]["modules"].append({
                        "module_name": module_name,
                        "running": False
                    })
            # 将运行中的模块标记为True
            for role in self.modules:
                for module in self.modules[role]:
                    for item in status[-1]["modules"]:
                        if item["module_name"] == module.name:
                            item["running"] = module.running
                            item["loaded"] = True
            return JSONResponse(status)

        @self.app.get("/api/startup_param", response_class=JSONResponse)
        async def get_startup_param() -> JSONResponse:
            """
            [
                {
                    "role_name":【模块角色】,
                    "modules":[
                        {
                            "module_name":【模块名字】
                            "desc":【介绍】,
                            "config":[
                                {
                                    "name":【配置项名字】
                                    "type":【类型，int整数float小数（默认小数点后2位精度）str字符串bool布尔值（是/否）selection选择项】,
                                    "desc":【介绍信息】,
                                    "required":【布尔值，是否必填】,
                                    "default":【默认值】,
                                    "options":【可选项，仅对选择项有用，若为空则为无选项】,
                                    "min":【最小值】,
                                    "max":【最大值】,
                                    "step":【步长】 # 对于整数，默认为1，对于小数，默认为0.01
                                },...
                            ]
                        },...
                    ]
                },...
            ]
            """
            config: list[Any] = []
            for role, role_module_classes in module_classes.items():
                config.append({"role_name": role.value, "modules": []})
                for module_name, module_class in role_module_classes.items():
                    if "dummy" in module_name.lower():
                        continue # 占位模块不应被展示出来
                    config[-1]["modules"].append({
                        "module_name": module_name,
                        "desc": module_class.__doc__ or "",
                        "config": []
                    })
                    for field in fields(module_class.config_class): # config_class是被其元类注入的，是dataclass
                        name = field.name
                        default = ""
                        # 将各种类型转换为字符串表示
                        _type: str
                        raw_type = field.type
                        if isinstance(raw_type, type):
                            raw_type = raw_type.__name__
                        if "int" in raw_type and "float" not in raw_type: # 只在一个参数只能是int而不能是float时确定其为int
                            _type = "int" # TODO: if "int" == raw_type好像也行？
                        elif "float" in raw_type:
                            _type = "float"
                        elif "bool" in raw_type:
                            _type = "bool"
                        else:
                            _type = "str"
                        selection = field.metadata.get("selection", False)
                        if selection:
                            _type = "selection" # 如果是选择项则不管类型如何
                        
                        required = field.metadata.get("required", False)

                        desc = field.metadata.get("desc", "")

                        options = field.metadata.get("options", [])

                        if field.default is not MISSING and (default := field.default) is not None:
                            pass
                        elif field.default_factory is not MISSING and (default := field.default_factory()) is not None:
                            pass
                        else: # 无默认值则生成对应类型的空值
                            if _type == "str":
                                default = ""
                            elif _type == "int":
                                default = 0
                            elif _type == "float":
                                default = 0.0
                            elif _type == "bool":
                                default = False
                            elif _type == "selection":
                                default = options[0]["value"]
                        if isinstance(default, str):
                            default = escape_all(default) # 进行转义
                        
                        # 如果有的话，提供最大最小值和步长
                        minimum = field.metadata.get("min")
                        maximum = field.metadata.get("max")
                        step = field.metadata.get("step")

                        config[-1]["modules"][-1]["config"].append({
                            "name": name,
                            "type": _type,
                            "desc": desc,
                            "required": required,
                            "default": default,
                            "options": options,
                            "min": minimum,
                            "max": maximum,
                            "step": step
                        })
            return JSONResponse(config)
        
        @self.app.post("/api/start", response_class=JSONResponse)
        async def start(request: Request) -> JSONResponse:
            """
            {
                "cfg": {
                    "模块角色": {
                        "模块名称": {
                            "配置项": "配置值", ...
                        }, ...
                    }, ...
                },
                "selected": [
                    "选中模块名称", ...
                ]
            }
            """
            data = await request.json()
            self.clear_modules()
            missing_modules: list[str] = []
            cfg = data["cfg"]
            for role in cfg.keys():
                for module in cfg[role].keys():
                    module_config = cfg[role][module]
                    try:
                        module_class = module_classes[ModuleRoles(role)][module]
                    except KeyError:
                        missing_modules.append(module)
                        continue
                    
                    if not missing_modules: # 如果已有缺少模块就不再尝试加载更多模块
                        for key, value in module_config.items():
                            if isinstance(value, str):
                                # 去转义
                                module_config[key] = unescape_all(value)
                            else:
                                module_config[key] = value
                        try:
                            module = module_class(**module_config)
                        except Exception as e:
                            return JSONResponse({"error": str(e)}, 500)
                        self.add_module(module)
            if missing_modules:
                return JSONResponse(missing_modules, 404)
            self.start_modules()
            return JSONResponse({"status": "OK"})

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
                await self.handle_message(ASRActivated(self.agent))
                message = ASRMessage(
                    source=self.agent,
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
    
    def start_modules(self):
        loop = asyncio.get_event_loop()
        for (module_role, modules) in self.modules.items():
            for i, module in enumerate(filter(lambda x: not x.running, modules)):
                self.module_tasks.append(loop.create_task(module.run(), name=repr(module)))
                self.handler_tasks.append(loop.create_task(self.handle_module(module), name=f"{module_role} handler"))
                print(f"{module}已启动（{i + 1}/{len(modules)}）")
                module.running = True
            if len(modules) > 0:
                print(f"{module_role.value}模块已启动")

    def stop_modules(self):
        for task in self.module_tasks:
            print(f"停止{task.get_name()}模块任务")
            task.cancel()
        for task in self.handler_tasks:
            print(f"停止{task.get_name()}模块任务")
            task.cancel()
        for _role, modules in self.modules.items():
            for module in modules:
                module.running = False
        self.module_tasks.clear()
        self.handler_tasks.clear()

    def run(self):
        self.start_modules()
        
        uvcorn_config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=8000,
            loop="asyncio"
        )
        server = uvicorn.Server(uvcorn_config)
        loop = asyncio.get_event_loop()
        server_task = loop.create_task(server.serve())
        try:
            loop.run_until_complete(server_task)
        except KeyboardInterrupt:
            self.stop_modules()
            server_task.cancel()
        finally:
            loop.run_until_complete(server.shutdown())
    
    async def handle_module(self, module: ModuleBase):
        while True:
            result: Message = await module.results_queue.get()
            await self.handle_message(result)
