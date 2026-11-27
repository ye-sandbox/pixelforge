"""Hermetic unit and stdio protocol tests for `pixelforge mcp`."""

from __future__ import annotations

import asyncio
import base64
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, ImageContent, TextContent
from PIL import Image
from pytest import MonkeyPatch

from pixelforge.cli.mcp_cmd import create_mcp_server
from pixelforge.cli.scaffold import scaffold_project

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_EXPECTED_TOOLS = {
    "inspect_style",
    "inspect_presets",
    "inspect_prefabs",
    "inspect_api",
    "inspect_assets",
    "inspect_scenes",
    "check_asset",
    "probe_canvas",
    "render_contact_sheet",
    "compose_dry_run",
    "diff_asset",
    "analyze_ref",
    "critic_asset",
}


def _call_tool(
    server_root: Path,
    name: str,
    arguments: Mapping[str, object],
) -> CallToolResult:
    server = create_mcp_server(default_root=server_root)
    result = asyncio.run(server.call_tool(name, dict(arguments)))
    assert isinstance(result, CallToolResult)
    return result


def test_mcp_server_registers_expected_tools(tmp_path: Path) -> None:
    server = create_mcp_server(default_root=tmp_path)
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == _EXPECTED_TOOLS


def test_mcp_inspect_tools_return_structured_text(tmp_path: Path) -> None:
    scaffold_project(tmp_path)

    for tool_name, args in (
        ("inspect_presets", {}),
        ("inspect_prefabs", {"target": "architecture"}),
        ("inspect_api", {"target": "Asset"}),
        ("inspect_style", {}),
        ("inspect_assets", {}),
    ):
        res = _call_tool(tmp_path, tool_name, args)
        assert not res.is_error, f"{tool_name} failed: {res.content}"
        assert res.content
        first = res.content[0]
        assert isinstance(first, TextContent)
        assert len(first.text.strip()) > 0

    scenes_res = _call_tool(tmp_path, "inspect_scenes", {})
    assert scenes_res.is_error  # No .scene.py files in default scaffold


def test_mcp_check_asset_and_probe_canvas(tmp_path: Path) -> None:
    scaffold_project(tmp_path)

    check_res = _call_tool(tmp_path, "check_asset", {})
    assert not check_res.is_error
    assert isinstance(check_res.content[0], TextContent)
    assert "status=pass" in check_res.content[0].text

    probe_res = _call_tool(
        tmp_path,
        "probe_canvas",
        {"asset_id": "example_crate", "layers": True},
    )
    assert not probe_res.is_error
    assert isinstance(probe_res.content[0], TextContent)
    assert "example_crate" in probe_res.content[0].text

    missing_res = _call_tool(tmp_path, "probe_canvas", {"asset_id": "nonexistent_prop"})
    assert missing_res.is_error


def test_mcp_render_contact_sheet_returns_png_image_block(tmp_path: Path) -> None:
    scaffold_project(tmp_path)

    res = _call_tool(
        tmp_path,
        "render_contact_sheet",
        {"asset_id": "example_crate", "scale": 2, "layers": True},
    )
    assert not res.is_error
    assert len(res.content) == 2
    assert isinstance(res.content[0], TextContent)
    assert "probe: asset=example_crate" in res.content[0].text
    assert "histogram:" in res.content[0].text
    image_block = res.content[1]
    assert isinstance(image_block, ImageContent)
    assert image_block.mime_type == "image/png"
    decoded = base64.b64decode(image_block.data)
    assert decoded.startswith(_PNG_MAGIC)
    # Dry/ephemeral: dist/ should not be created in the project root
    assert not (tmp_path / "dist").exists()


def test_mcp_analyze_ref_and_critic_asset(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    scaffold_project(tmp_path)
    ref_path = tmp_path / "ref.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(ref_path)

    ref_res = _call_tool(
        tmp_path,
        "analyze_ref",
        {
            "image_path": str(ref_path),
            "width": 8,
            "height": 8,
            "trim": True,
            "emit_spr": True,
            "scaffold": True,
            "asset_id": "red_box",
        },
    )
    assert not ref_res.is_error
    assert isinstance(ref_res.content[0], TextContent)
    assert "red_box" in ref_res.content[0].text
    assert "SPEC = AssetSpec" in ref_res.content[0].text
    assert "a.spr(grid, 0, 0, color_map)" in ref_res.content[0].text
    assert not (tmp_path / "assets" / "red_box.asset.py").exists()

    def _fake_critic(*_args: object, **kwargs: object) -> int:
        out = kwargs["out"]
        assert callable(out)
        out("critic: status=pass score=9/10")
        return 0

    monkeypatch.setattr("pixelforge.cli.mcp_cmd.critic_workflow", _fake_critic)
    critic_res = _call_tool(tmp_path, "critic_asset", {"asset_id": "example_crate"})
    assert not critic_res.is_error
    assert isinstance(critic_res.content[0], TextContent)
    assert "critic: status=pass" in critic_res.content[0].text


def test_mcp_compose_dry_run_validates_and_catches_errors(tmp_path: Path) -> None:
    scaffold_project(tmp_path)

    # Valid self-mount dry run
    ok_res = _call_tool(
        tmp_path,
        "compose_dry_run",
        {"parent_id": "example_crate", "mounts": ["example_crate@foot"]},
    )
    assert not ok_res.is_error
    assert not (tmp_path / "dist").exists()

    bad_res = _call_tool(
        tmp_path,
        "compose_dry_run",
        {"parent_id": "example_crate", "mounts": ["invalid-mount-spec"]},
    )
    assert bad_res.is_error


def test_mcp_diff_asset_returns_png_image_block(tmp_path: Path) -> None:
    scaffold_project(tmp_path)
    git_bin = shutil.which("git")
    assert git_bin is not None
    subprocess.run([git_bin, "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [git_bin, "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [git_bin, "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run([git_bin, "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [git_bin, "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    asset_path = tmp_path / "assets" / "example_crate.asset.py"
    original = asset_path.read_text(encoding="utf-8")
    asset_path.write_text(
        f"{original.rstrip()}\n    a.put(1, 1, a.style.outline_index)\n",
        encoding="utf-8",
    )

    res = _call_tool(
        tmp_path,
        "diff_asset",
        {"asset_id": "example_crate", "base_ref": "HEAD", "scale": 2},
    )
    assert not res.is_error
    assert len(res.content) >= 2
    assert isinstance(res.content[0], TextContent)
    image_blocks = [b for b in res.content[1:] if isinstance(b, ImageContent)]
    assert image_blocks
    assert all(b.mime_type == "image/png" for b in image_blocks)
    assert base64.b64decode(image_blocks[0].data).startswith(_PNG_MAGIC)


def test_mcp_stdio_protocol_round_trip(tmp_path: Path) -> None:
    scaffold_project(tmp_path)

    async def _run() -> tuple[set[str], CallToolResult]:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "pixelforge.cli.main", "mcp", "--root", str(tmp_path)],
        )
        async with (
            stdio_client(params) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}
            call_result = await session.call_tool("inspect_presets", {})
            return tool_names, call_result

    tool_names, call_result = asyncio.run(_run())
    assert tool_names == _EXPECTED_TOOLS
    assert not call_result.is_error
    assert call_result.content
    assert isinstance(call_result.content[0], TextContent)
