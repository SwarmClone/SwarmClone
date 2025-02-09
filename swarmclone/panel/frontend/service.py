from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import threading

class FrontendService:
    def __init__(self, host: str, port: int, static_dir: str):
        self.app = FastAPI()
        self.server = None
        self.host = host
        self.port = port
        self._configure_routes()
        self._mount_static(static_dir)

    def _configure_routes(self):
        @self.app.get("/")
        async def _redirect_root():
            return RedirectResponse(url="/pages/index.html")
        
        @self.app.post("/api/start_all/}")
        async def _start_module(request: Request):
            # 支持任意多个参数，可以在这个字典中读取
            args = dict(request.query_params)
            print(args)
            return {"message": "Starting all modules..."}
        

    def _mount_static(self, static_dir: str):
        self.app.mount("/", StaticFiles(directory=static_dir), name="static")

    def start(self):
        """启动服务并返回启动事件"""
        started_event = threading.Event()
        
        def run():
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.port,
                lifespan="on",
                log_level="critical"
            )
            self.server = uvicorn.Server(config)
            started_event.set()
            self.server.run()

        threading.Thread(target=run, daemon=True).start()
        return started_event

    def stop(self):
        """安全停止服务"""
        if self.server:
            self.server.should_exit = True