import asyncio
import uvicorn
import threading
from loguru import logger as log
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ...config import config

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
        
        @self.app.post("/api/start_all/")
        async def _start_module(request: Request):
            # 获取 POST 请求中的 JSON 数据
            args = await request.json()
            log.debug(f"Starting all modules...\n{args}")

            async def read_stream(stream, logger):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    try:
                        # 先尝试utf-8解码
                        decoded = line.decode('utf-8').strip()
                    except UnicodeDecodeError:
                        # 使用GBK作为后备编码
                        decoded = line.decode('gbk', errors='replace').strip()
                    logger(decoded)

            # 所有需要启动的模块命令列表
            commands = [
                config.START_ASR_COMMAND,
                config.START_TTS_COMMAND,
                config.START_LLM_COMMAND,
                config.START_FRONTEND_COMMAND
                # 此处不应包含Panel的启动命令，因为显然Panel已经启动
            ]

            create_procs = []
            for cmd in commands:
                try:
                    # 创建异步子进程
                    create_procs.append(
                        asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                    )
                except Exception as e:
                    log.error(f"创建子进程命令 {cmd} 时出错: {e}")

            # 并行执行所有子进程的创建
            results = await asyncio.gather(*create_procs, return_exceptions=True)

            # 处理每个子进程的结果
            for cmd, result in zip(commands, results):
                if isinstance(result, Exception):
                    log.error(f"启动命令 {cmd} 失败: {result}")
                    continue
                proc = result
                assert isinstance(proc, asyncio.subprocess.Process) # 让mypy不抱怨类型不对
                log.debug(f"模块启动成功: {' '.join(cmd)} (PID: {proc.pid})")
                # 捕获输出到日志
                asyncio.create_task(read_stream(proc.stdout, log.debug))
                asyncio.create_task(read_stream(proc.stderr, log.error))

            return {"message": "所有模块启动命令已执行"}

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
                log_level="error"
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