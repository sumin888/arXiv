"""Structured API models (Pydantic BaseModel) for /api/query."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ChatRole = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role: ChatRole
    content: str = Field(default="", max_length=500_000)


class IndexRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    arxiv_id: str = Field(..., alias="arxivId", min_length=1, max_length=256)


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
    # Conceptual drift / bridge feature
    message_count: int = Field(default=0, alias="messageCount", ge=0)
    primary_category: str = Field(default="", alias="primaryCategory", max_length=64)
    active_bridge_id: str = Field(default="", alias="activeBridgeId", max_length=256)
    active_bridge_title: str = Field(default="", alias="activeBridgeTitle", max_length=1000)

    @model_validator(mode="after")
    def last_nonempty_turn_is_user(self):
        nonempty = [m for m in self.messages if m.content.strip()]
        if not nonempty:
            raise ValueError("At least one message with non-empty content is required")
        if nonempty[-1].role != "user":
            raise ValueError("The last non-empty message must be from the user")
        return self
