"""Hermetic unit tests for the automated multimodal critic (`pixelforge.guard.critic`)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx2
import pytest

from pixelforge.cli.main import main
from pixelforge.cli.scaffold import scaffold_project
from pixelforge.export.bundle import LoadedAsset
from pixelforge.guard.critic import (
    CriticAssetInput,
    CriticBatchReport,
    CriticConfig,
    CriticError,
    CriticVerdict,
    build_critic_payload,
    format_critic_markdown,
    parse_critic_response,
    score_asset_via_hydra,
    score_assets_batch,
)
from pixelforge.guard.runner import load_asset_module

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _make_sample_asset(tmp_path: Path) -> LoadedAsset:
    scaffold_project(tmp_path, style_id="homelab-16bit")
    asset_path = next((tmp_path / "assets").rglob("*.asset.py"))
    return load_asset_module(asset_path)


def test_critic_config_enforces_fast_model_and_redacts_key() -> None:
    cfg = CriticConfig(
        base_url="https://hydra-router.homelab.yegear.dev/v1/",
        api_key="hydra_live_secret_token_123",
        session_id="ci-run-42",
    )
    assert cfg.base_url == "https://hydra-router.homelab.yegear.dev/v1"
    assert "hydra_live_secret_token_123" not in repr(cfg)

    for bad_model in ("deep", "gemini-2.5-flash", "llama-3.3-70b-versatile"):
        with pytest.raises(ValueError, match="only virtual model 'fast' is permitted"):
            CriticConfig(
                base_url="http://127.0.0.1:3000/v1",
                api_key="sk-test",
                model=bad_model,
            )


def test_build_critic_payload_includes_contact_sheet_and_optional_diff(tmp_path: Path) -> None:
    loaded = _make_sample_asset(tmp_path)
    item = CriticAssetInput(
        asset=loaded,
        contact_sheet_png=_TINY_PNG,
        diff_png=_TINY_PNG,
        diff_changed_pixels=14,
    )
    payload = build_critic_payload(item)
    assert payload["model"] == "fast"
    assert payload["response_format"] == {"type": "json_object"}
    messages = payload["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    user_parts = messages[1]["content"]
    assert user_parts[0]["type"] == "text"
    assert loaded.SPEC.id in user_parts[0]["text"]
    assert "Changed pixels vs baseline: 14" in user_parts[0]["text"]
    assert len([p for p in user_parts if p["type"] == "image_url"]) == 2
    assert user_parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_critic_system_prompt_includes_spatial_and_scene_coherence_checks(tmp_path: Path) -> None:
    loaded = _make_sample_asset(tmp_path)
    payload = build_critic_payload(CriticAssetInput(asset=loaded, contact_sheet_png=_TINY_PNG))
    system_prompt = payload["messages"][0]["content"]
    assert "1-3px" in system_prompt
    assert "rectangular workstation desk" in system_prompt
    assert "facing direction" in system_prompt
    assert "peripherals" in system_prompt
    assert "duplicate baked-in props" in system_prompt


def test_parse_critic_response_handles_fenced_json_and_threshold() -> None:
    raw = {
        "choices": [
            {
                "message": {
                    "content": (
                        "```json\n"
                        '{"score": 68, "summary": "Readable silhouette but noisy bezel.", '
                        '"findings": ["(12, 8): orphan highlight pixel"]}\n'
                        "```"
                    )
                }
            }
        ]
    }
    verdict = parse_critic_response(
        raw,
        asset_id="starter_box",
        model="fast",
        threshold=70,
    )
    assert verdict.score == 68
    assert verdict.passed is False
    assert verdict.summary == "Readable silhouette but noisy bezel."
    assert verdict.findings == ["(12, 8): orphan highlight pixel"]


def test_parse_critic_response_rejects_malformed_payload() -> None:
    with pytest.raises(CriticError, match="Invalid critic response"):
        parse_critic_response({}, asset_id="a", model="fast", threshold=70)

    with pytest.raises(CriticError, match="Invalid JSON"):
        parse_critic_response(
            {"choices": [{"message": {"content": "not-json"}}]},
            asset_id="a",
            model="fast",
            threshold=70,
        )

    with pytest.raises(CriticError, match="schema mismatch"):
        parse_critic_response(
            {"choices": [{"message": {"content": '{"score": 150, "summary": "bad"}'}}]},
            asset_id="a",
            model="fast",
            threshold=70,
        )


def test_score_assets_batch_with_mock_transport(tmp_path: Path) -> None:
    loaded = _make_sample_asset(tmp_path)
    captured_headers: list[tuple[str | None, str | None]] = []
    captured_paths: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured_paths.append(request.url.path)
        captured_headers.append(
            (
                request.headers.get("Authorization"),
                request.headers.get("X-Hydra-Session"),
            )
        )
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "fast"
        return httpx2.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "score": 88,
                                    "summary": "Crisp 1x silhouette and clean palette.",
                                    "findings": [],
                                }
                            )
                        }
                    }
                ]
            },
        )

    transport = httpx2.MockTransport(handler)
    config = CriticConfig(
        base_url="https://hydra-router.homelab.yegear.dev/v1",
        api_key="hydra_live_test_key",
        threshold=70,
        session_id="ci-session-1",
    )
    report = score_assets_batch(
        [CriticAssetInput(asset=loaded, contact_sheet_png=_TINY_PNG)],
        config,
        transport=transport,
    )
    assert report.passed is True
    assert report.average_score == 88.0
    assert report.verdicts[0].asset_id == loaded.SPEC.id
    assert captured_paths == ["/v1/chat/completions"]
    assert captured_headers == [("Bearer hydra_live_test_key", "ci-session-1")]


def test_score_asset_error_handling_never_leaks_api_key(tmp_path: Path) -> None:
    loaded = _make_sample_asset(tmp_path)
    bearer_value = "hydra_live_test_value_999"

    def handler_503(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            503,
            headers={"Retry-After": "5"},
            json={
                "error": {
                    "type": "hydra_exhaustion_error",
                    "message": "All upstream tiers exhausted",
                }
            },
        )

    config = CriticConfig(
        base_url="http://127.0.0.1:3000/v1",
        api_key=bearer_value,
    )
    with pytest.raises(CriticError) as exc_info:
        score_asset_via_hydra(
            CriticAssetInput(asset=loaded, contact_sheet_png=_TINY_PNG),
            config,
            transport=httpx2.MockTransport(handler_503),
        )
    message = str(exc_info.value)
    assert "503" in message
    assert "hydra_exhaustion_error" in message
    assert "Retry-After: 5s" in message
    assert bearer_value not in message


def test_cli_critic_skips_cleanly_when_no_git_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _make_sample_asset(tmp_path)

    def _no_changes(_root: Path, *, base_ref: str) -> set[Path]:
        return set()

    monkeypatch.setattr(
        "pixelforge.cli.critic_cmd.discover_changed_paths_from_git",
        _no_changes,
    )
    code = main(["critic", "--root", str(tmp_path), "--base", "HEAD"])
    assert code == 0
    captured = capsys.readouterr()
    assert "status=skip reason=no_changes base=HEAD threshold=70 passed=true" in captured.out


def test_format_critic_markdown_includes_assets_scenes_and_findings() -> None:
    report = CriticBatchReport(
        verdicts=[
            CriticVerdict(
                asset_id="desk_iso",
                kind="asset",
                score=85,
                passed=True,
                summary="Clean silhouette and palette.",
                findings=[],
                model="fast",
                threshold=70,
            ),
            CriticVerdict(
                asset_id="desk_scene",
                kind="scene",
                score=64,
                passed=False,
                summary="Monitor overlaps lamp.",
                findings=["(22, 10): monitor clips lamp shade"],
                model="fast",
                threshold=70,
            ),
        ],
        passed=False,
        threshold=70,
        average_score=74.5,
    )
    md = format_critic_markdown(report, base_ref="origin/main")
    assert "## Pixelforge Visual Critic Summary" in md
    assert "**Status:** FAIL" in md
    assert "**Base:** `origin/main`" in md
    assert "| `desk_iso` | asset | 85/100 | PASS |" in md
    assert "| `desk_scene` | scene | 64/100 | FAIL |" in md
    assert "- **`desk_scene`**: (22, 10): monitor clips lamp shade" in md


def _setup_scene_repo(tmp_path: Path) -> None:
    scaffold_project(tmp_path, style_id="homelab-16bit")
    prop_path = tmp_path / "assets" / "tiny_led.asset.py"
    prop_path.write_text(
        '"""Tiny mounted LED prop."""\n\n'
        "from __future__ import annotations\n\n"
        "from pixelforge import Asset, AssetSpec\n\n"
        "SPEC = AssetSpec(\n"
        '    id="tiny_led",\n'
        '    style_id="homelab-16bit",\n'
        '    perspective="iso-2:1",\n'
        "    width=8,\n"
        "    height=8,\n"
        '    states=("idle",),\n'
        "    frames=1,\n"
        "    fps=1,\n"
        ")\n\n\n"
        "def render(a: Asset) -> None:\n"
        "    p = a.pal\n"
        "    a.rect(2, 2, 4, 4, p.LED_C)\n"
        '    a.anchor("mount_bottom", 4, 6)\n',
        encoding="utf-8",
    )
    scene_path = tmp_path / "assets" / "crate_scene.scene.py"
    scene_path.write_text(
        '"""Composed crate scene."""\n\n'
        "from __future__ import annotations\n\n"
        "from pixelforge import SceneMountSpec, SceneSpec\n\n"
        "SCENE = SceneSpec(\n"
        '    id="crate_scene",\n'
        '    parent_id="example_crate",\n'
        '    style_id="homelab-16bit",\n'
        "    mounts=(\n"
        '        SceneMountSpec(prop_id="tiny_led", anchor="foot", prop_anchor="mount_bottom"),\n'
        "    ),\n"
        ")\n",
        encoding="utf-8",
    )


def test_cli_critic_scores_composed_scene_and_writes_summary_md(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _setup_scene_repo(tmp_path)
    captured_items: list[CriticAssetInput] = []

    def _fake_batch(
        items: list[CriticAssetInput],
        config: CriticConfig,
    ) -> CriticBatchReport:
        captured_items.extend(items)
        verdicts = [
            CriticVerdict(
                asset_id=item.target_spec.id,
                kind=item.kind,
                score=91,
                passed=True,
                summary="Coherent scene composition.",
                findings=[],
                model=config.model,
                threshold=config.threshold,
            )
            for item in items
        ]
        return CriticBatchReport(
            verdicts=verdicts,
            passed=True,
            threshold=config.threshold,
            average_score=91.0,
        )

    monkeypatch.setattr("pixelforge.cli.critic_cmd.score_assets_batch", _fake_batch)
    monkeypatch.setenv("LLM_API_KEY", "sk-test-scene")
    summary_md = tmp_path / ".pixelforge" / "critic-summary.md"

    code = main(
        [
            "critic",
            "crate_scene",
            "--root",
            str(tmp_path),
            "--summary-md",
            str(summary_md),
        ]
    )
    assert code == 0
    assert len(captured_items) == 1
    assert captured_items[0].kind == "scene"
    assert captured_items[0].target_spec.id == "crate_scene"
    assert captured_items[0].contact_sheet_png.startswith(b"\x89PNG")
    payload = build_critic_payload(captured_items[0])
    user_text = payload["messages"][1]["content"][0]["text"]
    assert "Kind: scene" in user_text
    assert "Parent ID: example_crate" in user_text
    assert "tiny_led@foot" in user_text

    out = capsys.readouterr().out
    assert "critic kind=scene asset=crate_scene score=91/100 status=PASS" in out
    md_text = summary_md.read_text(encoding="utf-8")
    assert "| `crate_scene` | scene | 91/100 | PASS |" in md_text


def test_cli_critic_base_selects_scene_when_prop_changes_and_writes_skip_md(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_scene_repo(tmp_path)
    prop_path = (tmp_path / "assets" / "tiny_led.asset.py").resolve()
    captured_ids: list[str] = []

    def _changed_prop(_root: Path, *, base_ref: str) -> set[Path]:
        return {prop_path}

    def _fake_batch(
        items: list[CriticAssetInput],
        config: CriticConfig,
    ) -> CriticBatchReport:
        captured_ids.extend(item.target_spec.id for item in items)
        return CriticBatchReport(
            verdicts=[
                CriticVerdict(
                    asset_id=item.target_spec.id,
                    kind=item.kind,
                    score=84,
                    passed=True,
                    summary="Clean update.",
                    findings=[],
                    model=config.model,
                    threshold=config.threshold,
                )
                for item in items
            ],
            passed=True,
            threshold=config.threshold,
            average_score=84.0,
        )

    def _none_from_git(_root: Path, _path: Path, *, ref: str = "HEAD") -> None:
        return None

    def _no_changes(_root: Path, *, base_ref: str) -> set[Path]:
        return set()

    monkeypatch.setattr(
        "pixelforge.cli.critic_cmd.discover_changed_paths_from_git",
        _changed_prop,
    )
    monkeypatch.setattr("pixelforge.cli.critic_cmd.score_assets_batch", _fake_batch)
    monkeypatch.setattr("pixelforge.cli.critic_cmd.load_asset_from_git", _none_from_git)
    monkeypatch.setattr("pixelforge.cli.critic_cmd.load_scene_from_git", _none_from_git)
    monkeypatch.setenv("LLM_API_KEY", "sk-test-scene")

    code = main(["critic", "--root", str(tmp_path), "--base", "HEAD"])
    assert code == 0
    assert "tiny_led" in captured_ids
    assert "crate_scene" in captured_ids

    # Skip case also writes --summary-md cleanly
    skip_md = tmp_path / ".pixelforge" / "skip-summary.md"
    monkeypatch.setattr(
        "pixelforge.cli.critic_cmd.discover_changed_paths_from_git",
        _no_changes,
    )
    skip_code = main(
        ["critic", "--root", str(tmp_path), "--base", "HEAD", "--summary-md", str(skip_md)]
    )
    assert skip_code == 0
    assert "No changed assets, styles, or scenes detected" in skip_md.read_text(encoding="utf-8")
