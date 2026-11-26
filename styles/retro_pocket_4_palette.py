"""Auto-generated typed palette stub for StylePack 'retro-pocket-4'."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Protocol, Self


class RetroPocket4Palette(Protocol):
    """Static palette token contract for `retro-pocket-4`."""

    @property
    def style_id(self) -> str: ...

    @property
    def INK(self) -> int: ...

    @property
    def SHADE_D(self) -> int: ...

    @property
    def SHADE_L(self) -> int: ...

    @property
    def HIGHLIGHT(self) -> int: ...

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
