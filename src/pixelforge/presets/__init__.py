"""Built-in `.style.py` preset catalog for `pixelforge init` and `pixelforge inspect`."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pixelforge.core.types import StylePack
from pixelforge.guard.runner import load_style_module

DEFAULT_INIT_PRESET: Final[str] = "sweetie-16"

_PRESET_FILENAMES: Final[dict[str, str]] = {
    "ink-1bit": "ink_1bit.style.py",
    "retro-pocket-4": "retro_pocket_4.style.py",
    "sweetie-16": "sweetie_16.style.py",
    "endesga-32": "endesga_32.style.py",
    "cozy-pastel": "cozy_pastel.style.py",
    "scifi-neon": "scifi_neon.style.py",
    "topdown-rpg": "topdown_rpg.style.py",
    "homelab-16bit": "homelab_16bit.style.py",
}

PRESET_IDS: Final[tuple[str, ...]] = tuple(_PRESET_FILENAMES)
_PRESETS_DIR: Final[Path] = Path(__file__).resolve().parent


def is_builtin_preset(preset_id: str) -> bool:
    """Return `True` when `preset_id` names a built-in `.style.py` preset."""
    return preset_id in _PRESET_FILENAMES


def get_preset_path(preset_id: str) -> Path:
    """Return the filesystem path to the built-in `.style.py` preset."""
    filename = _PRESET_FILENAMES.get(preset_id)
    if filename is None:
        available = ", ".join(PRESET_IDS)
        msg = f"Unknown built-in preset {preset_id!r}; available: {available}"
        raise KeyError(msg)
    return _PRESETS_DIR / filename


def read_preset_source(preset_id: str) -> str:
    """Read the raw `.style.py` source for `preset_id`."""
    return get_preset_path(preset_id).read_text(encoding="utf-8")


def load_preset_style(preset_id: str) -> StylePack:
    """Load and validate a built-in `StylePack` preset."""
    return load_style_module(get_preset_path(preset_id))


def load_all_presets() -> dict[str, StylePack]:
    """Load all built-in `StylePack` presets keyed by `style.id`."""
    return {preset_id: load_preset_style(preset_id) for preset_id in PRESET_IDS}


__all__ = [
    "DEFAULT_INIT_PRESET",
    "PRESET_IDS",
    "get_preset_path",
    "is_builtin_preset",
    "load_all_presets",
    "load_preset_style",
    "read_preset_source",
]
