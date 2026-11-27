"""Typed StylePack palette stub generation for static Pyright validation."""

from __future__ import annotations

import re
from pathlib import Path

from pixelforge.core.types import StylePack

_SPLIT_RE = re.compile(r"[-_]+")


def palette_stub_class_name(style_id: str) -> str:
    """Return the PascalCase Protocol class name for `style_id`."""
    parts = [part.capitalize() for part in _SPLIT_RE.split(style_id) if part]
    stem = "".join(parts) or "Style"
    return f"{stem}Palette"


def palette_stub_path(style_path: Path) -> Path:
    """Return the co-located `*_palette.py` stub path for a `*.style.py` file."""
    stem = style_path.name.removesuffix(".style.py")
    return style_path.with_name(f"{stem}_palette.py")


def generate_palette_stub(style: StylePack) -> str:
    """Generate a `ruff`-formatted `Protocol` stub module for `style`."""
    class_name = palette_stub_class_name(style.id)
    typing_imports = "Literal, Protocol, Self" if style.ramps else "Protocol, Self"
    lines: list[str] = [
        f'"""Auto-generated typed palette stub for StylePack {style.id!r}."""',
        "",
        "from __future__ import annotations",
        "",
        "from collections.abc import Iterator, Mapping",
        f"from typing import {typing_imports}",
        "",
        "",
        f"class {class_name}(Protocol):",
        f'    """Static palette token contract for `{style.id}`."""',
        "",
        "    @property",
        "    def style_id(self) -> str: ...",
        "",
    ]

    emitted: set[str] = set()
    for entry in style.palette:
        emitted.add(entry.name)
        lines.extend(
            [
                "    @property",
                f"    def {entry.name}(self) -> int: ...",
                "",
            ]
        )

    for alias_name in style.aliases:
        if alias_name in emitted:
            continue
        emitted.add(alias_name)
        lines.extend(
            [
                "    @property",
                f"    def {alias_name}(self) -> int: ...",
                "",
            ]
        )

    ramp_lines: list[str]
    if style.ramps:
        literal_items = [f'"{name}"' for name in style.ramps]
        single_line = (
            f"    def ramp(self, name: Literal[{', '.join(literal_items)}]) -> tuple[int, ...]: ..."
        )
        if len(single_line) <= 100:
            ramp_lines = [single_line]
        else:
            ramp_lines = [
                "    def ramp(",
                "        self,",
                "        name: Literal[",
                *[f"            {item}," for item in literal_items],
                "        ],",
                "    ) -> tuple[int, ...]: ...",
            ]
    else:
        ramp_lines = ["    def ramp(self, name: str) -> tuple[int, ...]: ..."]

    lines.extend(
        [
            "    @property",
            "    def ramps(self) -> dict[str, tuple[int, ...]]: ...",
            "",
            *ramp_lines,
            "",
            "    def __getitem__(self, name: str) -> int: ...",
            "",
            "    def __contains__(self, name: object) -> bool: ...",
            "",
            "    def __len__(self) -> int: ...",
            "",
            "    def __iter__(self) -> Iterator[str]: ...",
            "",
            "    def with_overrides(",
            "        self,",
            "        overrides: Mapping[str, str | int] | None = None,",
            "        /,",
            "        **kw_overrides: str | int,",
            "    ) -> Self: ...",
            "",
            "    def to_dict(self) -> dict[str, int]: ...",
            "",
        ]
    )
    return "\n".join(lines)


def write_palette_stub(style_path: Path, style: StylePack) -> Path:
    """Write the generated typed palette stub next to `style_path` and return its path."""
    target = palette_stub_path(style_path)
    target.write_text(generate_palette_stub(style), encoding="utf-8")
    return target
