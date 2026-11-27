"""AST static and runtime guard suite for pixel determinism and palette closure."""

from pixelforge.guard.ast_rules import GuardScope, check_ast_file, check_ast_source, infer_scope
from pixelforge.guard.craft_rules import CRAFT_RULE_NAMES, check_asset_craft
from pixelforge.guard.runner import (
    CheckReport,
    discover_asset_files,
    discover_style_files,
    load_all_assets,
    load_all_styles,
    load_asset_from_git,
    load_asset_module,
    load_style_from_git,
    load_style_module,
    read_git_file,
    run_checks,
)
from pixelforge.guard.runtime_rules import check_asset_runtime, find_orphan_pixel_coords
from pixelforge.guard.scene_rules import check_scene_runtime
from pixelforge.guard.types import GuardSeverity, GuardViolation

__all__ = [
    "CRAFT_RULE_NAMES",
    "CheckReport",
    "GuardScope",
    "GuardSeverity",
    "GuardViolation",
    "check_asset_craft",
    "check_asset_runtime",
    "check_ast_file",
    "check_ast_source",
    "check_scene_runtime",
    "discover_asset_files",
    "discover_style_files",
    "find_orphan_pixel_coords",
    "infer_scope",
    "load_all_assets",
    "load_all_styles",
    "load_asset_from_git",
    "load_asset_module",
    "load_style_from_git",
    "load_style_module",
    "read_git_file",
    "run_checks",
]
