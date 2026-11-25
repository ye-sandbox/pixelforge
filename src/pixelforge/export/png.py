"""Headless PNG, indexed texture, 1D LUT, GIF, and APNG encoding backed by Pillow."""

from __future__ import annotations

import io
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from pixelforge.core.palette import build_rgba_lut
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import MAX_PALETTE_INDEX, TRANSPARENT_INDEX, StylePack


def assert_binary_alpha(rgba: NDArray[np.uint8]) -> None:
    """Verify an `(H, W, 4)` uint8 RGBA array contains strictly binary alpha (`0` or `255`)."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        msg = f"Expected (H, W, 4) RGBA array, got shape {rgba.shape}"
        raise ValueError(msg)
    alpha = rgba[:, :, 3]
    if not bool(np.all((alpha == 0) | (alpha == 255))):
        msg = "RGBA buffer violates binary alpha invariant (alpha must be 0 or 255)"
        raise ValueError(msg)


def _validate_scale(scale: int) -> int:
    s = int(scale)
    if s < 1:
        msg = f"Export scale must be >= 1, got {scale}"
        raise ValueError(msg)
    return s


def _upscale_nearest(rgba: NDArray[np.uint8], scale: int) -> NDArray[np.uint8]:
    if scale == 1:
        return rgba
    return np.repeat(np.repeat(rgba, scale, axis=0), scale, axis=1)


def surface_to_rgba(
    surface: IndexedSurface,
    style: StylePack,
    *,
    variant: str | None = None,
    scale: int = 1,
    emissive_only: bool = False,
) -> NDArray[np.uint8]:
    """Convert an `IndexedSurface` into a binary-alpha `(H, W, 4)` uint8 RGBA array."""
    s = _validate_scale(scale)
    lut = build_rgba_lut(style, variant)

    if emissive_only:
        emissive_indices = {entry.index for entry in style.palette if "emissive" in entry.flags}
        # INVARIANT: Emissive masks must drop all non-emissive pixels to transparent (alpha 0)
        # so WebGL2 bloom passes never bleed onto painted surfaces.
        masked_lut = np.zeros_like(lut)
        for idx in emissive_indices:
            masked_lut[idx] = lut[idx]
        lut = masked_lut

    rgba = lut[surface.data]
    scaled = _upscale_nearest(rgba, s)
    assert_binary_alpha(scaled)
    return scaled


def rgba_to_png(rgba: NDArray[np.uint8]) -> bytes:
    """Encode an `(H, W, 4)` uint8 RGBA buffer as deterministic lossless PNG bytes."""
    assert_binary_alpha(rgba)
    image = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    image.save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def surface_to_png(
    surface: IndexedSurface,
    style: StylePack,
    *,
    variant: str | None = None,
    scale: int = 1,
    emissive_only: bool = False,
) -> bytes:
    """Render an `IndexedSurface` directly to binary-alpha PNG bytes."""
    rgba = surface_to_rgba(
        surface,
        style,
        variant=variant,
        scale=scale,
        emissive_only=emissive_only,
    )
    return rgba_to_png(rgba)


def surface_to_indexed_rgba(
    surface: IndexedSurface,
    *,
    scale: int = 1,
) -> NDArray[np.uint8]:
    """Encode palette indices in R (`0..254`) and binary alpha in A (`0` or `255`) for shaders."""
    s = _validate_scale(scale)
    h, w = surface.height, surface.width
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    opaque = surface.data != TRANSPARENT_INDEX
    rgba[opaque, 0] = surface.data[opaque]
    rgba[opaque, 3] = 255
    scaled = _upscale_nearest(rgba, s)
    assert_binary_alpha(scaled)
    return scaled


def surface_to_indexed_png(surface: IndexedSurface, *, scale: int = 1) -> bytes:
    """Encode an `IndexedSurface` into an R-index / A-binary PNG for 1D LUT shaders."""
    return rgba_to_png(surface_to_indexed_rgba(surface, scale=scale))


def style_to_lut_rgba(
    style: StylePack,
    variants: Sequence[str | None] | None = None,
) -> NDArray[np.uint8]:
    """Build a `(N, 256, 4)` 1D LUT texture where each row maps indices `0..255` for a variant."""
    row_variants: Sequence[str | None] = (
        (None, *style.variants.keys()) if variants is None else tuple(variants)
    )
    if not row_variants:
        row_variants = (None,)

    rows = [build_rgba_lut(style, variant) for variant in row_variants]
    lut_rgba = np.stack(rows, axis=0)
    assert_binary_alpha(lut_rgba)
    return lut_rgba


def style_to_lut_png(
    style: StylePack,
    variants: Sequence[str | None] | None = None,
) -> bytes:
    """Encode a `256 x N` 1D LUT PNG for WebGL2 runtime palette swaps."""
    return rgba_to_png(style_to_lut_rgba(style, variants))


def decode_png_to_rgba(png_bytes: bytes) -> NDArray[np.uint8]:
    """Decode PNG bytes into a contiguous `(H, W, 4)` uint8 RGBA numpy array."""
    with Image.open(io.BytesIO(png_bytes)) as img:
        rgba = img.convert("RGBA")
        return np.asarray(rgba, dtype=np.uint8).copy()


def _rgba_to_exact_gif_frame(rgba: NDArray[np.uint8]) -> Image.Image:
    """Convert RGBA to exact 256-color `P` frame with index 255 reserved for alpha 0."""
    assert_binary_alpha(rgba)
    h, w, _ = rgba.shape
    opaque_mask = rgba[:, :, 3] == 255
    opaque_rgb = rgba[opaque_mask, :3]

    if len(opaque_rgb) == 0:
        indices = np.full((h, w), TRANSPARENT_INDEX, dtype=np.uint8)
        frame_img = Image.fromarray(indices, mode="P")
        flat_palette = [0] * (256 * 3)
        frame_img.putpalette(flat_palette)
        frame_img.info["transparency"] = TRANSPARENT_INDEX
        return frame_img

    packed = (
        (opaque_rgb[:, 0].astype(np.uint32) << 16)
        | (opaque_rgb[:, 1].astype(np.uint32) << 8)
        | opaque_rgb[:, 2].astype(np.uint32)
    )
    unique_packed, inverse = np.unique(packed, return_inverse=True)

    if len(unique_packed) <= MAX_PALETTE_INDEX + 1:
        indices = np.full((h, w), TRANSPARENT_INDEX, dtype=np.uint8)
        indices[opaque_mask] = inverse.astype(np.uint8)
        flat_palette = [0] * (256 * 3)
        for slot, color_u32 in enumerate(unique_packed.tolist()):
            base = slot * 3
            flat_palette[base] = (color_u32 >> 16) & 0xFF
            flat_palette[base + 1] = (color_u32 >> 8) & 0xFF
            flat_palette[base + 2] = color_u32 & 0xFF
        frame_img = Image.fromarray(indices, mode="P")
        frame_img.putpalette(flat_palette)
        frame_img.info["transparency"] = TRANSPARENT_INDEX
        return frame_img

    # Fallback when >255 distinct colors appear across scaled/composited frames.
    quantized = Image.fromarray(rgba[:, :, :3], mode="RGB").quantize(
        colors=MAX_PALETTE_INDEX,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    q_arr = np.asarray(quantized, dtype=np.uint8).copy()
    q_arr[~opaque_mask] = TRANSPARENT_INDEX
    palette_data = quantized.getpalette() or [0] * (256 * 3)
    if len(palette_data) < 256 * 3:
        palette_data = [*palette_data, *([0] * (256 * 3 - len(palette_data)))]
    palette_data[TRANSPARENT_INDEX * 3 : TRANSPARENT_INDEX * 3 + 3] = [0, 0, 0]
    frame_img = Image.fromarray(q_arr, mode="P")
    frame_img.putpalette(palette_data[: 256 * 3])
    frame_img.info["transparency"] = TRANSPARENT_INDEX
    return frame_img


def _frame_duration_ms(fps: int) -> int:
    if fps < 1:
        msg = f"fps must be >= 1, got {fps}"
        raise ValueError(msg)
    return max(10, round(1000 / fps))


def frames_to_gif(
    frames: Sequence[NDArray[np.uint8]],
    *,
    fps: int = 6,
    loop: int = 0,
) -> bytes:
    """Encode a sequence of binary-alpha RGBA frames into a looping nearest-neighbor GIF."""
    if not frames:
        msg = "frames_to_gif requires at least one frame"
        raise ValueError(msg)
    duration_ms = _frame_duration_ms(fps)
    pil_frames = [_rgba_to_exact_gif_frame(frame) for frame in frames]
    buf = io.BytesIO()
    pil_frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=pil_frames[1:],
        duration=duration_ms,
        loop=loop,
        disposal=2,
        transparency=TRANSPARENT_INDEX,
    )
    return buf.getvalue()


def frames_to_apng(
    frames: Sequence[NDArray[np.uint8]],
    *,
    fps: int = 6,
    loop: int = 0,
) -> bytes:
    """Encode a sequence of binary-alpha RGBA frames into a looping lossless APNG."""
    if not frames:
        msg = "frames_to_apng requires at least one frame"
        raise ValueError(msg)
    duration_ms = _frame_duration_ms(fps)
    pil_frames: list[Image.Image] = []
    for frame in frames:
        assert_binary_alpha(frame)
        pil_frames.append(Image.fromarray(frame, mode="RGBA"))
    buf = io.BytesIO()
    pil_frames[0].save(
        buf,
        format="PNG",
        save_all=True,
        append_images=pil_frames[1:],
        duration=duration_ms,
        loop=loop,
        disposal=1,
    )
    return buf.getvalue()
