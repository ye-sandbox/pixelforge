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
    CriticConfig,
    CriticError,
    build_critic_payload,
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
