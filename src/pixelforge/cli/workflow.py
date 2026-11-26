"""Backward-compatible facade re-exporting CLI subcommand workflows."""

from __future__ import annotations

from pixelforge.cli.compose_cmd import compose_scene_workflow, parse_mount_arg
from pixelforge.cli.critic_cmd import critic_workflow
from pixelforge.cli.diff_cmd import diff_asset, resolve_baseline_style
from pixelforge.cli.render_cmd import OutputFn, compile_style_indexed_bundles, render_once
from pixelforge.cli.watch_cmd import watch_loop

__all__ = [
    "OutputFn",
    "compile_style_indexed_bundles",
    "compose_scene_workflow",
    "critic_workflow",
    "diff_asset",
    "parse_mount_arg",
    "render_once",
    "resolve_baseline_style",
    "watch_loop",
]
