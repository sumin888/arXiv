"""Tool registry: register, describe, and execute tools for the agent loop."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class _ToolEntry:
    name: str
    schema: dict
    fn: Callable[..., Awaitable[str]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, _ToolEntry] = {}

    def register(self, schema: dict, fn: Callable[..., Awaitable[str]]) -> None:
        name = schema["name"]
        self._tools[name] = _ToolEntry(name=name, schema=schema, fn=fn)

    def schemas(self) -> list[dict]:
        return [t.schema for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    async def execute(self, name: str, **kwargs: Any) -> str:
        if name not in self._tools:
            return f"Unknown tool: {name!r}. Available: {', '.join(self.names())}"
        try:
            return await self._tools[name].fn(**kwargs)
        except Exception as exc:
            return f"Tool '{name}' raised {type(exc).__name__}: {exc}"
