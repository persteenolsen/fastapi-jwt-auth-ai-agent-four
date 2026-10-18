
from typing import Any, Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    message: str


class AgentResponse(BaseModel):
    action: str
    action_input: Any = None
    observation: list[dict] = []
    final_answer: str
    tools_used: list[str] = []


class ChatResponse(BaseModel):
    response: AgentResponse
