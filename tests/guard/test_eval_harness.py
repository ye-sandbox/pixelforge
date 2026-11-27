"""Hermetic tests for the reproducible multi-genre craft + 5-axis critic eval harness."""

from __future__ import annotations

import json
from pathlib import Path

import httpx2
import pytest

from pixelforge.guard.critic import CriticConfig
from pixelforge.guard.eval_harness import (
    DEFAULT_EVAL_CASES,
    EvalCase,
    format_eval_report,
    main,
    run_multi_genre_eval,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_multi_genre_eval_offline_passes_all_default_cases() -> None:
    report = run_multi_genre_eval(_REPO_ROOT)

    assert report.mode == "offline"
    assert report.total_cases == len(DEFAULT_EVAL_CASES)
    assert report.passed is True
    assert report.passed_cases == report.total_cases
    assert report.failed_cases == 0
    assert report.craft_pass_rate == 1.0
    assert report.critic_pass_rate == 1.0
    assert report.mean_critic_score >= 90.0

    categories = {r.category for r in report.results}
    styles = {r.style_id for r in report.results}
    assert {"character", "iso_prop", "ui_tilemap"}.issubset(categories)
    assert len(styles) >= 6
    for res in report.results:
        assert res.critic_verdict.criteria is not None
        assert res.critic_verdict.criteria.total == res.critic_verdict.score
        assert res.critic_verdict.model == "deterministic-craft-v1"


def test_multi_genre_eval_is_deterministic_and_formats_cleanly() -> None:
    subset = DEFAULT_EVAL_CASES[:3]
    first = run_multi_genre_eval(_REPO_ROOT, cases=subset)
    second = run_multi_genre_eval(_REPO_ROOT, cases=subset)
    assert first.model_dump() == second.model_dump()

    llm_out = format_eval_report(first, output_format="llm")
    assert "status=pass mode=offline cases=3/3" in llm_out

    json_out = format_eval_report(first, output_format="json")
    parsed = json.loads(json_out)
    assert parsed["total_cases"] == 3
    assert parsed["passed"] is True

    human_out = format_eval_report(first, output_format="human")
    assert "[PASS]" in human_out


def test_multi_genre_eval_supports_hydra_mock_transport() -> None:
    def _handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "score": 88,
                                "criteria": {
                                    "silhouette_1x": 18,
                                    "lighting_consistency": 18,
                                    "cluster_cleanliness": 17,
                                    "state_frame_legibility": 18,
                                    "anchors_and_palette": 17,
                                },
                                "summary": "Clean 1x silhouette and consistent top-left shading.",
                                "strengths": ["Crisp 1x readability on dark and light backgrounds"],
                                "findings": [],
                                "fixes": [],
                            }
                        )
                    }
                }
            ]
        }
        return httpx2.Response(200, json=payload)

    cfg = CriticConfig(base_url="http://127.0.0.1:3000/v1", api_key="sk-test")
    with httpx2.Client(base_url=cfg.base_url, transport=httpx2.MockTransport(_handler)) as client:
        report = run_multi_genre_eval(
            _REPO_ROOT,
            cases=DEFAULT_EVAL_CASES[:2],
            critic_config=cfg,
            client=client,
        )

    assert report.mode == "hydra"
    assert report.passed is True
    assert report.mean_critic_score == 88.0
    assert all(r.critic_verdict.model == "fast" for r in report.results)


def test_multi_genre_eval_rejects_empty_or_missing_cases(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one EvalCase"):
        run_multi_genre_eval(_REPO_ROOT, cases=())

    with pytest.raises(FileNotFoundError, match="not found"):
        run_multi_genre_eval(
            _REPO_ROOT,
            cases=(
                EvalCase(
                    asset_id="nonexistent_asset",
                    genre="test",
                    category="iso_prop",
                    style_id="homelab-16bit",
                ),
            ),
        )


def test_eval_harness_cli_main_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--root", str(_REPO_ROOT), "--format", "llm"])
    captured = capsys.readouterr()
    assert code == 0
    assert "status=pass mode=offline" in captured.out
