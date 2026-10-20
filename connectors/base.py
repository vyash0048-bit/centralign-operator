"""Base abstractions for connectors and tools in CentrAlign."""
from __future__ import annotations

import inspect
from abc import ABC
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Standardized result returned by every connector/tool action."""
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    error_code: Optional[str] = None
    screenshot_path: Optional[str] = None


class BaseConnector(ABC):
    """Abstract base class for all connectors."""
    pass


class ToolRegistry:
    """Registry mapping string tool names to executable connector functions."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., ToolResult]] = {}

    def register(self, tool_name: str, func: Callable[..., ToolResult]) -> None:
        self._tools[tool_name] = func

    def get(self, tool_name: str) -> Optional[Callable[..., ToolResult]]:
        return self._tools.get(tool_name)

    def execute(self, tool_name: str, /, **kwargs: Any) -> ToolResult:
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' is not registered in ToolRegistry.",
                error_code="TOOL_NOT_FOUND",
            )
        try:
            sig = inspect.signature(tool)
            has_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if has_var_keyword:
                call_kwargs = kwargs
            else:
                call_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
            return tool(**call_kwargs)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Unhandled exception executing '{tool_name}': {str(exc)}",
                error_code="EXECUTION_ERROR",
            )
