"""
主控——主控端的核心
"""
import asyncio

from flask import Flask
from flask import request, jsonify

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
        self.app = Flask(__name__)
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
        @self.app.route("/")
        async def index():
            return "Hello, Zhiluo!"

        @self.app.route("/api", methods=["POST"])
        async def api():
            data = request.get_json()
            if not data:
                return jsonify({"error": "Invalid JSON"}), 400
            if "module" not in data:
                return jsonify({"error": "Missing module field"}), 400

            module = data.get("module")
            
            if module == ModuleRoles.ASR.value:
                speaker_name = data.get("speaker_name")
                content = data.get("content")
                message = ASRMessage(
                    source=ControllerDummy(),
                    speaker_name=speaker_name,
                    message=content
                )
                for destination in message.destinations:
                    for module_destination in self.modules[destination]:
                        await module_destination.task_queue.put(message)
            
            return jsonify({"status": "OK"}), 200

    def start(self):
        loop = asyncio.get_event_loop()
        for (module_role, modules) in self.modules.items():
            for module in modules:
                loop.create_task(module.run())
                loop.create_task(self.handle_module(module))
                print(f"{module}已启动")
            if len(modules) > 0:
                print(f"{module_role.value}模块已启动")

        self.app.run()
        loop.run_forever()
    
    async def handle_module(self, module: ModuleBase):
        while True:
            result: Message = await module.results_queue.get()
            for destination in result.destinations:
                for module_destination in self.modules[destination]:
                    await module_destination.task_queue.put(result)
