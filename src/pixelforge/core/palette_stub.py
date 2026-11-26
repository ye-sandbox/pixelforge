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
    lines: list[str] = [
        f'"""Auto-generated typed palette stub for StylePack {style.id!r}."""',
        "",
        "from __future__ import annotations",
        "",
        "from collections.abc import Iterator, Mapping",
        "from typing import Protocol, Self",
        "",
        "",
        f"class {class_name}(Protocol):",
        f'    """Static palette token contract for `{style.id}`."""',
        "",
        "    @property",
        "    def style_id(self) -> str: ...",
        "",
    ]

    for entry in style.palette:
        lines.extend(
            [
                "    @property",
                f"    def {entry.name}(self) -> int: ...",
                "",
            ]
        )

    lines.extend(
        [
            "    def __getitem__(self, name: str) -> int: ...",
            "",
            "    def __contains__(self, name: object) -> bool: ...",
            "",
            "    def __len__(self) -> int: ...",
            "",
            "    def __iter__(self) -> Iterator[str]: ...",
            "",
            "    def with_overrides(self, overrides: Mapping[str, str | int]) -> Self: ...",
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
