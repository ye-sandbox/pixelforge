"""Environment-backed and TOML project build-profile CLI configuration."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from pixelforge.export.atlas import AtlasFormat

if TYPE_CHECKING:
    from pixelforge.core.types import StylePack

BuildTarget = Literal[
    "png",
    "emissive",
    "lut",
    "normals",
    "height",
    "indexed-ts",
    "indexed-ts-lazy",
    "ui-css",
    "atlas",
    "aseprite",
    "texturepacker",
    "sheet",
    "animate",
]


class BuildProfile(BaseModel):
    """Declarative build-profile settings in `pixelforge.toml` or `[tool.pixelforge]`."""

    model_config = ConfigDict(extra="forbid")

    style: str | None = None
    out: str | None = None
    targets: list[BuildTarget] | None = None
    variant: str | None = None
    scale: int | None = Field(default=None, ge=1)
    emissive: bool | None = None
    indexed_ts: bool | None = None
    ui_css: bool | None = None
    atlas: AtlasFormat | None = None


class PixelforgeProjectConfig(BuildProfile):
    """Root TOML configuration with top-level defaults and named `[profiles.*]`."""

    model_config = ConfigDict(extra="forbid")

    profiles: dict[str, BuildProfile] = Field(default_factory=dict)


class ResolvedBuildProfile(BaseModel):
    """Effective build configuration after merging preset, TOML, and profile layers."""

    model_config = ConfigDict(extra="forbid")

    profile_name: str
    style: str | None = None
    out: str | None = None
    targets: tuple[BuildTarget, ...] = ()
    variant: str | None = None
    scale: int = 1
    emissive: bool | None = None
    lut: bool = False
    normals: bool = False
    height: bool = False
    indexed_ts: bool = False
    indexed_ts_lazy: bool = False
    ui_css: bool = False
    atlas: AtlasFormat | None = None
    sheet: bool = False
    animate: bool = False


BUILTIN_BUILD_PROFILES: dict[str, BuildProfile] = {
    "default": BuildProfile(),
    "web-ui": BuildProfile(
        targets=["png", "ui-css"],
        ui_css=True,
        indexed_ts=False,
    ),
    "framebuffer-ui": BuildProfile(
        targets=["indexed-ts"],
        indexed_ts=True,
        ui_css=False,
    ),
}


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


def load_project_config(root: Path) -> tuple[PixelforgeProjectConfig, Path | None]:
    """Load `pixelforge.toml` or `[tool.pixelforge]` in `pyproject.toml` under `root`."""
    pixelforge_toml = root / "pixelforge.toml"
    if pixelforge_toml.is_file():
        cfg = _parse_project_config_file(pixelforge_toml, nested_tool=False)
        if cfg is not None:
            return cfg, pixelforge_toml

    pyproject_toml = root / "pyproject.toml"
    if pyproject_toml.is_file():
        cfg = _parse_project_config_file(pyproject_toml, nested_tool=True)
        if cfg is not None:
            return cfg, pyproject_toml

    return PixelforgeProjectConfig(), None


def _parse_project_config_file(
    path: Path,
    *,
    nested_tool: bool,
) -> PixelforgeProjectConfig | None:
    try:
        raw_doc: Mapping[str, object] = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        msg = f"invalid TOML in {path}: {exc}"
        raise ValueError(msg) from exc

    raw_section: object
    if nested_tool:
        tool_table = raw_doc.get("tool")
        if not isinstance(tool_table, Mapping):
            return None
        tool_map = cast("Mapping[str, object]", tool_table)
        if "pixelforge" not in tool_map:
            return None
        raw_section = tool_map["pixelforge"]
    else:
        raw_section = raw_doc

    if not isinstance(raw_section, Mapping):
        msg = f"invalid pixelforge config in {path}: expected a TOML table"
        raise ValueError(msg)

    try:
        return PixelforgeProjectConfig.model_validate(raw_section)
    except ValidationError as exc:
        msg = f"invalid pixelforge config in {path}: {exc}"
        raise ValueError(msg) from exc


def _merge_profile_fields(base: BuildProfile, overlay: BuildProfile) -> BuildProfile:
    updates = {
        field_name: getattr(overlay, field_name)
        for field_name in BuildProfile.model_fields
        if getattr(overlay, field_name) is not None
    }
    return base.model_copy(update=updates)


def _resolve_atlas_from_targets(
    explicit_atlas: AtlasFormat | None,
    target_set: set[BuildTarget],
) -> AtlasFormat | None:
    if explicit_atlas is not None:
        return explicit_atlas
    if "atlas" in target_set or ("aseprite" in target_set and "texturepacker" in target_set):
        return "all"
    if "aseprite" in target_set:
        return "aseprite"
    if "texturepacker" in target_set:
        return "texturepacker"
    return None


def resolve_build_profile(root: Path, profile_name: str | None = None) -> ResolvedBuildProfile:
    """Resolve the active build profile by merging top-level TOML, built-ins, and named profile."""
    config, _ = load_project_config(root)
    selected_name = profile_name or "default"

    if selected_name not in BUILTIN_BUILD_PROFILES and selected_name not in config.profiles:
        available = ", ".join(sorted({*BUILTIN_BUILD_PROFILES, *config.profiles}))
        msg = f"unknown build profile {selected_name!r}; available: {available}"
        raise ValueError(msg)

    top_level = BuildProfile(
        style=config.style,
        out=config.out,
        targets=config.targets,
        variant=config.variant,
        scale=config.scale,
        emissive=config.emissive,
        indexed_ts=config.indexed_ts,
        ui_css=config.ui_css,
        atlas=config.atlas,
    )
    merged = top_level
    if selected_name in BUILTIN_BUILD_PROFILES:
        merged = _merge_profile_fields(merged, BUILTIN_BUILD_PROFILES[selected_name])
    if selected_name in config.profiles:
        merged = _merge_profile_fields(merged, config.profiles[selected_name])

    targets = tuple(merged.targets or ())
    target_set = set(targets)
    indexed_ts_lazy = "indexed-ts-lazy" in target_set
    indexed_ts = (
        merged.indexed_ts
        if merged.indexed_ts is not None
        else ("indexed-ts" in target_set or indexed_ts_lazy)
    )
    ui_css = merged.ui_css if merged.ui_css is not None else ("ui-css" in target_set)
    emissive = (
        merged.emissive
        if merged.emissive is not None
        else (True if "emissive" in target_set else None)
    )

    return ResolvedBuildProfile(
        profile_name=selected_name,
        style=merged.style,
        out=merged.out,
        targets=targets,
        variant=merged.variant,
        scale=merged.scale if merged.scale is not None else 1,
        emissive=emissive,
        lut="lut" in target_set,
        normals="normals" in target_set,
        height="height" in target_set,
        indexed_ts=indexed_ts,
        indexed_ts_lazy=indexed_ts_lazy,
        ui_css=ui_css,
        atlas=_resolve_atlas_from_targets(merged.atlas, target_set),
        sheet="sheet" in target_set,
        animate="animate" in target_set,
    )
