"""Environment-backed CLI configuration using `pydantic-settings`."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    default_style: str = "homelab-16bit"


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
