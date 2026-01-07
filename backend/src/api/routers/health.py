from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/", response_class=JSONResponse)
async def health_check():
    return JSONResponse(content={"status": "ok"})
    
@router.get("/module", response_class=JSONResponse)
async def module_health_check():
    return JSONResponse(content={"status": "ok"})
#查询模块是否正常运行应该也会在这个子目录下
#后续如果有更多健康检查相关的接口，可以继续添加在这里
#没有也可以合并到server里去