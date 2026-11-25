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
