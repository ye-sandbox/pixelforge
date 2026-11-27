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
from typing import Any, Final, Literal

import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pixelforge.core.types import AssetSpec
from pixelforge.export.bundle import LoadedAsset

_ALLOWED_VIRTUAL_MODEL: Final[str] = "fast"
CriticCategory = Literal["character", "iso_prop", "scene", "ui_tilemap"]
CriticTier = Literal["fast", "dev"]
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"^```(?:json)?\s*\n(?P<body>.*?)\n```\s*$",
    re.DOTALL,
)

_CHARACTER_KEYWORDS: Final[tuple[str, ...]] = (
    "avatar",
    "character",
    "operator",
    "knight",
    "slime",
    "npc",
    "player",
    "hero",
    "enemy",
    "goblin",
    "wizard",
    "skeleton",
)
_UI_TILEMAP_KEYWORDS: Final[tuple[str, ...]] = (
    "hud_",
    "ui_",
    "_9slice",
    "_tile",
    "_tiles",
    "_font",
)

_BASE_RUBRIC_PROMPT: Final[str] = (
    "You are a senior 16-bit pixel-art visual critic for pixelforge. "
    "Evaluate ONLY the provided diagnostic contact sheet (and optional baseline|current|diff "
    "panel) using the 5-axis rubric (0-20 per axis, 0-100 total):\n"
    "1. silhouette_1x (0-20): Is the subject immediately recognizable at native 1x resolution "
    "on both dark (#0d1117) and light (#e6edf3) checkerboards?\n"
    "2. lighting_consistency (0-20): Do highlights sit consistently on the lit side matching the "
    "declared lighting_angle and perspective, with shadows on the opposite side?\n"
    "3. cluster_cleanliness (0-20): Are outlines continuous without broken corners, mixels, "
    "stray 1x1 orphan pixels, or unintended stair-stepping?\n"
    "4. state_frame_legibility (0-20): Are declared states visually distinct, and do animation "
    "frames cycle smoothly without unintentional jitter?\n"
    "5. anchors_and_palette (0-20): Do anchor crosshairs and hitbox rectangles land on their "
    "exact semantic features, and do emissive/bright highlights avoid bleeding into matte "
    "surfaces?\n"
    "If a diff panel is included, also assess visual regression risk against the baseline.\n"
    "Anchor every defect in `findings` to exact `(x, y)` coordinates from the contact-sheet ruler "
    'or `(state, frame)` cells (e.g. "(12, 8) [cluster_cleanliness]: orphan highlight pixel").\n'
)

_CATEGORY_GUIDANCE: Final[dict[CriticCategory, str]] = {
    "character": (
        "Category focus (character): Prioritize 1x silhouette readability, clear head-to-body "
        "proportion and limb separation, consistent directional rim/key lighting, clean outlines "
        "without stray pixels, readable pose/animation transitions across frames, and accurate "
        "feet/head/hand anchor and hitbox placement."
    ),
    "iso_prop": (
        "Category focus (iso_prop): Prioritize 1x object silhouette and material clarity, crisp "
        "2:1 isometric or declared orthographic plane geometry, consistent shading across top/left/"
        "right faces, continuous outlines without 1x1 orphans, distinct state feedback, and exact "
        "semantic anchor/emissive discipline."
    ),
    "scene": (
        "Category focus (scene): Prioritize overall 1x composition readability and figure-ground "
        "separation, consistent perspective and lighting direction across shell and mounted props, "
        "flush 1-3px wall/floor/surface contact placement (no unintended floating items), zero "
        "duplicate baked-in props underneath mounted scene items, and accurate mount/portal "
        "anchors."
    ),
    "ui_tilemap": (
        "Category focus (ui_tilemap): Prioritize 1x icon/glyph/tile legibility on dark and light "
        "backgrounds, crisp 9-slice border/corner symmetry or seamless tile-to-tile edge "
        "continuity without visible seams, consistent bevel lighting, clean pixel clusters, "
        "distinct UI state feedback or autotile bitmask coverage, and strict margin/emissive "
        "discipline."
    ),
}

_JSON_SCHEMA_PROMPT: Final[str] = (
    "Respond ONLY with a JSON object matching:\n"
    "{\n"
    '  "score": <int 0-100>,\n'
    '  "criteria": {\n'
    '    "silhouette_1x": <int 0-20>,\n'
    '    "lighting_consistency": <int 0-20>,\n'
    '    "cluster_cleanliness": <int 0-20>,\n'
    '    "state_frame_legibility": <int 0-20>,\n'
    '    "anchors_and_palette": <int 0-20>\n'
    "  },\n"
    '  "summary": "<one concise sentence>",\n'
    '  "strengths": ["<observed visual strength>", ...],\n'
    '  "findings": ["(x, y) [<axis>]: <specific coordinate-anchored defect>", ...],\n'
    '  "fixes": ["<concrete coordinate or parametric fix>", ...]\n'
    "}"
)


class CriticError(RuntimeError):
    """Raised when the multimodal critic request or response fails."""


@dataclass(frozen=True)
class CriticConfig:
    """Connection and scoring configuration for `hydra-llm-router`."""

    base_url: str
    api_key: str = field(repr=False)
    model: str = _ALLOWED_VIRTUAL_MODEL
    allow_dev_model: bool = False
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

        normalized_model = self.model.strip()
        if not normalized_model:
            msg = "Critic model must not be empty"
            raise ValueError(msg)
        object.__setattr__(self, "model", normalized_model)

        # INVARIANT: Restrict CI critic to the `fast` virtual model alias by default to prevent
        # hardcoded upstream provider coupling and unintended `deep` quota spend.
        if not self.allow_dev_model and normalized_model != _ALLOWED_VIRTUAL_MODEL:
            msg = (
                f"Unsupported critic model {self.model!r}: "
                f"only virtual model {_ALLOWED_VIRTUAL_MODEL!r} is permitted "
                "(pass allow_dev_model=True or --tier dev for dev review)"
            )
            raise ValueError(msg)

        if self.timeout_seconds <= 0:
            msg = f"timeout_seconds must be positive, got {self.timeout_seconds}"
            raise ValueError(msg)
        if not (0 <= self.threshold <= 100):
            msg = f"threshold must be in 0..100, got {self.threshold}"
            raise ValueError(msg)


class CriticCriteria(BaseModel):
    """5-axis pixel-art visual quality rubric aligned with `blind-critic` (0-20 each)."""

    silhouette_1x: int = Field(ge=0, le=20)
    lighting_consistency: int = Field(ge=0, le=20)
    cluster_cleanliness: int = Field(ge=0, le=20)
    state_frame_legibility: int = Field(ge=0, le=20)
    anchors_and_palette: int = Field(ge=0, le=20)

    @property
    def total(self) -> int:
        """Return total rubric score in `0..100`."""
        return (
            self.silhouette_1x
            + self.lighting_consistency
            + self.cluster_cleanliness
            + self.state_frame_legibility
            + self.anchors_and_palette
        )


class _RawFinding(BaseModel):
    """Structured coordinate-anchored finding accepted from multimodal responses."""

    model_config = ConfigDict(extra="ignore")

    x: int | None = None
    y: int | None = None
    axis: str | None = None
    message: str = ""
    detail: str = ""
    issue: str = ""
    description: str = ""


class _RawCriticPayload(BaseModel):
    """Validated JSON schema returned by the multimodal model."""

    score: int | None = Field(default=None, ge=0, le=100)
    criteria: CriticCriteria | None = None
    summary: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    findings: tuple[str | _RawFinding, ...] = ()
    issues: tuple[str | _RawFinding, ...] = ()
    fixes: list[str] = Field(default_factory=list)


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
    """Structured per-asset or per-scene visual regression score and findings."""

    asset_id: str
    kind: Literal["asset", "scene"] = "asset"
    category: CriticCategory = "iso_prop"
    score: int = Field(ge=0, le=100)
    passed: bool
    criteria: CriticCriteria | None = None
    summary: str
    strengths: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    fixes: list[str] = Field(default_factory=list)
    model: str
    threshold: int


class CriticBatchReport(BaseModel):
    """Aggregated batch scoring report across one or more assets or scenes."""

    verdicts: list[CriticVerdict]
    passed: bool
    threshold: int
    average_score: float


@dataclass(frozen=True)
class CriticAssetInput:
    """Rendered visual artifacts submitted to the critic for one asset or scene."""

    asset: LoadedAsset | None = None
    contact_sheet_png: bytes = b""
    diff_png: bytes | None = None
    diff_changed_pixels: int | None = None
    spec: AssetSpec | None = None
    kind: Literal["asset", "scene"] = "asset"
    category: CriticCategory | None = None
    scene_context: tuple[str, ...] = ()

    @property
    def target_spec(self) -> AssetSpec:
        """Return the resolved `AssetSpec` for either an asset or a composed scene."""
        if self.spec is not None:
            return self.spec
        if self.asset is not None:
            return self.asset.SPEC
        msg = "CriticAssetInput requires either `asset` or `spec`"
        raise ValueError(msg)


def infer_critic_category(
    spec: AssetSpec,
    *,
    kind: Literal["asset", "scene"] = "asset",
    asset_path: Path | None = None,
) -> CriticCategory:
    """Infer the visual critic category from scene kind, spec metadata, path, and ID."""
    if kind == "scene":
        return "scene"
    if spec.tilemap is not None or spec.nine_slice is not None or spec.font is not None:
        return "ui_tilemap"

    if asset_path is not None:
        parts = {part.lower() for part in asset_path.parts}
        if parts & {"characters", "avatars"}:
            return "character"
        if parts & {"ui", "tiles", "tilemaps"}:
            return "ui_tilemap"

    lowered_id = spec.id.lower()
    if any(kw in lowered_id for kw in _CHARACTER_KEYWORDS):
        return "character"
    if any(kw in lowered_id for kw in _UI_TILEMAP_KEYWORDS):
        return "ui_tilemap"
    return "iso_prop"


def build_system_prompt(category: CriticCategory) -> str:
    """Build the category-specific 5-axis system prompt for the multimodal critic."""
    return f"{_BASE_RUBRIC_PROMPT}\n{_CATEGORY_GUIDANCE[category]}\n\n{_JSON_SCHEMA_PROMPT}"


def _encode_png_data_url(png_bytes: bytes) -> str:
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_critic_payload(
    item: CriticAssetInput,
    *,
    model: str = _ALLOWED_VIRTUAL_MODEL,
) -> dict[str, Any]:
    """Build an OpenAI v1 `/v1/chat/completions` multimodal request payload."""
    spec = item.target_spec
    category = item.category or infer_critic_category(spec, kind=item.kind)
    context_lines = [
        f"Kind: {item.kind}",
        f"Category: {category}",
        f"Asset ID: {spec.id}",
        f"Style ID: {spec.style_id}",
        f"Dimensions: {spec.width}x{spec.height}",
        f"Perspective: {spec.perspective}",
        f"States: {', '.join(spec.states)} | Frames: {spec.frames} | FPS: {spec.fps}",
    ]
    context_lines.extend(item.scene_context)
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
            {"role": "system", "content": build_system_prompt(category)},
            {"role": "user", "content": user_content},
        ],
    }


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group("body").strip() if match else stripped


def _format_raw_finding(entry: str | _RawFinding) -> str:
    if isinstance(entry, str):
        return entry.strip()
    text = (entry.message or entry.detail or entry.issue or entry.description).strip()
    prefix_parts: list[str] = []
    if entry.x is not None and entry.y is not None:
        prefix_parts.append(f"({entry.x}, {entry.y})")
    if entry.axis and entry.axis.strip():
        prefix_parts.append(f"[{entry.axis.strip()}]")
    if not prefix_parts:
        return text
    prefix = " ".join(prefix_parts)
    return f"{prefix}: {text}" if text else prefix


def parse_critic_response(
    raw_json: object,
    *,
    asset_id: str,
    model: str,
    threshold: int,
    kind: Literal["asset", "scene"] = "asset",
    category: CriticCategory = "iso_prop",
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

    if validated.score is not None:
        score = validated.score
    elif validated.criteria is not None:
        score = validated.criteria.total
    else:
        msg = f"Critic JSON schema mismatch for {asset_id}: missing 'score' and 'criteria'"
        raise CriticError(msg)

    raw_findings = validated.findings if validated.findings else validated.issues
    findings = [formatted for entry in raw_findings if (formatted := _format_raw_finding(entry))]

    return CriticVerdict(
        asset_id=asset_id,
        kind=kind,
        category=category,
        score=score,
        passed=score >= threshold,
        criteria=validated.criteria,
        summary=validated.summary.strip(),
        strengths=[s.strip() for s in validated.strengths if s.strip()],
        findings=findings,
        fixes=[f.strip() for f in validated.fixes if f.strip()],
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
    spec = item.target_spec
    try:
        response = active_client.post("/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
    except httpx2.HTTPStatusError as exc:
        detail = _extract_error_detail(exc.response)
        retry_after = exc.response.headers.get("Retry-After")
        suffix = f" (Retry-After: {retry_after}s)" if retry_after else ""
        msg = (
            f"hydra-llm-router returned {exc.response.status_code} for {spec.id}: {detail}{suffix}"
        )
        raise CriticError(msg) from exc
    except httpx2.TimeoutException as exc:
        msg = f"hydra-llm-router request timed out after {config.timeout_seconds}s for {spec.id}"
        raise CriticError(msg) from exc
    except httpx2.TransportError as exc:
        msg = f"hydra-llm-router transport error for {spec.id}: {exc}"
        raise CriticError(msg) from exc
    finally:
        if owns_client:
            active_client.close()

    try:
        raw_json: object = response.json()
    except ValueError as exc:
        msg = f"Non-JSON response from hydra-llm-router for {spec.id}: {exc}"
        raise CriticError(msg) from exc

    category = item.category or infer_critic_category(spec, kind=item.kind)
    return parse_critic_response(
        raw_json,
        asset_id=spec.id,
        model=config.model,
        threshold=config.threshold,
        kind=item.kind,
        category=category,
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


def format_critic_markdown(
    report: CriticBatchReport,
    *,
    base_ref: str | None = None,
) -> str:
    """Format a `CriticBatchReport` as a Markdown PR regression summary."""
    status = "PASS" if report.passed else "FAIL"
    lines = ["## Pixelforge Visual Critic Summary", ""]
    meta_parts = [
        f"**Status:** {status}",
        f"**Average Score:** {report.average_score}/100",
        f"**Threshold:** {report.threshold}",
    ]
    if base_ref is not None:
        meta_parts.append(f"**Base:** `{base_ref}`")
    lines.append(" | ".join(meta_parts))
    lines.append("")

    if not report.verdicts:
        lines.append("No changed assets, styles, or scenes detected; visual critic skipped.")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| Target | Kind | Category | Score | Status | Summary |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for verdict in report.verdicts:
        v_status = "PASS" if verdict.passed else "FAIL"
        summary_cell = verdict.summary.replace("|", "\\|").replace("\n", " ")
        if verdict.criteria is not None:
            c = verdict.criteria
            rubric_note = (
                f" (sil={c.silhouette_1x}/20 lit={c.lighting_consistency}/20 "
                f"clu={c.cluster_cleanliness}/20 leg={c.state_frame_legibility}/20 "
                f"anc={c.anchors_and_palette}/20)"
            )
            summary_cell = f"{summary_cell}{rubric_note}"
        lines.append(
            f"| `{verdict.asset_id}` | {verdict.kind} | {verdict.category} | "
            f"{verdict.score}/100 | {v_status} | {summary_cell} |"
        )

    findings_lines = [
        f"- **`{verdict.asset_id}`**: {finding}"
        for verdict in report.verdicts
        for finding in verdict.findings
    ]
    if findings_lines:
        lines.extend(["", "### Findings", "", *findings_lines])

    fixes_lines = [
        f"- **`{verdict.asset_id}`**: {fix}" for verdict in report.verdicts for fix in verdict.fixes
    ]
    if fixes_lines:
        lines.extend(["", "### Fixes", "", *fixes_lines])

    return "\n".join(lines) + "\n"
