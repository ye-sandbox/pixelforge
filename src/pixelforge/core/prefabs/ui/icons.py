"""Modular multi-genre pixel icon registries (`8x8`, `12x12`, `16x16`)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal, get_args

from pixelforge.core.prefabs.ui.icons_core import (
    ICON_GRIDS_CORE_8,
    ICON_GRIDS_CORE_12,
    ICON_GRIDS_CORE_16,
)
from pixelforge.core.prefabs.ui.icons_rpg import (
    ICON_GRIDS_RPG_8,
    ICON_GRIDS_RPG_12,
    ICON_GRIDS_RPG_16,
)
from pixelforge.core.prefabs.ui.icons_tech import (
    ICON_GRIDS_TECH_8,
    ICON_GRIDS_TECH_12,
    ICON_GRIDS_TECH_16,
)
from pixelforge.core.prefabs.ui.palette import UiTarget

UiIconSize = Literal[8, 12, 16]
UiIconPackName = Literal["core", "rpg", "tech"]

# Preserved for backwards compatibility with existing `ui_icon_16` callers.
UiIconKind = Literal[
    "cpu",
    "ram",
    "disk",
    "network",
    "power",
    "alert",
    "bolt",
    "terminal",
    "check",
    "lock",
]

_VALID_ICON_SIZES: Final[tuple[UiIconSize, ...]] = get_args(UiIconSize)
_VALID_GLYPH_CHARS: Final[frozenset[str]] = frozenset({".", "#", "+", "o"})
_BUILTIN_PACK_ORDER: Final[tuple[str, ...]] = ("tech", "core", "rpg")


def _validate_icon_grid(
    name: str,
    grid: tuple[str, ...],
    size: int | None = None,
) -> UiIconSize:
    """Validate icon grid dimensions and glyph characters, returning canonical size."""
    resolved_size = len(grid) if size is None else size
    if resolved_size not in _VALID_ICON_SIZES:
        msg = (
            f"Icon {name!r} has unsupported size {resolved_size}; "
            f"expected one of {_VALID_ICON_SIZES}."
        )
        raise ValueError(msg)
    if len(grid) != resolved_size:
        msg = f"Icon {name!r} expected {resolved_size} rows, got {len(grid)}."
        raise ValueError(msg)
    for row_idx, row in enumerate(grid):
        if len(row) != resolved_size:
            msg = f"Icon {name!r} row {row_idx} expected width {resolved_size}, got {len(row)}."
            raise ValueError(msg)
        invalid_chars = set(row) - _VALID_GLYPH_CHARS
        if invalid_chars:
            msg = f"Icon {name!r} row {row_idx} contains invalid chars {sorted(invalid_chars)!r}."
            raise ValueError(msg)
    return resolved_size


@dataclass
class UiIconPack:
    """Named collection of pixel icon grids indexed by `(size, name)`."""

    name: str
    grids: dict[UiIconSize, dict[str, tuple[str, ...]]] = field(
        default_factory=lambda: {8: {}, 12: {}, 16: {}},
    )

    def register(
        self,
        name: str,
        grid: tuple[str, ...],
        *,
        size: UiIconSize | None = None,
        overwrite: bool = False,
    ) -> None:
        """Validate and register an icon grid in this pack."""
        resolved_size = _validate_icon_grid(name, grid, size=size)
        bucket = self.grids.setdefault(resolved_size, {})
        if name in bucket and not overwrite:
            msg = (
                f"Icon {name!r} ({resolved_size}x{resolved_size}) "
                f"already exists in pack {self.name!r}."
            )
            raise ValueError(msg)
        bucket[name] = tuple(grid)

    def get(self, name: str, size: UiIconSize = 16) -> tuple[str, ...] | None:
        """Return the icon grid for `name` at `size`, or `None` if absent."""
        return self.grids.get(size, {}).get(name)

    def has(self, name: str, size: UiIconSize | None = None) -> bool:
        """Return whether `name` is registered in this pack (optionally at `size`)."""
        if size is not None:
            return name in self.grids.get(size, {})
        return any(name in bucket for bucket in self.grids.values())

    def list_icons(self, size: UiIconSize | None = None) -> list[str]:
        """Return sorted icon names in this pack (optionally filtered by `size`)."""
        if size is not None:
            return sorted(self.grids.get(size, {}).keys())
        names: set[str] = set()
        for bucket in self.grids.values():
            names.update(bucket.keys())
        return sorted(names)


def _build_pack(
    name: str,
    grids_by_size: Mapping[UiIconSize, Mapping[str, tuple[str, ...]]],
) -> UiIconPack:
    pack = UiIconPack(name=name)
    for size, items in grids_by_size.items():
        for icon_name, grid in items.items():
            pack.register(icon_name, grid, size=size)
    return pack


ui_icons_core: Final[UiIconPack] = _build_pack(
    "core",
    {8: ICON_GRIDS_CORE_8, 12: ICON_GRIDS_CORE_12, 16: ICON_GRIDS_CORE_16},
)
ui_icons_rpg: Final[UiIconPack] = _build_pack(
    "rpg",
    {8: ICON_GRIDS_RPG_8, 12: ICON_GRIDS_RPG_12, 16: ICON_GRIDS_RPG_16},
)
ui_icons_tech: Final[UiIconPack] = _build_pack(
    "tech",
    {8: ICON_GRIDS_TECH_8, 12: ICON_GRIDS_TECH_12, 16: ICON_GRIDS_TECH_16},
)

_ICON_PACKS: dict[str, UiIconPack] = {
    "core": ui_icons_core,
    "rpg": ui_icons_rpg,
    "tech": ui_icons_tech,
}


def list_icon_packs() -> list[str]:
    """Return registered icon pack names in deterministic lookup order."""
    builtin = [name for name in _BUILTIN_PACK_ORDER if name in _ICON_PACKS]
    custom = sorted(name for name in _ICON_PACKS if name not in _BUILTIN_PACK_ORDER)
    return [*builtin, *custom]


def register_icon_pack(
    pack_name: str,
    icons_by_size: Mapping[UiIconSize, Mapping[str, tuple[str, ...]]] | None = None,
    *,
    overwrite: bool = False,
) -> UiIconPack:
    """Register a new named icon pack (or replace an existing one with `overwrite=True`)."""
    if pack_name in _ICON_PACKS and not overwrite:
        msg = f"Icon pack {pack_name!r} is already registered."
        raise ValueError(msg)
    pack = _build_pack(pack_name, icons_by_size or {})
    _ICON_PACKS[pack_name] = pack
    return pack


def unregister_icon_pack(pack_name: str) -> bool:
    """Remove a custom icon pack by name, returning `True` if it existed."""
    if pack_name in _BUILTIN_PACK_ORDER:
        msg = f"Cannot unregister built-in icon pack {pack_name!r}."
        raise ValueError(msg)
    return _ICON_PACKS.pop(pack_name, None) is not None


def register_icon(
    name: str,
    grid: tuple[str, ...],
    *,
    size: UiIconSize | None = None,
    pack: str = "custom",
    overwrite: bool = False,
) -> None:
    """Register an `8x8`, `12x12`, or `16x16` pixel icon into a pack (creating it if needed)."""
    target_pack = _ICON_PACKS.get(pack)
    if target_pack is None:
        target_pack = UiIconPack(name=pack)
        _ICON_PACKS[pack] = target_pack
    target_pack.register(name, grid, size=size, overwrite=overwrite)


def get_icon_grid(
    name: str,
    size: UiIconSize = 16,
    *,
    pack: str | None = None,
) -> tuple[str, ...]:
    """Resolve an icon grid by `name`, `size`, and optional `pack`."""
    if size not in _VALID_ICON_SIZES:
        msg = f"Unsupported icon size {size}; expected one of {_VALID_ICON_SIZES}."
        raise ValueError(msg)

    if pack is not None:
        target_pack = _ICON_PACKS.get(pack)
        if target_pack is None:
            msg = f"Unknown icon pack {pack!r}. Available: {', '.join(list_icon_packs())}."
            raise KeyError(msg)
        grid = target_pack.get(name, size)
        if grid is None:
            msg = f"Icon {name!r} ({size}x{size}) not found in pack {pack!r}."
            raise KeyError(msg)
        return grid

    for pack_name in list_icon_packs():
        grid = _ICON_PACKS[pack_name].get(name, size)
        if grid is not None:
            return grid

    msg = f"Icon {name!r} ({size}x{size}) not found in any registered pack."
    raise KeyError(msg)


def list_icons(
    *,
    pack: str | None = None,
    size: UiIconSize | None = None,
) -> list[str]:
    """List registered icon names, optionally filtered by `pack` and/or `size`."""
    if pack is not None:
        target_pack = _ICON_PACKS.get(pack)
        if target_pack is None:
            msg = f"Unknown icon pack {pack!r}. Available: {', '.join(list_icon_packs())}."
            raise KeyError(msg)
        return target_pack.list_icons(size=size)

    names: set[str] = set()
    for target_pack in _ICON_PACKS.values():
        names.update(target_pack.list_icons(size=size))
    return sorted(names)


def ui_icon(
    a: UiTarget,
    x: int,
    y: int,
    kind: str,
    fg: int,
    *,
    size: UiIconSize = 16,
    pack: str | None = None,
    bg: int | None = None,
    accent: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a crisp pixel icon (`8x8`, `12x12`, or `16x16`) from any registered pack."""
    grid = get_icon_grid(kind, size=size, pack=pack)
    if bg is not None:
        a.rect(x, y, size, size, color=bg)
    color_map: dict[str, int] = {
        "#": fg,
        "+": fg if accent is None else accent,
        "o": fg if outline is None else outline,
    }
    a.spr(grid, x, y, color_map)


def ui_icon_8(
    a: UiTarget,
    x: int,
    y: int,
    kind: str,
    fg: int,
    *,
    pack: str | None = None,
    bg: int | None = None,
    accent: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a crisp `8x8` pixel icon from the registered icon packs."""
    ui_icon(a, x, y, kind, fg, size=8, pack=pack, bg=bg, accent=accent, outline=outline)


def ui_icon_12(
    a: UiTarget,
    x: int,
    y: int,
    kind: str,
    fg: int,
    *,
    pack: str | None = None,
    bg: int | None = None,
    accent: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a crisp `12x12` pixel icon from the registered icon packs."""
    ui_icon(a, x, y, kind, fg, size=12, pack=pack, bg=bg, accent=accent, outline=outline)


def ui_icon_16(
    a: UiTarget,
    x: int,
    y: int,
    kind: UiIconKind | str,
    fg: int,
    *,
    pack: str | None = None,
    bg: int | None = None,
    accent: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a crisp `16x16` pixel icon from the registered icon packs."""
    ui_icon(a, x, y, kind, fg, size=16, pack=pack, bg=bg, accent=accent, outline=outline)
