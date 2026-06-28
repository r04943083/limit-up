"""AI chat routes (#1)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lucore.services import chat

router = APIRouter(prefix="/chat", tags=["chat"])


class SendIn(BaseModel):
    message: str
    session_id: str = "default"


@router.get("/history", response_model=list[chat.ChatTurn])
def history(session_id: str = "default") -> list[chat.ChatTurn]:
    return chat.history(session_id)


@router.post("/send", response_model=chat.ChatReply)
def send(body: SendIn) -> chat.ChatReply:
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="empty message")
    try:
        return chat.send(body.message, session_id=body.session_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"chat failed: {e}") from e


@router.delete("/history")
def clear(session_id: str = "default") -> dict:
    return {"cleared": chat.clear(session_id)}
