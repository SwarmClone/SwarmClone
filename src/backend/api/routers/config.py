from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Any
from pydantic import BaseModel

from backend.core import controller

router = APIRouter(prefix="/config", tags=["config"])

class ConfigUpdateRequest(BaseModel):
    data: dict[str, Any]

@router.post("/", response_class=JSONResponse)
async def update_config(request: Request, config_update: ConfigUpdateRequest):
    try:
        result = request.app.state.controller.configure_change(config_update.data) # type: ignore
        return JSONResponse(status_code=200, content={"status": "ok", "result": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/", response_class=JSONResponse)
async def get_config():
    return JSONResponse(content=controller.config_manager.config_data) # type: ignore