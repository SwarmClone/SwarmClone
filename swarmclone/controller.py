"""
主控——主控端的核心
"""
import asyncio
from typing import Any
from collections import deque

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

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
        self.messages_buffer: deque[Message] = deque(maxlen=200)
        self.started: bool = False

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
        /api/stop: 停止运行(POST)
        /api/get_status: 获取状态(GET)
        /api/get_messages: 获取最新信息(GET)
        /api/health: 检查是否在线(GET)
        """
        self.app.mount("/assets", StaticFiles(directory="panel/dist/assets"), name="assets")

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"]
        )
        
        @self.app.get("/")
        async def root():
            return HTMLResponse(open("panel/dist/index.html").read())
        
        @self.app.get("/api/health")
        async def health():
            return JSONResponse({"status": "ok"})

        @self.app.get("/api/get_status")
        async def get_status(selected: str = ""):
            """
            {
                "started":【布尔值，是否已启动】,
                "module_status":[
                    {
                        "role_name":【模块角色】,
                        "modules":[
                            {
                                "module_name":【模块名字】,
                                "running":【布尔值，是否运行】,
                                "loaded":【布尔值，是否加载】,
                                "err":【加载错误信息，若无错误则为null，若有错误则为错误信息】
                            },...
                        ]
                    },...
                ]
            }
            未加载+未运行=加载中
            已加载+未运行=已加载
            已加载+已运行=运行中
            """
            # 找到所有模块类
            names = [s.strip() for s in selected.split(",") if s.strip()]
            module_status = []
            for role, role_module_classes in module_classes.items():
                module_status.append({"role_name": role.value, "modules": []})
                for module_name, _module_class in role_module_classes.items():
                    if module_name not in names:
                        continue
                    module_status[-1]["modules"].append({
                        "module_name": module_name,
                        "running": False,
                        "loaded": False,
                        "err": None
                    })
            # 将运行中的模块标记为True
            for role in self.modules:
                for module in self.modules[role]:
                    for item in module_status:
                        if item["role_name"] == role.value:
                            for module_item in item["modules"]:
                                if module_item["module_name"] == module.name:
                                    module_item["running"] = module.running
                                    module_item["loaded"] = True
                                    module_item["err"] = None if module.err is None else repr(module.err)
            return JSONResponse({
                "started": self.started,
                "module_status": module_status
            })

        @self.app.get("/api/startup_param", response_class=JSONResponse)
        async def get_startup_param() -> JSONResponse:
            """
            [
                {
                    "role_name":【模块角色】,
                    "allowed_num":【允许加载的模块数量】,
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
                                    "multiline":【是否为多行文本，默认不是】,
                                    "min":【最小值】,
                                    "max":【最大值】,
                                    "step":【步长】 # 对于整数，默认为1，对于小数，默认为0.01,
                                    "password": 【是否需要隐藏输入值，默认为否】
                                },...
                            ]
                        },...
                    ]
                },...
            ]
            """
            config: list[Any] = []
            for role, role_module_classes in module_classes.items():
                if role in [ModuleRoles.LLM, ModuleRoles.TTS, ModuleRoles.CHAT, ModuleRoles.FRONTEND]:
                    allowed_num = 1
                else:
                    allowed_num = len(role_module_classes)
                
                config.append({"role_name": role.value, "allowed_num": allowed_num, "modules": []})
                for module_name, module_class in role_module_classes.items():
                    if "dummy" in module_name.lower() or "base" in module_name.lower():
                        continue  # 占位模块和模块基类不应被展示出来
                    # 使用ModuleBase的get_config_schema方法获取配置信息
                    schema = module_class.get_config_schema()
                    config[-1]["modules"].append({
                        "module_name": schema["module_name"],
                        "desc": schema["desc"],
                        "config": schema["config"]
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
                        module_class: type = module_classes[ModuleRoles(role)][module]
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
                            print(f"ERR: {e}")
                            return JSONResponse({"error": str(e)}, 500)
                        self.add_module(module)
            if missing_modules:
                return JSONResponse(missing_modules, 404)
            self.start_modules()
            return JSONResponse({"status": "started"})

        @self.app.post("/api/stop")
        async def stop():
            await self.stop_modules()
            self.clear_modules()
            return Response()

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
                speaker_name = data.get("speaker_name")
                content = data.get("message")
                if speaker_name and content:
                    await self.handle_message(ASRActivated(self.agent))
                    message = ASRMessage(
                        source=self.agent,
                        speaker_name=speaker_name,
                        message=content
                    )
                    await self.handle_message(message)
            
            return {"status": "OK"}
        
        @self.app.get("/api/get_version")
        async def get_version():
            response = JSONResponse({"version": __version__})
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response

        @self.app.get("/api/get_messages", response_class=JSONResponse)
        async def get_messages():
            """
            [
                {
                    "message_name": "【信息名】",
                    "send_time": 【发送时间戳，整数】,
                    "message_type": "【信息类型，DATA或者SIGNAL】",
                    "message_source": "【消息来源模块名】",
                    "message_destinations": [
                        "【消息目的地名】"
                    ],
                    "message": [
                        {"key": "键", "value": "值"},...
                    ],
                    "getters": [
                        {"name": "【获取者名】", "time": 【获取时间戳，整数】},...
                    ]
                },...
            ]
            """
            res: list[dict[str, Any]] = []
            for message in self.messages_buffer:
                res.append(message.get_dict_repr())
            self.messages_buffer.clear()
            return JSONResponse(res)

        @self.app.get("/{path:path}")
        async def serve_spa(request: Request, path: str):
            # 排除API和静态资源
            if path.startswith("api") or path.startswith("assets"):
                return Response(status_code=404)
            return HTMLResponse(open("panel/dist/index.html").read())

    async def handle_message(self, message: Message):
        for destination in message.destinations:
            if isinstance(destination, type):
                for _module_role, modules in self.modules.items():
                    for module in modules:
                        if isinstance(module, destination):
                            await module.task_queue.put(message)
            else:
                for module_destination in self.modules[destination]:
                    await module_destination.task_queue.put(message)
    
    def start_modules(self):
        loop = asyncio.get_event_loop()
        for (module_role, modules) in self.modules.items():
            for i, module in enumerate(filter(lambda x: not x.running, modules)):
                module_task = loop.create_task(module.run(), name=repr(module))
                handler_task = loop.create_task(self.handle_module(module, module_task), name=f"{module_role} handler")
                self.module_tasks.append(module_task)
                self.handler_tasks.append(handler_task)
                print(f"{module}已启动（{i + 1}/{len(modules)}）")
                module.running = True
            if len(modules) > 0:
                print(f"{module_role.value}模块已启动")
        self.started = True

    async def stop_modules(self):
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
        self.messages_buffer.clear()
        print("等待剩余协程退出")
        tasks = [
            t for t in asyncio.all_tasks()
            if t is not asyncio.current_task()
            and t.get_name() != "ROOT SERVER" # 不要取消掉服务器协程
        ]
        if tasks:
            for t in tasks:
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.started = False

    def run(self):
        self.start_modules()
        
        uvicorn_config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=8000,
            loop="asyncio"
        )
        server = uvicorn.Server(uvicorn_config)
        loop = asyncio.get_event_loop()

        server_task = loop.create_task(server.serve(), name="ROOT SERVER")
        try:
            loop.run_until_complete(server_task)
        except KeyboardInterrupt:
            loop.run_until_complete(self.stop_modules())
        finally:
            loop.run_until_complete(server.shutdown())
    
    async def handle_module(self, module: ModuleBase, module_task: asyncio.Task[None]):
        while True:
            if module_task.done():
                module.running = False
                if (not module_task.cancelled()) and ((err := module_task.exception()) is not None):
                    print(f"{module}模块任务异常：{err}")
                    module.err = err
                break
            if not module.results_queue.empty():
                result = module.results_queue.get_nowait()
                self.messages_buffer.append(result)
                await self.handle_message(result)
            await asyncio.sleep(0.05) # 以防空转占满 CPU
