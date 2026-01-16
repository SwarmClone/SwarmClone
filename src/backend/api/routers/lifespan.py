#留给可能的控制各种开启和停止的接口
#可能是控制某个部分开关的也可以是直接关闭服务
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.modules.ai.test import factory as TestAIFactory

router = APIRouter(prefix="/lifespan", tags=["lifespan"])


@router.post("/start", response_class=JSONResponse)
async def start_lifespan(request: Request):
    is_started = getattr(request.app.state, "is_started", None)
    if not is_started:
        await request.app.state.controller.start_all({"ai": TestAIFactory})  # type: ignore
        request.app.state.is_started = True
        return JSONResponse(content={
            "status": "started",
            "operation": "success",
            "message": "server is started"
        })
    else:
        return JSONResponse(status_code=500, content={
            "status": "started",
            "operation": "failed",
            "message": "server is already started"
        })


@router.post("/stop", response_class=JSONResponse)
async def stop_lifespan(request: Request):
    # 从 app.state 读取 uvicorn.Server 实例并触发退出
    server = getattr(request.app.state, "_uvicorn_server", None)
    if server is None:
        return JSONResponse(status_code=500, content={
            "status": "stopped",
            "operation": "failed",
            "message": "error when stopping server: server instance not found"
        })

    server.should_exit = True
    return JSONResponse(content={
        "status": "stopped",
        "operation": "success",
        "message": "server stopped"
    })
