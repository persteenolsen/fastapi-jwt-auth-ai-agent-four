from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    message: str


class PrivateRAGResult(BaseModel):
    """Structured result returned by the private knowledge service."""

    answer: str
    source: list[Any] = Field(default_factory=list)
    status: Literal[
        "sources_found",
        "unverified",
        "error",
    ] = "unverified"
    error: str | None = None


class AgentResponse(BaseModel):
    action: str
    action_input: Any = None
    observation: list[dict] = Field(default_factory=list)
    final_answer: str
    tools_used: list[str] = Field(default_factory=list)
    source: list[Any] = Field(default_factory=list)
    status: str = "unknown"


class ChatResponse(BaseModel):
    response: AgentResponse
