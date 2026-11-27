"""Auto-generated typed palette stub for StylePack 'ink-1bit'."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Literal, Protocol, Self


class Ink1bitPalette(Protocol):
    """Static palette token contract for `ink-1bit`."""

    @property
    def style_id(self) -> str: ...

    @property
    def INK(self) -> int: ...

    @property
    def PAPER(self) -> int: ...

    @property
    def BG_D(self) -> int: ...

    @property
    def BG_M(self) -> int: ...

    @property
    def BG_L(self) -> int: ...

    @property
    def SURFACE_D(self) -> int: ...

    @property
    def SURFACE_M(self) -> int: ...

    @property
    def SURFACE_L(self) -> int: ...

    @property
    def ACCENT_1(self) -> int: ...

    @property
    def ACCENT_2(self) -> int: ...

    @property
    def EMISSIVE_1(self) -> int: ...

    @property
    def EMISSIVE_2(self) -> int: ...

    @property
    def ramps(self) -> dict[str, tuple[int, ...]]: ...

    def ramp(self, name: Literal["mono"]) -> tuple[int, ...]: ...

    def __getitem__(self, name: str) -> int: ...

    def __contains__(self, name: object) -> bool: ...

    def __len__(self) -> int: ...

    def __iter__(self) -> Iterator[str]: ...

    def with_overrides(
        self,
        overrides: Mapping[str, str | int] | None = None,
        /,
        **kw_overrides: str | int,
    ) -> Self: ...

    def to_dict(self) -> dict[str, int]: ...
