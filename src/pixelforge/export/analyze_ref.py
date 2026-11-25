"""Ephemeral reference image proportion and palette-quantized ASCII sketch analyzer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from pixelforge.core.palette import hex_to_rgb
from pixelforge.core.types import TRANSPARENT_INDEX, PaletteColor, StylePack

_ASCII_SYMBOLS = "#@%*=+:-~^!&?$0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_TRANSPARENT_CHAR = "."
_MAX_SKETCH_DIM = 128


@dataclass(frozen=True)
class PaletteTokenCount:
    """Histogram entry for a quantized `StylePack` palette token."""

    token: str
    index: int
    hex: str
    pixels: int
    percentage: float


@dataclass(frozen=True)
class ReferenceAnalysis:
    """Ephemeral proportion, palette histogram, and ASCII sketch of a reference image."""

    source_width: int
    source_height: int
    aspect_ratio: float
    simplified_ratio: str
    target_width: int
    target_height: int
    style_id: str
    histogram: tuple[PaletteTokenCount, ...]
    legend: dict[str, str]
    ascii_sketch: tuple[str, ...]

    def format_report(self) -> str:
        """Format the ephemeral analysis as human- and agent-readable text."""
        lines = [
            "# EPHEMERAL REFERENCE SKETCH — DO NOT IMPORT INTO assets/ OR COMMIT TO GIT",
            f"style: {self.style_id}",
            (
                f"source: {self.source_width}x{self.source_height} "
                f"(ratio {self.aspect_ratio:.4f}, {self.simplified_ratio})"
            ),
            f"sketch: {self.target_width}x{self.target_height}",
            "",
            "palette_histogram:",
        ]
        sym_by_token = {token: sym for sym, token in self.legend.items()}
        for entry in self.histogram:
            sym = sym_by_token.get(entry.token, "?")
            lines.append(
                f"  [{sym}] {entry.token:<20} {entry.hex}  "
                f"{entry.pixels:>5} px ({entry.percentage:5.1f}%)"
            )
        if not self.histogram:
            lines.append("  (no opaque pixels)")
        lines.append("")
        lines.append("ascii_sketch:")
        lines.extend(self.ascii_sketch)
        return "\n".join(lines)


def parse_sketch_size(raw: str) -> tuple[int, int]:
    """Parse a `WxH` sketch dimension string into `(width, height)`."""
    parts = raw.lower().split("x")
    if len(parts) != 2:
        msg = f"Invalid --size {raw!r}; expected WxH (e.g. 32x32 or 64x64)"
        raise ValueError(msg)
    try:
        width = int(parts[0].strip())
        height = int(parts[1].strip())
    except ValueError as exc:
        msg = f"Invalid --size {raw!r}; width and height must be integers"
        raise ValueError(msg) from exc
    _validate_sketch_size(width, height)
    return width, height


def _validate_sketch_size(width: int, height: int) -> None:
    if width < 1 or height < 1 or width > _MAX_SKETCH_DIM or height > _MAX_SKETCH_DIM:
        msg = (
            f"Sketch size {width}x{height} out of bounds; "
            f"dimensions must be between 1 and {_MAX_SKETCH_DIM}"
        )
        raise ValueError(msg)


def _open_reference_image(source: Path | BinaryIO | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGBA")
    with Image.open(source) as img:
        return img.convert("RGBA")


def _quantize_to_style(
    rgba: NDArray[np.uint8],
    palette: tuple[PaletteColor, ...],
) -> NDArray[np.uint8]:
    """Map an `(H, W, 4)` RGBA array to `StylePack` palette indices (`255` = transparent)."""
    height, width, _ = rgba.shape
    out = np.full((height, width), TRANSPARENT_INDEX, dtype=np.uint8)
    opaque_mask = rgba[:, :, 3] >= 128
    if not np.any(opaque_mask):
        return out

    if not palette:
        msg = "StylePack palette must contain at least one color"
        raise ValueError(msg)

    pal_indices = np.array([c.index for c in palette], dtype=np.uint8)
    pal_rgb = np.array([hex_to_rgb(c.hex) for c in palette], dtype=np.int32)

    opaque_rgb = rgba[opaque_mask, :3].astype(np.int32)
    # INVARIANT: Squared Euclidean RGB distance is deterministic and avoids floating-point
    # tie-breaking drift across platforms.
    diffs = opaque_rgb[:, None, :] - pal_rgb[None, :, :]
    sq_dist = np.sum(diffs * diffs, axis=2)
    nearest_pos = np.argmin(sq_dist, axis=1)
    out[opaque_mask] = pal_indices[nearest_pos]
    return out


def analyze_reference_image(
    path: Path | BinaryIO | Image.Image,
    style: StylePack,
    size: tuple[int, int] = (32, 32),
) -> ReferenceAnalysis:
    """Analyze a local reference image into proportions, palette histogram, and ASCII sketch."""
    target_w, target_h = size
    _validate_sketch_size(target_w, target_h)

    rgba_img = _open_reference_image(path)
    src_w, src_h = rgba_img.size
    if src_w < 1 or src_h < 1:
        msg = f"Reference image has invalid dimensions: {src_w}x{src_h}"
        raise ValueError(msg)

    divisor = math.gcd(src_w, src_h)
    simplified_ratio = f"{src_w // divisor}:{src_h // divisor}"
    aspect_ratio = round(src_w / src_h, 4)

    resized = rgba_img.resize((target_w, target_h), Image.Resampling.BILINEAR)
    rgba_arr = np.asarray(resized, dtype=np.uint8)
    index_grid = _quantize_to_style(rgba_arr, style.palette)

    by_index = {c.index: c for c in style.palette}
    unique_vals, counts = np.unique(index_grid, return_counts=True)

    raw_counts: list[tuple[int, int]] = [
        (int(val), int(cnt))
        for val, cnt in zip(unique_vals, counts, strict=True)
        if int(val) != TRANSPARENT_INDEX
    ]
    raw_counts.sort(key=lambda item: (-item[1], item[0]))
    opaque_total = sum(cnt for _, cnt in raw_counts)

    histogram: list[PaletteTokenCount] = []
    legend: dict[str, str] = {}
    char_by_index: dict[int, str] = {TRANSPARENT_INDEX: _TRANSPARENT_CHAR}

    for rank, (pal_idx, pixel_count) in enumerate(raw_counts):
        color = by_index[pal_idx]
        pct = (pixel_count / opaque_total * 100.0) if opaque_total > 0 else 0.0
        histogram.append(
            PaletteTokenCount(
                token=color.name,
                index=color.index,
                hex=color.hex,
                pixels=pixel_count,
                percentage=round(pct, 2),
            )
        )
        sym = _ASCII_SYMBOLS[rank] if rank < len(_ASCII_SYMBOLS) else "?"
        legend[sym] = color.name
        char_by_index[pal_idx] = sym

    sketch_rows = tuple("".join(char_by_index[int(idx)] for idx in row) for row in index_grid)

    return ReferenceAnalysis(
        source_width=src_w,
        source_height=src_h,
        aspect_ratio=aspect_ratio,
        simplified_ratio=simplified_ratio,
        target_width=target_w,
        target_height=target_h,
        style_id=style.id,
        histogram=tuple(histogram),
        legend=legend,
        ascii_sketch=sketch_rows,
    )
