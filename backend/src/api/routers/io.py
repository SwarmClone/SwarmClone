#一个直接与模型对话的预留接口
#悄悄话之类的
#也许能归到interface里去？
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class ChatMessage(BaseModel):
    source: str
    message: str

from backend.src.core import controller
from backend.src.core.event_bus import Event

router = APIRouter(prefix="/io", tags=["io"])

@router.post("/", response_class=JSONResponse)
async def chat(message: ChatMessage):
    await controller.event_message_publish(Event(name="chat", source=message.source, data=message.message))
    return {"status": "message published"}

@router.get("/", response_class=JSONResponse)
async def get_messages(request: Request):
    #获取最近的消息记录
    q = getattr(request.app.state, "_messages_queue", None)
    if q is None:
        return JSONResponse(status_code=500, content={"error": "messages queue not initialized"})

    try:
        msg = q.get_nowait()
    except asyncio.QueueEmpty:
        # 没有消息，返回 204 或空列表，根据需要调整
        return JSONResponse(status_code=204, content={})
    return JSONResponse(content={"message": msg})