"""Auto-generated typed palette stub for StylePack 'topdown-rpg'."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Literal, Protocol, Self


class TopdownRpgPalette(Protocol):
    """Static palette token contract for `topdown-rpg`."""

    @property
    def style_id(self) -> str: ...

    @property
    def VOID(self) -> int: ...

    @property
    def INK(self) -> int: ...

    @property
    def SOIL_D(self) -> int: ...

    @property
    def SOIL_M(self) -> int: ...

    @property
    def SOIL_L(self) -> int: ...

    @property
    def GRASS_D(self) -> int: ...

    @property
    def GRASS_M(self) -> int: ...

    @property
    def GRASS_L(self) -> int: ...

    @property
    def LEAF_L(self) -> int: ...

    @property
    def STONE_D(self) -> int: ...

    @property
    def STONE_M(self) -> int: ...

    @property
    def STONE_L(self) -> int: ...

    @property
    def STONE_H(self) -> int: ...

    @property
    def BARK_D(self) -> int: ...

    @property
    def BARK_M(self) -> int: ...

    @property
    def BARK_L(self) -> int: ...

    @property
    def WATER_D(self) -> int: ...

    @property
    def WATER_M(self) -> int: ...

    @property
    def WATER_L(self) -> int: ...

    @property
    def IRON_D(self) -> int: ...

    @property
    def IRON_M(self) -> int: ...

    @property
    def IRON_L(self) -> int: ...

    @property
    def GOLD_D(self) -> int: ...

    @property
    def GOLD_M(self) -> int: ...

    @property
    def GOLD_L(self) -> int: ...

    @property
    def RUBY_D(self) -> int: ...

    @property
    def RUBY_M(self) -> int: ...

    @property
    def TORCH_GLOW(self) -> int: ...

    @property
    def TORCH_CORE(self) -> int: ...

    @property
    def MANA_GLOW(self) -> int: ...

    @property
    def MANA_CORE(self) -> int: ...

    @property
    def RUNE_GOLD(self) -> int: ...

    @property
    def ramps(self) -> dict[str, tuple[int, ...]]: ...

    def ramp(
        self,
        name: Literal[
            "soil",
            "grass",
            "stone",
            "bark",
            "water",
            "iron",
            "gold",
        ],
    ) -> tuple[int, ...]: ...

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
