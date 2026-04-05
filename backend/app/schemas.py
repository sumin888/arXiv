"""Structured API models (Pydantic BaseModel) for /api/query."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ChatRole = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role: ChatRole
    content: str = Field(default="", max_length=500_000)


class QueryRequest(BaseModel):
    """Body for POST /api/query. Use JSON keys `arxivId` (camelCase) from the browser extension."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    arxiv_id: str = Field(..., alias="arxivId", min_length=1, max_length=256)
    title: str = Field(default="", max_length=20_000)
    abstract: str = Field(default="", max_length=200_000)
    messages: list[ChatMessage] = Field(..., min_length=1)

    @model_validator(mode="after")
    def last_nonempty_turn_is_user(self):
        nonempty = [m for m in self.messages if m.content.strip()]
        if not nonempty:
            raise ValueError("At least one message with non-empty content is required")
        if nonempty[-1].role != "user":
            raise ValueError("The last non-empty message must be from the user")
        return self


class QueryResponse(BaseModel):
    reply: str


class ChatRequest(BaseModel):
    """Body for POST /chat — full agent loop with tool calling."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    arxiv_id: str = Field(..., alias="arxivId", min_length=1, max_length=256)
    title: str = Field(default="", max_length=20_000)
    abstract: str = Field(default="", max_length=200_000)
    messages: list[ChatMessage] = Field(..., min_length=1)
    # Reserved for future per-request tool filtering; empty = all tools enabled
    tools: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def last_nonempty_turn_is_user(self):
        nonempty = [m for m in self.messages if m.content.strip()]
        if not nonempty:
            raise ValueError("At least one message with non-empty content is required")
        if nonempty[-1].role != "user":
            raise ValueError("The last non-empty message must be from the user")
        return self
