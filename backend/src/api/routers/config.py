from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...core import controller

router = APIRouter(prefix="/config", tags=["config"])

@router.post("/", response_class=JSONResponse)
async def update_config(request: Request):
    data = await request.json()
    try:
        result = controller.configure_change(data)
        return JSONResponse(status_code=200, content={"status": "ok", "result": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/", response_class=JSONResponse)
async def get_config():
    return JSONResponse(content=controller.config_manager.config_data)