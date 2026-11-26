"""Hermetic unit and CLI tests for deterministic scene ergonomics guards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelforge.cli.main import main
from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, PerspectiveMode, StylePack
from pixelforge.export.bundle import LoadedAsset
from pixelforge.export.scene import SceneMountSpec, ScenePortalSpec, SceneSpec
from pixelforge.guard.scene_rules import check_scene_graph, check_scene_runtime


def _sample_style() -> StylePack:
    return StylePack(
        id="test-style",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="FILL", hex="#3b82f6", flags=("surface",)),
            PaletteColor(index=2, name="ACCENT", hex="#f59e0b", flags=("surface",)),
        ),
    )


def _make_parent(
    *,
    width: int = 32,
    height: int = 32,
    anchors: tuple[tuple[str, int, int], ...] = (("slot_a", 10, 14), ("slot_b", 20, 14)),
    empty: bool = False,
) -> LoadedAsset:
    spec = AssetSpec(
        id="parent_room",
        style_id="test-style",
        perspective="iso-2:1",
        width=width,
        height=height,
        states=("idle",),
        frames=1,
        fps=4,
    )

    def render(a: Asset) -> None:
        if not empty:
            a.rect(4, 4, width - 8, height - 8, 1)
        for name, x, y in anchors:
            a.anchor(name, x, y)

    return LoadedAsset(SPEC=spec, render=render)


def _make_prop(
    prop_id: str,
    *,
    width: int = 8,
    height: int = 8,
    fill_rect: tuple[int, int, int, int] = (1, 1, 6, 6),
    perspective: PerspectiveMode = "iso-2:1",
) -> LoadedAsset:
    spec = AssetSpec(
        id=prop_id,
        style_id="test-style",
        perspective=perspective,
        width=width,
        height=height,
        states=("idle",),
        frames=1,
        fps=4,
    )

    def render(a: Asset) -> None:
        rx, ry, rw, rh = fill_rect
        a.rect(rx, ry, rw, rh, 2)
        a.anchor("foot", width // 2, height - 1)

    return LoadedAsset(SPEC=spec, render=render)


def test_valid_scene_passes_with_minor_occlusion() -> None:
    """Valid scene with minor (<25%) isometric overlap produces zero violations."""
    style = _sample_style()
    parent = _make_parent(anchors=(("slot_a", 12, 14), ("slot_b", 12, 15)))
    prop_back = _make_prop("prop_back", width=8, height=8, fill_rect=(0, 0, 8, 8))
    prop_front = _make_prop("prop_front", width=8, height=8, fill_rect=(0, 7, 8, 1))
    scene = SceneSpec(
        id="valid_scene",
        parent_id="parent_room",
        mounts=(
            SceneMountSpec(prop_id="prop_back", anchor="slot_a", prop_anchor="foot"),
            SceneMountSpec(
                prop_id="prop_front",
                anchor="slot_b",
                prop_anchor="foot",
                offset_y=-1,
                z_index=1,
            ),
        ),
    )

    violations = check_scene_runtime(
        scene,
        parent,
        {"prop_back": prop_back, "prop_front": prop_front},
        style,
    )
    assert violations == []


def test_duplicate_mount_detected() -> None:
    """Mounting two props onto the same parent anchor triggers `duplicate-mount` error."""
    style = _sample_style()
    parent = _make_parent()
    prop_a = _make_prop("prop_a")
    prop_b = _make_prop("prop_b")
    scene = SceneSpec(
        id="dup_mount_scene",
        parent_id="parent_room",
        mounts=(
            SceneMountSpec(prop_id="prop_a", anchor="slot_a", prop_anchor="foot"),
            SceneMountSpec(prop_id="prop_b", anchor="slot_a", prop_anchor="foot", offset_x=4),
        ),
    )

    violations = check_scene_runtime(
        scene,
        parent,
        {"prop_a": prop_a, "prop_b": prop_b},
        style,
    )
    dup = [v for v in violations if v.rule == "duplicate-mount"]
    assert len(dup) == 1
    assert dup[0].severity == "error"
    assert "slot_a" in dup[0].detail


def test_anchor_outside_parent_bbox_detected() -> None:
    """Mounted parent anchor outside parent's opaque bbox triggers `scene-anchor-bounds`."""
    style = _sample_style()
    parent = _make_parent(anchors=(("outside_slot", 1, 1),))
    prop_a = _make_prop("prop_a", width=4, height=4, fill_rect=(1, 1, 2, 2))
    scene = SceneSpec(
        id="oob_anchor_scene",
        parent_id="parent_room",
        mounts=(SceneMountSpec(prop_id="prop_a", anchor="outside_slot", prop_anchor="foot"),),
    )

    violations = check_scene_runtime(scene, parent, {"prop_a": prop_a}, style)
    anchor_errs = [v for v in violations if v.rule == "scene-anchor-bounds"]
    assert len(anchor_errs) == 1
    assert anchor_errs[0].severity == "error"
    assert "outside_slot" in anchor_errs[0].detail

    empty_parent = _make_parent(anchors=(("slot_a", 10, 14),), empty=True)
    empty_violations = check_scene_runtime(
        SceneSpec(
            id="empty_parent_scene",
            parent_id="parent_room",
            mounts=(SceneMountSpec(prop_id="prop_a", anchor="slot_a", prop_anchor="foot"),),
        ),
        empty_parent,
        {"prop_a": prop_a},
        style,
    )
    assert any(v.rule == "scene-anchor-bounds" and v.severity == "error" for v in empty_violations)


@pytest.mark.parametrize(
    ("strict_bounds", "expected_severity"),
    [(False, "warning"), (True, "error")],
)
def test_scene_bounds_audit_respects_strict_flag(
    strict_bounds: bool,
    expected_severity: str,
) -> None:
    """Out-of-bounds prop placement emits warning or error based on `strict_bounds`."""
    style = _sample_style()
    parent = _make_parent(anchors=(("edge_slot", 4, 14),))
    prop_a = _make_prop("prop_a", width=12, height=8, fill_rect=(0, 0, 12, 8))
    scene = SceneSpec(
        id="bounds_scene",
        parent_id="parent_room",
        strict_bounds=strict_bounds,
        mounts=(SceneMountSpec(prop_id="prop_a", anchor="edge_slot", prop_anchor="foot"),),
    )

    violations = check_scene_runtime(scene, parent, {"prop_a": prop_a}, style)
    bounds_v = [v for v in violations if v.rule == "scene-bounds"]
    assert len(bounds_v) == 1
    assert bounds_v[0].severity == expected_severity


@pytest.mark.parametrize(
    ("strict_perspective", "expected_severity"),
    [(False, "warning"), (True, "error")],
)
def test_scene_perspective_audit_respects_strict_flag(
    strict_perspective: bool,
    expected_severity: str,
) -> None:
    """Mismatched prop perspective emits warning or error based on `strict_perspective`."""
    style = _sample_style()
    parent = _make_parent()
    prop_front = _make_prop("prop_front", perspective="front-2.5d")
    scene = SceneSpec(
        id="persp_scene",
        parent_id="parent_room",
        strict_perspective=strict_perspective,
        mounts=(SceneMountSpec(prop_id="prop_front", anchor="slot_a", prop_anchor="foot"),),
    )

    violations = check_scene_runtime(scene, parent, {"prop_front": prop_front}, style)
    persp_v = [v for v in violations if v.rule == "scene-perspective"]
    assert len(persp_v) == 1
    assert persp_v[0].severity == expected_severity


def test_scene_occlusion_thresholds_warning_and_error() -> None:
    """Occlusion >=25% emits warning and >=50% emits error."""
    style = _sample_style()
    parent = _make_parent(anchors=(("back_slot", 16, 16), ("front_slot", 16, 17)))

    # 8x4 = 32 opaque px in back; front covers 12 px (37.5% -> warning)
    prop_back = _make_prop("prop_back", width=8, height=8, fill_rect=(0, 4, 8, 4))
    prop_warn = _make_prop("prop_warn", width=8, height=8, fill_rect=(0, 5, 4, 3))
    warn_scene = SceneSpec(
        id="occ_warn_scene",
        parent_id="parent_room",
        mounts=(
            SceneMountSpec(prop_id="prop_back", anchor="back_slot", prop_anchor="foot"),
            SceneMountSpec(
                prop_id="prop_warn",
                anchor="front_slot",
                prop_anchor="foot",
                offset_y=-1,
                z_index=1,
            ),
        ),
    )
    warn_v = [
        v
        for v in check_scene_runtime(
            warn_scene, parent, {"prop_back": prop_back, "prop_warn": prop_warn}, style
        )
        if v.rule == "scene-occlusion"
    ]
    assert len(warn_v) == 1
    assert warn_v[0].severity == "warning"

    # Front covers 24/32 px (75.0% -> error)
    prop_err = _make_prop("prop_err", width=8, height=8, fill_rect=(0, 4, 6, 4))
    err_scene = SceneSpec(
        id="occ_err_scene",
        parent_id="parent_room",
        mounts=(
            SceneMountSpec(prop_id="prop_back", anchor="back_slot", prop_anchor="foot"),
            SceneMountSpec(
                prop_id="prop_err",
                anchor="front_slot",
                prop_anchor="foot",
                offset_y=-1,
                z_index=1,
            ),
        ),
    )
    err_v = [
        v
        for v in check_scene_runtime(
            err_scene, parent, {"prop_back": prop_back, "prop_err": prop_err}, style
        )
        if v.rule == "scene-occlusion"
    ]
    assert len(err_v) == 1
    assert err_v[0].severity == "error"


def test_cli_check_validates_scene_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `pixelforge check` runs scene ergonomics guards and reports JSON/LLM findings."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    # Add a parent asset with two anchors (one inside bbox, one outside) and a valid scene
    (tmp_path / "assets" / "room_base.asset.py").write_text(
        """from __future__ import annotations

from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="room_base",
    style_id="sweetie-16",
    perspective="iso-2:1",
    width=48,
    height=48,
    states=("idle",),
    frames=1,
    fps=4,
)


def render(a: Asset) -> None:
    p = a.pal
    a.rect(8, 8, 32, 32, p.SLATE_D)
    a.anchor("slot_a", 24, 28)
    a.anchor("slot_oob", 2, 2)
""",
        encoding="utf-8",
    )

    scene_path = tmp_path / "assets" / "room_scene.scene.py"
    scene_path.write_text(
        """from __future__ import annotations

from pixelforge import SceneMountSpec, SceneSpec

SCENE = SceneSpec(
    id="room_scene",
    parent_id="room_base",
    mounts=(
        SceneMountSpec(prop_id="example_crate", anchor="slot_a"),
    ),
)
""",
        encoding="utf-8",
    )

    assert main(["check", "room_scene", "--format", "json", "--root", str(tmp_path)]) == 0
    ok_payload = json.loads(capsys.readouterr().out)
    assert ok_payload["passed"] is True
    assert ok_payload["errors"] == 0

    # Break scene with duplicate mount + out-of-bbox anchor
    scene_path.write_text(
        """from __future__ import annotations

from pixelforge import SceneMountSpec, SceneSpec

SCENE = SceneSpec(
    id="room_scene",
    parent_id="room_base",
    mounts=(
        SceneMountSpec(prop_id="example_crate", anchor="slot_oob"),
        SceneMountSpec(prop_id="example_crate", anchor="slot_oob", offset_x=2),
    ),
)
""",
        encoding="utf-8",
    )

    assert main(["check", "room_scene", "--format", "json", "--root", str(tmp_path)]) == 1
    err_payload = json.loads(capsys.readouterr().out)
    assert err_payload["passed"] is False
    rules = {v["rule"] for v in err_payload["violations"]}
    assert {"duplicate-mount", "scene-anchor-bounds"} <= rules
    assert all(v["hint"] for v in err_payload["violations"])


def test_scene_portal_runtime_checks() -> None:
    """Verify duplicate-portal, self-loop, and portal anchor bounds checks."""
    style = _sample_style()
    parent = _make_parent(anchors=(("door_in", 12, 14), ("door_oob", 1, 1)))
    scene = SceneSpec(
        id="room_a",
        parent_id="parent_room",
        portals=(
            ScenePortalSpec(id="p1", target_scene_id="room_a"),
            ScenePortalSpec(id="p1", target_scene_id="room_b", anchor="missing_anchor"),
            ScenePortalSpec(id="p2", target_scene_id="room_b", anchor="door_oob"),
        ),
    )

    violations = check_scene_runtime(scene, parent, {}, style, file_path="room_a.scene.py")
    rules = {v.rule for v in violations}
    assert {"duplicate-portal", "scene-portal-self-loop", "scene-portal-anchor"} <= rules


def test_check_scene_graph_multi_scene_validation() -> None:
    """Validate bidirectional portal links, missing targets, and unreachable islands."""
    room_a = SceneSpec(
        id="room_a",
        parent_id="p_a",
        portals=(
            ScenePortalSpec(
                id="to_b",
                target_scene_id="room_b",
                target_portal_id="to_a",
                bidirectional=True,
            ),
        ),
    )
    room_b = SceneSpec(
        id="room_b",
        parent_id="p_b",
        portals=(
            ScenePortalSpec(
                id="to_a",
                target_scene_id="room_a",
                target_portal_id="to_b",
                bidirectional=True,
            ),
        ),
    )
    assert (
        check_scene_graph({"room_a": (room_a, "a.scene.py"), "room_b": (room_b, "b.scene.py")})
        == []
    )

    # Broken target, missing target_portal_id, missing reciprocal, and unreachable island
    broken_a = SceneSpec(
        id="room_a",
        parent_id="p_a",
        portals=(
            ScenePortalSpec(id="to_missing", target_scene_id="nowhere"),
            ScenePortalSpec(
                id="to_b_bad_port",
                target_scene_id="room_b",
                target_portal_id="nonexistent",
            ),
            ScenePortalSpec(
                id="to_b_oneway",
                target_scene_id="room_b",
                bidirectional=True,
            ),
        ),
    )
    room_b_empty = SceneSpec(id="room_b", parent_id="p_b")
    island = SceneSpec(id="island", parent_id="p_c")

    violations = check_scene_graph(
        {
            "room_a": (broken_a, "a.scene.py"),
            "room_b": (room_b_empty, "b.scene.py"),
            "island": (island, "c.scene.py"),
        }
    )
    by_rule = {v.rule: v for v in violations}
    assert "scene-portal-target" in by_rule
    assert "scene-portal-target-portal" in by_rule
    assert "scene-portal-reciprocal" in by_rule
    assert by_rule["scene-graph-unreachable"].severity == "warning"


def test_cli_check_validates_multi_scene_world_graph(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `pixelforge check` validates multi-scene portal graphs across `*.scene.py`."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    (tmp_path / "assets" / "hall.asset.py").write_text(
        """from __future__ import annotations
from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="hall_base",
    style_id="sweetie-16",
    perspective="iso-2:1",
    width=32,
    height=32,
    states=("idle",),
)

def render(a: Asset) -> None:
    p = a.pal
    a.rect(4, 4, 24, 24, p.SLATE_D)
    a.anchor("door_east", 20, 16)
""",
        encoding="utf-8",
    )

    scene_a = tmp_path / "assets" / "hall_a.scene.py"
    scene_b = tmp_path / "assets" / "hall_b.scene.py"
    scene_a.write_text(
        """from __future__ import annotations
from pixelforge import ScenePortalSpec, SceneSpec

SCENE = SceneSpec(
    id="hall_a",
    parent_id="hall_base",
    portals=(
        ScenePortalSpec(
            id="east_door",
            target_scene_id="hall_b",
            anchor="door_east",
            target_portal_id="west_door",
            bidirectional=True,
        ),
    ),
)
""",
        encoding="utf-8",
    )
    scene_b.write_text(
        """from __future__ import annotations
from pixelforge import ScenePortalSpec, SceneSpec

SCENE = SceneSpec(
    id="hall_b",
    parent_id="hall_base",
    portals=(
        ScenePortalSpec(
            id="west_door",
            target_scene_id="hall_a",
            anchor="door_east",
            target_portal_id="east_door",
            bidirectional=True,
        ),
    ),
)
""",
        encoding="utf-8",
    )

    assert main(["check", "--format", "json", "--root", str(tmp_path)]) == 0
    ok_payload = json.loads(capsys.readouterr().out)
    assert ok_payload["passed"] is True

    # Break reciprocal link in hall_b
    scene_b.write_text(
        """from __future__ import annotations
from pixelforge import SceneSpec

SCENE = SceneSpec(id="hall_b", parent_id="hall_base")
""",
        encoding="utf-8",
    )
    assert main(["check", "--format", "json", "--root", str(tmp_path)]) == 1
    err_payload = json.loads(capsys.readouterr().out)
    assert err_payload["passed"] is False
    assert any(v["rule"] == "scene-portal-target-portal" for v in err_payload["violations"])
