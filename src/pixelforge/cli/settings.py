"""Environment-backed CLI configuration using `pydantic-settings`."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pixelforge.core.types import StylePack


class PixelforgeSettings(BaseSettings):
    """Runtime defaults loaded from environment variables and optional `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="PIXELFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    out_dir: Path = Path("dist")
    sheets_dir: Path = Path(".pixelforge/sheets")
    previews_dir: Path = Path(".pixelforge/previews")
    diffs_dir: Path = Path(".pixelforge/diffs")
    default_style: str | None = None


class HydraSettings(BaseSettings):
    """Optional `hydra-llm-router` settings for `pixelforge critic`."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = "https://hydra-router.homelab.yegear.dev/v1"
    api_key: str = ""
    model_fast: str = "fast"
    model_deep: str = "deep"
    model_dev: str | None = None
    timeout_seconds: float = 120.0


def _resolve_env_file(root: Path | None) -> Path | None:
    if root is None:
        return None
    env_path = root / ".env"
    return env_path if env_path.is_file() else None


def load_pixelforge_settings(root: Path | None = None) -> PixelforgeSettings:
    """Load `PixelforgeSettings` scoped to `root / '.env'` when `root` is given."""
    if root is None:
        return PixelforgeSettings()
    # INVARIANT: Scoping `.env` to `--root` prevents CWD `.env` leakage across external repos.
    env_file = _resolve_env_file(root)

    class _ScopedPixelforgeSettings(PixelforgeSettings):
        model_config = SettingsConfigDict(
            env_prefix="PIXELFORGE_",
            env_file=env_file,
            env_file_encoding="utf-8",
            extra="ignore",
        )

    return _ScopedPixelforgeSettings()


def load_hydra_settings(root: Path | None = None) -> HydraSettings:
    """Load `HydraSettings` scoped to `root / '.env'` when `root` is given."""
    if root is None:
        return HydraSettings()
    env_file = _resolve_env_file(root)

    class _ScopedHydraSettings(HydraSettings):
        model_config = SettingsConfigDict(
            env_prefix="LLM_",
            env_file=env_file,
            env_file_encoding="utf-8",
            extra="ignore",
        )

    return _ScopedHydraSettings()


def resolve_project_style_id(
    *,
    explicit_style: str | None,
    default_style: str | None,
    styles: Mapping[str, StylePack],
    styles_dir: Path,
) -> str:
    """Resolve the active `StylePack` ID deterministically for a project."""
    available = ", ".join(sorted(styles)) or "(none)"
    if explicit_style is not None:
        if explicit_style in styles:
            return explicit_style
        msg = f"unknown style {explicit_style!r}; available in {styles_dir}: {available}"
        raise ValueError(msg)

    if default_style is not None:
        if default_style in styles:
            return default_style
        msg = f"unknown default style {default_style!r}; available in {styles_dir}: {available}"
        raise ValueError(msg)

    if len(styles) == 1:
        return next(iter(styles))

    if not styles:
        msg = (
            f"no .style.py files found in {styles_dir}; run 'pixelforge init' or pass --style <id>"
        )
        raise ValueError(msg)

    msg = (
        f"multiple styles found in {styles_dir}: {available}; "
        "pass --style <id> or set PIXELFORGE_DEFAULT_STYLE"
    )
    raise ValueError(msg)
