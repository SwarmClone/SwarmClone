#留给可能的控制各种开启和停止的接口
#可能是控制某个部分开关的也可以是直接关闭服务
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/lifespan", tags=["lifespan"])

@router.post("/start", response_class=JSONResponse)
async def start_lifespan(request: Request):
    #启动生命周期相关的操作
    #反正现在还没啥用
    return JSONResponse(content={"status": "started"})

@router.post("/stop", response_class=JSONResponse)
async def stop_lifespan(request: Request):
     # 从 app.state 读取 uvicorn.Server 实例并触发退出
    server = getattr(request.app.state, "_uvicorn_server", None)
    if server is None:
        return JSONResponse(status_code=500, content={"status": "error", "message": "server not found"})

    server.should_exit = True
    return JSONResponse(content={"status": "stopping"})
    #目前是一个关闭服务器的接口