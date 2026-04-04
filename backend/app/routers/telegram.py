from __future__ import annotations
import httpx
from fastapi import APIRouter
from ..config import settings
from ..services.telegram import send_test

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.get("/test")
async def test_telegram():
    """發送一則測試訊息確認 Bot 有沒有通"""
    ok = await send_test()
    return {"success": ok, "chat_id": settings.TELEGRAM_CHAT_ID or "(未設定)"}


@router.get("/me")
async def get_chat_id():
    """
    幫你拿 chat_id：
    先去 Telegram 跟你的 Bot 傳任意訊息，再打這個 API
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN 未設定"}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"https://api.telegram.org/bot{token}/getUpdates")
        data = r.json()

    updates = data.get("result", [])
    if not updates:
        return {"error": "找不到任何訊息，請先去 Telegram 跟 Bot 傳一則訊息再試"}

    latest = updates[-1]
    msg = latest.get("message") or latest.get("channel_post") or {}
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    username = chat.get("username") or chat.get("first_name", "?")

    return {
        "chat_id": chat_id,
        "username": username,
        "hint": f"把 TELEGRAM_CHAT_ID={chat_id} 填入 .env 後重啟"
    }
