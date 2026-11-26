"""Module discovery, git-ref asset loading, and unified guard runner."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import cast

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, StylePack
from pixelforge.export.bundle import LoadedAsset
from pixelforge.export.scene import (
    LoadedScene,
    SceneCompositionError,
    SceneSpec,
    compose_scene_frames,
)
from pixelforge.guard.ast_rules import check_ast_file
from pixelforge.guard.runtime_rules import check_asset_runtime
from pixelforge.guard.types import GuardViolation


@dataclass(frozen=True)
class CheckReport:
    """Aggregated AST + runtime guard result."""

    violations: tuple[GuardViolation, ...]
    assets_checked: int
    styles_checked: int
    errors: int
    warnings: int

    @property
    def passed(self) -> bool:
        """Return `True` when zero error-severity violations occurred."""
        return self.errors == 0


def discover_style_files(styles_dir: Path) -> list[Path]:
    """Return sorted `*.style.py` files under `styles_dir`."""
    if not styles_dir.is_dir():
        return []
    return sorted(styles_dir.rglob("*.style.py"))


def discover_asset_files(assets_dir: Path) -> list[Path]:
    """Return sorted `*.asset.py` files under `assets_dir`."""
    if not assets_dir.is_dir():
        return []
    return sorted(assets_dir.rglob("*.asset.py"))


def discover_scene_files(assets_dir: Path) -> list[Path]:
    """Return sorted `*.scene.py` files under `assets_dir`."""
    if not assets_dir.is_dir():
        return []
    return sorted(assets_dir.rglob("*.scene.py"))


def _exec_module_from_path(path: Path) -> ModuleType:
    module_name = f"_pixelforge_dyn_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        msg = f"Cannot create module spec for {path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exec_module_from_source(source: str, filename: str) -> ModuleType:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / Path(filename).name
        tmp_path.write_text(source, encoding="utf-8")
        return _exec_module_from_path(tmp_path)


def _extract_style(module: ModuleType, origin: str) -> StylePack:
    style = getattr(module, "STYLE", None)
    if not isinstance(style, StylePack):
        msg = f"Style module {origin} must export `STYLE: StylePack`"
        raise TypeError(msg)
    return style


def _extract_asset(module: ModuleType, origin: str) -> LoadedAsset:
    spec = getattr(module, "SPEC", None)
    render_fn = getattr(module, "render", None)
    if not isinstance(spec, AssetSpec):
        msg = f"Asset module {origin} must export `SPEC: AssetSpec`"
        raise TypeError(msg)
    if not callable(render_fn):
        msg = f"Asset module {origin} must export callable `render(a: Asset) -> None`"
        raise TypeError(msg)
    typed_render = cast(Callable[[Asset], None], render_fn)
    return LoadedAsset(SPEC=spec, render=typed_render)


def _extract_scene(module: ModuleType, origin: str) -> LoadedScene:
    scene = getattr(module, "SCENE", None)
    if not isinstance(scene, SceneSpec):
        msg = f"Scene module {origin} must export `SCENE: SceneSpec`"
        raise TypeError(msg)
    return LoadedScene(SCENE=scene)


def load_style_module(path: Path) -> StylePack:
    """Load a `StylePack` from a `*.style.py` file."""
    return _extract_style(_exec_module_from_path(path), str(path))


def load_asset_module(path: Path) -> LoadedAsset:
    """Load a `LoadedAsset` (`SPEC` + `render`) from a `*.asset.py` file."""
    return _extract_asset(_exec_module_from_path(path), str(path))


def load_scene_module(path: Path) -> LoadedScene:
    """Load a `LoadedScene` (`SCENE: SceneSpec`) from a `*.scene.py` file."""
    return _extract_scene(_exec_module_from_path(path), str(path))


def read_git_file(repo_root: Path, file_path: Path, ref: str = "HEAD") -> str | None:
    """Read file contents at `ref` via `git show`, returning `None` if absent at `ref`."""
    if not ref or ref.startswith("-"):
        msg = f"Invalid git ref {ref!r}"
        raise ValueError(msg)

    git_bin = shutil.which("git")
    if git_bin is None:
        msg = "git executable not found on PATH"
        raise RuntimeError(msg)

    try:
        rel_path = file_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        rel_path = file_path.as_posix()

    proc = subprocess.run(
        [git_bin, "-C", str(repo_root), "show", f"{ref}:{rel_path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def load_asset_from_git(
    repo_root: Path,
    asset_path: Path,
    ref: str = "HEAD",
) -> LoadedAsset | None:
    """Load an `.asset.py` module from a historical git revision."""
    source = read_git_file(repo_root, asset_path, ref=ref)
    if source is None:
        return None
    module = _exec_module_from_source(source, f"{ref}:{asset_path.as_posix()}")
    return _extract_asset(module, f"{ref}:{asset_path.as_posix()}")


def load_style_from_git(
    repo_root: Path,
    style_path: Path,
    ref: str = "HEAD",
) -> StylePack | None:
    """Load a `.style.py` module from a historical git revision."""
    source = read_git_file(repo_root, style_path, ref=ref)
    if source is None:
        return None
    module = _exec_module_from_source(source, f"{ref}:{style_path.as_posix()}")
    return _extract_style(module, f"{ref}:{style_path.as_posix()}")


def load_all_styles(styles_dir: Path) -> dict[str, StylePack]:
    """Discover and load all `*.style.py` packs indexed by `StylePack.id`."""
    styles: dict[str, StylePack] = {}
    seen_paths: dict[str, Path] = {}
    for style_path in discover_style_files(styles_dir):
        pack = load_style_module(style_path)
        if pack.id in seen_paths:
            msg = (
                f"Duplicate style ID {pack.id!r} in {style_path} "
                f"(already declared in {seen_paths[pack.id]})"
            )
            raise ValueError(msg)
        seen_paths[pack.id] = style_path
        styles[pack.id] = pack
    return styles


def load_all_assets(assets_dir: Path) -> dict[str, LoadedAsset]:
    """Discover and load all `*.asset.py` modules indexed by `AssetSpec.id`."""
    assets: dict[str, LoadedAsset] = {}
    seen_paths: dict[str, Path] = {}
    for asset_path in discover_asset_files(assets_dir):
        loaded = load_asset_module(asset_path)
        if loaded.SPEC.id in seen_paths:
            msg = (
                f"Duplicate asset ID {loaded.SPEC.id!r} in {asset_path} "
                f"(already declared in {seen_paths[loaded.SPEC.id]})"
            )
            raise ValueError(msg)
        seen_paths[loaded.SPEC.id] = asset_path
        assets[loaded.SPEC.id] = loaded
    return assets


def run_checks(
    root: Path,
    *,
    asset_id: str | None = None,
    asset_paths: Collection[Path] | None = None,
    strict_orphans: bool = False,
) -> CheckReport:
    """Run AST static guards and runtime invariant checks across the project."""
    violations: list[GuardViolation] = []
    target_paths = {p.resolve() for p in asset_paths} if asset_paths is not None else None

    core_dir = root / "src" / "pixelforge" / "core"
    if core_dir.is_dir():
        for core_file in sorted(core_dir.rglob("*.py")):
            violations.extend(check_ast_file(core_file, scope="core"))

    style_files = discover_style_files(root / "styles")
    styles: dict[str, StylePack] = {}
    style_origins: dict[str, Path] = {}
    for style_path in style_files:
        ast_issues = check_ast_file(style_path, scope="style")
        violations.extend(ast_issues)
        if not ast_issues:
            try:
                pack = load_style_module(style_path)
            except Exception as exc:
                violations.append(
                    GuardViolation(
                        file=str(style_path),
                        line=1,
                        col=0,
                        rule="load-error",
                        detail=str(exc),
                    )
                )
                continue

            if pack.id in style_origins:
                violations.append(
                    GuardViolation(
                        file=str(style_path),
                        line=1,
                        col=0,
                        rule="duplicate-id",
                        detail=(
                            f"Duplicate style ID {pack.id!r} "
                            f"(already declared in {style_origins[pack.id]})"
                        ),
                    )
                )
                continue
            style_origins[pack.id] = style_path
            styles[pack.id] = pack

    asset_files = discover_asset_files(root / "assets")
    asset_origins: dict[str, Path] = {}
    loaded_assets_by_id: dict[str, LoadedAsset] = {}
    assets_checked = 0
    for asset_path in asset_files:
        in_target_paths = target_paths is None or asset_path.resolve() in target_paths
        ast_issues = check_ast_file(asset_path, scope="asset")
        if ast_issues:
            if in_target_paths and (
                asset_id is None or asset_path.stem.removesuffix(".asset") == asset_id
            ):
                violations.extend(ast_issues)
                assets_checked += 1
            continue

        try:
            loaded = load_asset_module(asset_path)
        except Exception as exc:
            if in_target_paths and (
                asset_id is None or asset_path.stem.removesuffix(".asset") == asset_id
            ):
                violations.append(
                    GuardViolation(
                        file=str(asset_path),
                        line=1,
                        col=0,
                        rule="load-error",
                        detail=str(exc),
                    )
                )
                assets_checked += 1
            continue

        if loaded.SPEC.id in asset_origins:
            if in_target_paths and (asset_id is None or loaded.SPEC.id == asset_id):
                violations.append(
                    GuardViolation(
                        file=str(asset_path),
                        line=1,
                        col=0,
                        rule="duplicate-id",
                        detail=(
                            f"Duplicate asset ID {loaded.SPEC.id!r} "
                            f"(already declared in {asset_origins[loaded.SPEC.id]})"
                        ),
                    )
                )
                assets_checked += 1
            continue
        asset_origins[loaded.SPEC.id] = asset_path
        loaded_assets_by_id[loaded.SPEC.id] = loaded

        if not in_target_paths:
            continue
        if asset_id is not None and loaded.SPEC.id != asset_id:
            continue

        assets_checked += 1
        style = styles.get(loaded.SPEC.style_id)
        if style is None:
            violations.append(
                GuardViolation(
                    file=str(asset_path),
                    line=1,
                    col=0,
                    rule="missing-style",
                    detail=f"Referenced style {loaded.SPEC.style_id!r} not found in styles/",
                )
            )
            continue

        violations.extend(
            check_asset_runtime(
                loaded,
                style,
                file_path=str(asset_path),
                strict_orphans=strict_orphans,
            )
        )

    for scene_path in discover_scene_files(root / "assets"):
        in_target_paths = target_paths is None or scene_path.resolve() in target_paths
        ast_issues = check_ast_file(scene_path, scope="asset")
        if ast_issues:
            if in_target_paths and (
                asset_id is None or scene_path.stem.removesuffix(".scene") == asset_id
            ):
                violations.extend(ast_issues)
                assets_checked += 1
            continue

        try:
            loaded_scene = load_scene_module(scene_path)
        except Exception as exc:
            if in_target_paths and (
                asset_id is None or scene_path.stem.removesuffix(".scene") == asset_id
            ):
                violations.append(
                    GuardViolation(
                        file=str(scene_path),
                        line=1,
                        col=0,
                        rule="load-error",
                        detail=str(exc),
                    )
                )
                assets_checked += 1
            continue

        scene_spec = loaded_scene.SCENE
        if scene_spec.id in asset_origins:
            if in_target_paths and (asset_id is None or scene_spec.id == asset_id):
                violations.append(
                    GuardViolation(
                        file=str(scene_path),
                        line=1,
                        col=0,
                        rule="duplicate-id",
                        detail=(
                            f"Duplicate asset ID {scene_spec.id!r} "
                            f"(already declared in {asset_origins[scene_spec.id]})"
                        ),
                    )
                )
                assets_checked += 1
            continue
        asset_origins[scene_spec.id] = scene_path

        if not in_target_paths:
            continue
        if asset_id is not None and scene_spec.id != asset_id:
            continue

        assets_checked += 1
        parent = loaded_assets_by_id.get(scene_spec.parent_id)
        if parent is None:
            violations.append(
                GuardViolation(
                    file=str(scene_path),
                    line=1,
                    col=0,
                    rule="missing-parent",
                    detail=f"Parent asset {scene_spec.parent_id!r} not found under assets/",
                )
            )
            continue

        missing_style = scene_spec.style_id or parent.SPEC.style_id
        style = styles.get(missing_style)
        if style is None:
            violations.append(
                GuardViolation(
                    file=str(scene_path),
                    line=1,
                    col=0,
                    rule="missing-style",
                    detail=f"Referenced style {missing_style!r} not found in styles/",
                )
            )
            continue

        try:
            compose_scene_frames(scene_spec, parent, loaded_assets_by_id, style)
        except SceneCompositionError as exc:
            violations.append(
                GuardViolation(
                    file=str(scene_path),
                    line=1,
                    col=0,
                    rule="scene-error",
                    detail=str(exc),
                )
            )

    if asset_id is not None and assets_checked == 0:
        violations.append(
            GuardViolation(
                file=str(root / "assets"),
                line=1,
                col=0,
                rule="asset-not-found",
                detail=f"Asset {asset_id!r} not found under assets/",
            )
        )

    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    return CheckReport(
        violations=tuple(violations),
        assets_checked=assets_checked,
        styles_checked=len(style_files),
        errors=errors,
        warnings=warnings,
    )
