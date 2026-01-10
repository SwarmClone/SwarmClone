import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncio

from backend.api.routers.io import router as io_router
from backend.api.routers.config import router as config_router
from backend.api.routers.lifespan import router as lifespan_router
from backend.api.routers.health import router as health_router

from backend.core.controller import Controller
from backend.core.event_bus import Event

class Server:
    """
    服务器类
    负责初始化和运行FastAPI服务器，处理HTTP请求和响应
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.app = FastAPI(title= "test server")
        self.register_routes()

        controller = Controller()
        controller.subscribe(
            module_name="server",
            config_events={},
            message_events={"rep": self.handle_rep_message} # type: ignore
        )

        #用于存储消息的缓冲区，同时要暴露在app.state里,以便路由能访问到
        self.app.state._messages_queue = asyncio.Queue(maxsize=5000)

    async def handle_rep_message(self, data: Event):
        #处理来自消息总线的消息
        await self.app.state._messages_queue.put(data.data)

    def register_routes(self):
        """
        注册FastAPI路由
        """
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"]
        )

        self.app.include_router(config_router)
        self.app.include_router(lifespan_router)
        self.app.include_router(health_router)  
        self.app.include_router(io_router)

        @self.app.get("/", response_class=HTMLResponse)
        async def read_root():
            return "<h1>Welcome to the FastAPI Server</h1>"


    def run(self):
        """
        运行FastAPI服务器
        """
        uvicorn_config=uvicorn.Config(
            self.app, 
            host=self.host, 
            port=self.port, 
            log_config=None)  # 不采用uvicorn默认日志配置，防止重复输出

        server = uvicorn.Server(uvicorn_config)
        self.app.state._uvicorn_server = server
        loop = asyncio.get_event_loop()

        server_task = loop.create_task(server.serve(), name="ROOT SERVER")
        try:
            loop.run_until_complete(server_task)
        except KeyboardInterrupt:
            pass
        finally:
            loop.run_until_complete(server.shutdown())
