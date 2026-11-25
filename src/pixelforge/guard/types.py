"""Shared guard types and violation formatting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GuardSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class GuardViolation:
    """Single static or runtime guard finding."""

    file: str
    line: int
    col: int
    rule: str
    detail: str
    severity: GuardSeverity = "error"

    def format_line(self) -> str:
        """Format violation as `file:line [rule] detail`."""
        return f"{self.file}:{self.line} [{self.rule}] {self.detail}"
