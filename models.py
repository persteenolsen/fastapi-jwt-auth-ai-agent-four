
from typing import Any
from pydantic import BaseModel, Field


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
    observation: list[dict] = Field(default_factory=list)
    final_answer: str
    tools_used: list[str] = Field(default_factory=list)

    # New fields
    source: list[Any] = Field(default_factory=list)
    status: str = "unknown"


class ChatResponse(BaseModel):
    response: AgentResponse
