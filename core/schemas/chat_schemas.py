"""Pydantic schemas for the Chat API route."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=2000)
    language: str = "uz"


class ChatMessageResponse(BaseModel):
    session_id: str
    reply: str
    intent: str = "other"
    is_ai: bool = True
