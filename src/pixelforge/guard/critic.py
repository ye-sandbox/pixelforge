"""Automated multimodal visual critic client for `hydra-llm-router` (OpenAI v1)."""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import httpx2
from pydantic import BaseModel, Field, ValidationError

from pixelforge.export.bundle import LoadedAsset

_ALLOWED_VIRTUAL_MODEL: Final[str] = "fast"
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"^```(?:json)?\s*\n(?P<body>.*?)\n```\s*$",
    re.DOTALL,
)

_SYSTEM_PROMPT: Final[str] = (
    "You are a senior 16-bit pixel-art visual critic for pixelforge. "
    "Evaluate the provided diagnostic contact sheet (and optional baseline|current|diff panel) "
    "for: (1) 1x silhouette readability, (2) palette and emissive-token discipline, "
    "(3) isometric/orthographic proportion and anchor alignment, and "
    "(4) visual regression risk against the baseline if a diff panel is included. "
    "Respond ONLY with a JSON object matching: "
    '{"score": <int 0-100>, "summary": "<one concise sentence>", '
    '"findings": ["<specific coordinate or token observation>", ...]}.'
)


class CriticError(RuntimeError):
    """Raised when the multimodal critic request or response fails."""


@dataclass(frozen=True)
class CriticConfig:
    """Connection and scoring configuration for `hydra-llm-router`."""

    base_url: str
    api_key: str = field(repr=False)
    model: str = _ALLOWED_VIRTUAL_MODEL
    timeout_seconds: float = 120.0
    threshold: int = 70
    session_id: str | None = None

    def __post_init__(self) -> None:
        normalized_url = self.base_url.strip().rstrip("/")
        if not normalized_url:
            msg = "LLM_BASE_URL must not be empty"
            raise ValueError(msg)
        object.__setattr__(self, "base_url", normalized_url)

        if not self.api_key.strip():
            msg = "LLM_API_KEY must not be empty"
            raise ValueError(msg)

        # INVARIANT: Restrict CI critic to the `fast` virtual model alias to prevent
        # hardcoded upstream provider coupling and unintended `deep` quota spend.
        if self.model != _ALLOWED_VIRTUAL_MODEL:
            msg = (
                f"Unsupported critic model {self.model!r}: "
                f"only virtual model {_ALLOWED_VIRTUAL_MODEL!r} is permitted"
            )
            raise ValueError(msg)

        if self.timeout_seconds <= 0:
            msg = f"timeout_seconds must be positive, got {self.timeout_seconds}"
            raise ValueError(msg)
        if not (0 <= self.threshold <= 100):
            msg = f"threshold must be in 0..100, got {self.threshold}"
            raise ValueError(msg)


class _RawCriticPayload(BaseModel):
    """Validated JSON schema returned by the multimodal model."""

    score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1)
    findings: list[str] = Field(default_factory=list)


class _OpenAIChoiceMessage(BaseModel):
    content: str = Field(min_length=1)


class _OpenAIChoice(BaseModel):
    message: _OpenAIChoiceMessage


class _OpenAIChatResponse(BaseModel):
    choices: list[_OpenAIChoice] = Field(min_length=1)


class _OpenAIErrorBody(BaseModel):
    type: str = ""
    message: str = ""


class _OpenAIErrorEnvelope(BaseModel):
    error: _OpenAIErrorBody | None = None


class CriticVerdict(BaseModel):
    """Structured per-asset visual regression score and findings."""

    asset_id: str
    score: int = Field(ge=0, le=100)
    passed: bool
    summary: str
    findings: list[str]
    model: str
    threshold: int


class CriticBatchReport(BaseModel):
    """Aggregated batch scoring report across one or more assets."""

    verdicts: list[CriticVerdict]
    passed: bool
    threshold: int
    average_score: float


@dataclass(frozen=True)
class CriticAssetInput:
    """Rendered visual artifacts submitted to the critic for one asset."""

    asset: LoadedAsset
    contact_sheet_png: bytes
    diff_png: bytes | None = None
    diff_changed_pixels: int | None = None


def _encode_png_data_url(png_bytes: bytes) -> str:
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_critic_payload(
    item: CriticAssetInput,
    *,
    model: str = _ALLOWED_VIRTUAL_MODEL,
) -> dict[str, Any]:
    """Build an OpenAI v1 `/v1/chat/completions` multimodal request payload."""
    spec = item.asset.SPEC
    context_lines = [
        f"Asset ID: {spec.id}",
        f"Style ID: {spec.style_id}",
        f"Dimensions: {spec.width}x{spec.height}",
        f"Perspective: {spec.perspective}",
        f"States: {', '.join(spec.states)} | Frames: {spec.frames} | FPS: {spec.fps}",
    ]
    if item.diff_changed_pixels is not None:
        context_lines.append(f"Changed pixels vs baseline: {item.diff_changed_pixels}")

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": "\n".join(context_lines)},
        {
            "type": "image_url",
            "image_url": {"url": _encode_png_data_url(item.contact_sheet_png)},
        },
    ]
    if item.diff_png is not None:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": _encode_png_data_url(item.diff_png)},
            }
        )

    return {
        "model": model,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group("body").strip() if match else stripped


def parse_critic_response(
    raw_json: object,
    *,
    asset_id: str,
    model: str,
    threshold: int,
) -> CriticVerdict:
    """Parse an OpenAI v1 chat completion response into a `CriticVerdict`."""
    try:
        envelope = _OpenAIChatResponse.model_validate(raw_json)
    except ValidationError as exc:
        msg = f"Invalid critic response for {asset_id}: {exc}"
        raise CriticError(msg) from exc

    cleaned = _strip_code_fence(envelope.choices[0].message.content)
    try:
        parsed_obj: object = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in critic content for {asset_id}: {exc}"
        raise CriticError(msg) from exc

    try:
        validated = _RawCriticPayload.model_validate(parsed_obj)
    except ValidationError as exc:
        msg = f"Critic JSON schema mismatch for {asset_id}: {exc}"
        raise CriticError(msg) from exc

    return CriticVerdict(
        asset_id=asset_id,
        score=validated.score,
        passed=validated.score >= threshold,
        summary=validated.summary.strip(),
        findings=[f.strip() for f in validated.findings if f.strip()],
        model=model,
        threshold=threshold,
    )


def _extract_error_detail(response: httpx2.Response) -> str:
    """Extract sanitized error detail from an HTTP error response without leaking secrets."""
    try:
        raw: object = response.json()
        envelope = _OpenAIErrorEnvelope.model_validate(raw)
    except ValueError, ValidationError:
        text = response.text.strip()
        return text[:200] if text else f"HTTP {response.status_code}"

    if envelope.error is not None:
        parts = [p.strip() for p in (envelope.error.type, envelope.error.message) if p.strip()]
        if parts:
            return ": ".join(parts)[:200]
    return f"HTTP {response.status_code}"


def score_asset_via_hydra(
    item: CriticAssetInput,
    config: CriticConfig,
    *,
    client: httpx2.Client | None = None,
    transport: httpx2.BaseTransport | None = None,
) -> CriticVerdict:
    """Send one asset's contact sheet (and optional diff) to `hydra-llm-router`."""
    payload = build_critic_payload(item, model=config.model)
    headers: dict[str, str] = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    if config.session_id:
        headers["X-Hydra-Session"] = config.session_id

    owns_client = client is None
    active_client = (
        client
        if client is not None
        else httpx2.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            transport=transport,
        )
    )
    try:
        response = active_client.post("/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
    except httpx2.HTTPStatusError as exc:
        detail = _extract_error_detail(exc.response)
        retry_after = exc.response.headers.get("Retry-After")
        suffix = f" (Retry-After: {retry_after}s)" if retry_after else ""
        msg = (
            f"hydra-llm-router returned {exc.response.status_code} "
            f"for {item.asset.SPEC.id}: {detail}{suffix}"
        )
        raise CriticError(msg) from exc
    except httpx2.TimeoutException as exc:
        msg = (
            f"hydra-llm-router request timed out after {config.timeout_seconds}s "
            f"for {item.asset.SPEC.id}"
        )
        raise CriticError(msg) from exc
    except httpx2.TransportError as exc:
        msg = f"hydra-llm-router transport error for {item.asset.SPEC.id}: {exc}"
        raise CriticError(msg) from exc
    finally:
        if owns_client:
            active_client.close()

    try:
        raw_json: object = response.json()
    except ValueError as exc:
        msg = f"Non-JSON response from hydra-llm-router for {item.asset.SPEC.id}: {exc}"
        raise CriticError(msg) from exc

    return parse_critic_response(
        raw_json,
        asset_id=item.asset.SPEC.id,
        model=config.model,
        threshold=config.threshold,
    )


def score_assets_batch(
    items: Sequence[CriticAssetInput],
    config: CriticConfig,
    *,
    transport: httpx2.BaseTransport | None = None,
) -> CriticBatchReport:
    """Score a batch of assets using a shared `httpx2.Client` connection pool."""
    if not items:
        return CriticBatchReport(
            verdicts=[],
            passed=True,
            threshold=config.threshold,
            average_score=100.0,
        )

    verdicts: list[CriticVerdict] = []
    with httpx2.Client(
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        transport=transport,
    ) as client:
        for item in items:
            verdicts.append(score_asset_via_hydra(item, config, client=client))

    avg_score = round(sum(v.score for v in verdicts) / len(verdicts), 2)
    return CriticBatchReport(
        verdicts=verdicts,
        passed=all(v.passed for v in verdicts),
        threshold=config.threshold,
        average_score=avg_score,
    )


def discover_changed_paths_from_git(root: Path, *, base_ref: str) -> set[Path]:
    """Return resolved working-tree paths under `assets/` or `styles/` changed vs `base_ref`."""
    git_bin = shutil.which("git")
    if git_bin is None:
        msg = "git executable not found in PATH"
        raise CriticError(msg)

    proc = subprocess.run(
        [git_bin, "diff", "--name-only", base_ref, "--", "assets/", "styles/"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"git diff exited with {proc.returncode}"
        msg = f"Failed to inspect changed assets against {base_ref!r}: {detail}"
        raise CriticError(msg)

    changed: set[Path] = set()
    for raw_line in proc.stdout.splitlines():
        rel = raw_line.strip()
        if rel:
            changed.add((root / rel).resolve())
    return changed
