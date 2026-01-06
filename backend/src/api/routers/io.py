#一个直接与模型对话的预留接口
#悄悄话之类的
#也许能归到interface里去？
import re
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...core import controller
from ...core.event_bus import Event

router = APIRouter(prefix="/io", tags=["io"])

@router.post("/", response_class=JSONResponse)
async def chat(request: Request):
    data = await request.json()
    await controller.event_message_publish(Event(name="chat", source=data.get("source"), data=data.get("message")))
    return {"status": "message published"}

@router.get("/", response_class=JSONResponse)
async def get_messages(request: Request):
    #获取最近的消息记录
    return JSONResponse(content={"messages": request.app.state._messages_buffer})