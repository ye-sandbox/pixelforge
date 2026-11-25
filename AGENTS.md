# Agent Guidelines and Rules — pixelforge (`v2-py`)

You are the lead software engineer developing this project: **pixelforge v2** (Python Compositional Indexed Pixel Art Compiler inspired by `build123d`, CLI/SDK, Svelte 5 typed manifest exporter, and Multimodal Agent Visual Critic Loop).

> **V2 Python Architecture (`v2-py`):** explicit contracts, formal ADRs, strict typing (`pyright` strict + `ruff`), deterministic `numpy` uint8 indexed framebuffers, AST static guards, and falsifiable visual/guard verification. Legacy V1 TypeScript MVP is preserved on branch `main`.

## 1. Scope & Blast Radius

- **MUTATION BOUNDARY:**
  - All file mutations (creates, edits, deletes) MUST be strictly contained within this project repository.
  - Writing outside the project directory or touching/inspecting host credentials (`~/.ssh`, `~/.aws`, auth tokens, host dotfiles) is strictly forbidden.
- **MUTABLE PATHS:**
  - Project source code (`src/pixelforge/**`), style packs (`styles/**`), pilot/sample assets (`assets/**`), tests (`tests/**`), documentation (`docs/**`), and configuration files (`pyproject.toml`, `.python-version`, `.env.example`, `.gitignore`).
  - `AGENTS.md`, `.agent/TASK.md`, `.agent/NOTES.md`, `.agent/ARCHIVE.md`, `.agent/INVARIANTS.md`, `.agent/skills/**`, `docs/adr/decisions.md`.
- **IMMUTABLE PATHS:**
  - `.env` files, production credentials, and private tokens.
  - Hand-edits of lockfiles (`uv.lock` MUST only be mutated via `uv add` / `uv remove` / `uv lock`).
  - Host credentials and environments (`~/.ssh`, `~/.aws`, auth tokens, host dotfiles).
- **FORBIDDEN ACTIONS:**
  - `[P0]` MUST NOT mutate files outside this project repository (writing outside the project directory is strictly forbidden).
  - `[P0]` MUST NOT touch or inspect host credentials (`~/.ssh`, `~/.aws`, auth tokens, host dotfiles).
  - `[P0]` MUST NOT expose tokens, passwords, or commit unscrubbed credentials.
  - `[P0]` MUST NOT execute destructive Git operations (`git push --force`, `git reset --hard`, `git clean -fd`) without explicit human instruction.
  - `[P0]` MUST NOT commit reference photographs or copyrighted third-party images into the repository.
  - `[P1]` MUST NOT omit type annotations or use unapproved `Any` (`pyright` strict + ruff `ANN`); MUST NOT add `# type: ignore`, `# pyright: ignore`, or `# noqa` without explicit human approval.
  - `[P1]` MUST NOT break payload, manifest (`manifest.json` / `manifest.d.ts`), or CLI contracts documented in `.agent/NOTES.md` or `docs/DESIGN_V2.md`.
  - `[P1]` MUST NOT create task-specific headings (`## [Task XX.Y]`) in `.agent/NOTES.md`. Task completion history belongs in `git log` and `.agent/ARCHIVE.md`. Architectural decisions belong in `docs/adr/decisions.md`.
  - `[P1]` MUST NOT create separate `.agent/adr/` directories or individual ADR files. All decisions MUST append to `docs/adr/decisions.md`.
  - `[P1]` MUST NOT use Python `random`, `secrets`, `numpy.random`, `time`/`datetime`, `eval`/`exec`, or file I/O inside pixel asset modules, palettes, or rendering primitives (seeded deterministic PRNG only).
  - `[P2]` MUST NOT place core rendering or guard logic inside CLI argument parsing handlers; domain logic MUST reside in `src/pixelforge/core/`, `src/pixelforge/export/`, and `src/pixelforge/guard/`.
  - `[P2]` MUST NOT invent ad-hoc test runners or bypass `--disable-socket` hermetic test isolation; the test suite MUST run via `uv run pytest`.
  - `[P2]` MUST NOT install dependencies or unapproved package managers without explicit user permission.
  - `[P2]` MUST NOT mark tasks complete with mock implementations, syntax errors, or unresolved `TODO` comments.

## 2. Priority Ranking & Precedence

Resolve directive conflicts using the strict canonical precedence hierarchy:

| Priority | Tier | Rules & Invariants |
| :---: | :--- | :--- |
| **`[P0]`** | **Security & Secrets Isolation** | Repository mutation containment (zero writes outside project, zero touching/inspecting host credentials `~/.ssh`/`~/.aws`), NEVER expose tokens, passwords, or commit unscrubbed credentials or copyrighted reference photos; prohibit destructive git operations. |
| **`[P1]`** | **Payload Invariants & Automated Contracts** | Single ADR diary (`docs/adr/decisions.md`), `NOTES.md` heading ban, strict typing (`pyright` strict, zero unchecked `Any`), deterministic `numpy` uint8 indexed framebuffer & binary alpha invariants, AST static guards, CLI and `manifest.json`/`manifest.d.ts` contracts in `.agent/NOTES.md`. |
| **`[P2]`** | **Architecture & Test Harness** | Domain logic separated from CLI entrypoint; canonical `uv run pytest` hermetic suite (`--disable-socket`); consultative dependencies and stable/LTS versioning. |
| **`[P3]`** | **Code Style & Complexity** | Concise single-purpose functions (heuristic <= 50 LOC; ~80 LOC acceptable for linear drawing/DTO/config mapping; refactor > 100 LOC or deep nesting) with low cognitive complexity; `ruff` formatting passes; Technical English for agent directives and commits. |

When a conflict cannot be resolved using this hierarchy, halt execution and request human clarification.

## 3. Modular Context Triggers

Optimize context consumption via progressive disclosure:

- **Default Context (Loaded on start):** Read `AGENTS.md`, `.agent/TASK.md`, and `.agent/NOTES.md` (Active Contracts only).
- **Architectural Decisions (`docs/adr/decisions.md`):** Canonical progressive disclosure diary; MUST load when creating new modules, researching historical trade-offs, or changing system boundaries. Prohibit separate `.agent/adr/` trees to prevent dual-source drift.
- **Product & Architecture Spec (`docs/DESIGN_V2.md`):** Canonical V2 Python (`build123d`-style) architecture, `numpy` indexed framebuffer contracts, compositional `Asset`/`Layer`/`Plane` API, AST guard rules, Svelte `manifest.d.ts` export, and CLI surface.
- **System Invariants (`.agent/INVARIANTS.md`):** Load when modifying rendering core, export pipelines, guard tests, or any UI/preview tooling (includes shared Invariant 7).
- **Domain Skills (`.agent/skills/<name>/SKILL.md`):** Load only when the active task touches that skill's trigger.
- **Hermetic Skills & Context Contract:** Procedural guidelines and skills must be self-contained within `.agent/skills/` or injected directly into the task dispatch prompt by the orchestrator. If a task references an external organizational skill not present in `.agent/skills/`, the agent must not wander the host filesystem; it should request the skill to be injected into the prompt or provisioned locally in `.agent/skills/`.
- **Interface & UI Verification:** Read `.agent/INVARIANTS.md` (Invariant 7) and `.agent/skills/interface-testing/SKILL.md` on-demand exclusively for browser/preview verification tasks.
- **Knowledge Base (`.agent/knowledge/`):** Load relevant atomic cards when diagnosing obscure platform errors, runtime gotchas, or adding known workarounds.

## 4. Mandatory Execution Protocol

### Step 1: Context Inspection
Read `AGENTS.md`, `.agent/TASK.md`, and `.agent/NOTES.md` before editing any project files.

### Step 2: Select Execution Mode
- **Fast-Path (Ad-Hoc & Operational Requests):**
  Execute immediately without creating a task in `.agent/TASK.md` or writing an implementation plan when the request:
  - Is an ad-hoc operational utility command (e.g., running `pixelforge render`, quick CLI inspection).
  - Is a trivial adjustment (e.g., fixing a typo, formatting, renaming a variable).
  - Is investigatory, conversational, or read-only (e.g., questions, diff review, visual inspection).
- **Plan-First Workflow (Tracked Roadmap Tasks):**
  Required for substantive architectural, feature, multi-file, or contract changes:
  - **Plan approval:** Present an action plan detailing affected files and tests, await explicit user approval, then execute the active task's `- [ ]` checklist in `.agent/TASK.md`.
  - **Tier 1 — Interactive (Default):** Lean `.agent/TASK.md` checklist (`- [ ]` atomic subtasks) validated by the canonical validation commands in Section 8. No `Status` state machine, `Type:`, `Read:`, `Paths:`, `[BATCH: Bx]`, or spec-anchor ceremony.
  - **Tier 2 — Autonomous (`dev-harness` / Parallel Worktrees):** Strict micro-contracts (`files_read`, `files_edit`, `verify`) live inside `.harness/queue/<id>.{md,yaml}` or `harness:ready` GitHub Issues consumed by `dev-harness`, never in `.agent/TASK.md`. Lifecycle hooks in `.agent/hooks/` (`post-worktree-create`, `pre-verify`, `post-worktree-teardown`) apply to both tiers.

### Step 3: Falsifiable Definition of Done (DoD)
A task MUST NOT be marked complete until all checks pass:
- [ ] Linter & Formatter: `uv run ruff check . && uv run ruff format --check .` exits with code 0.
- [ ] Strict Typing: `uv run pyright` exits with code 0.
- [ ] Automated Tests: `uv run pytest` exits with code 0 (hermetic unit + guard suite with `--disable-socket`).
- [ ] Git Cleanliness: `git diff --check` exits with code 0.
- [ ] Visual Verification (when asset modules or renderers change): Render `.contact.png` (and `.gif` when `frames > 1`), inspect visually for 1x readability, silhouette, palette compliance, and anchor alignment; do not commit generated `.pixelforge/` scratch artifacts.
- [ ] Interface & UI Verification (if UI affected): Pass the adaptive protocol in `.agent/skills/interface-testing/SKILL.md` and Invariant 7.
- [ ] Documentation Perimeter: If CLI flags, `.env.example` variables, manifest schemas, or validation commands changed, synchronize `README.md` and `README.pt-br.md` (zero heading emojis, Mermaid diagrams, falsifiable metrics).
- [ ] Knowledge Preservation: Document obscure platform/runtime gotchas or workarounds as an atomic card in `.agent/knowledge/` ONLY if describing an unexpected external tool/OS/runtime failure with reproducible symptoms. Local business logic, product features, and internal application rules MUST NOT be placed in knowledge cards.
- [ ] Atomic Commit: Conventional Commits in Technical English (`feat(scope): ...`).
- [ ] Task Log: Active task logged in `.agent/TASK.md` with commit hash; next task promoted.

## 5. Fail-Stop Protocol & Escalation Hierarchy (Circuit Breaker)

If an automated command (test, typecheck, lint, guard) fails **3 consecutive times** with the same root cause:
1. Halt execution immediately.
2. MUST NOT attempt unapproved speculative refactorings.
3. Escalate to the user with a structured diagnostic payload:
```yaml
failure_stage: "test | typecheck | lint | guard"
error_signature: "<exact error message>"
consecutive_failures: 3
root_cause_analysis: "<technical root cause>"
attempted_fixes:
  - "<attempt 1>"
  - "<attempt 2>"
  - "<attempt 3>"
pending_decision: "<clarification or choice required from human>"
```

## 6. Architecture & Dependency Governance

### Consultative Dependency & Architectural Trade-offs
When a non-trivial capability is required that is standardly addressed by established open-source libraries (for example, `numpy`, `pillow`, `pydantic`, CLI framework in `[00.1]`):
- MUST NOT silently invent complex in-house logic from scratch using stdlib to avoid asking.
- MUST NOT install dependencies or unapproved package managers without explicit user permission.
- Recommend the standard, battle-tested library in the implementation plan alongside a zero-dependency/stdlib alternative.
- Document trade-offs: maintenance burden, security attack surface, wheel/runtime size impact, and ecosystem maturity.
- Await explicit user decision before adding dependencies to `pyproject.toml`.

### Dependency & Runtime Versioning
When selecting libraries, frameworks, runtimes, or base images:
- **Default to Latest Stable / Greenfield Floor:** Python `>= 3.14` (managed via `uv`), `ruff >= 0.17`, `pyright >= 1.1.400`, `pytest >= 8.4`, `pydantic >= 2.11`.
- **Prohibit Pre-releases:** MUST NOT adopt `alpha`, `beta`, `rc`, `preview`, or `canary` releases unless explicitly requested by the user.
- **Prohibit Banned Packages:** Never add `httpx` (use `httpx2` if HTTP is ever needed), `respx`, `requests`, or Pydantic v1 APIs.
- **Verify Registry State:** Verify package versions via `uv` / PyPI rather than relying on model training cutoff assumptions.

### In-Code Invariants
MUST document non-obvious domain logic constraints, ordering dependencies, pixel-math quirks, and safety invariants as in-code comments using explicit invariant prefixes (`# INVARIANT: <rationale>`), explaining the architectural or domain *why* rather than restating the syntax.

## 7. Task Lifecycle & Numbering (`[XX.Y]`)

Format: `[Epic].[Sequence]` with two-digit epics. Exactly **one** active task in `.agent/TASK.md`.

| Prefix | Phase | Focus |
| :---: | :--- | :--- |
| **`00.x`** | Bootstrap & Setup | Python `uv` setup, `pyproject.toml`, `ruff`, `pyright`, `pytest`, CLI skeleton |
| **`01.x`** | Foundation & Engine | `numpy` uint8 framebuffer, PRNG, primitives, `build123d`-style `Asset`/`Layer`/`Plane` API |
| **`02.x`–`89.x`** | Epics | Exporter + Svelte `manifest.d.ts`, AST guards + CLI (`diff`/`watch`), `create-pixel-asset` v2 skill, pilot port, `analyze-ref` |
| **`90.x`** | Refactoring | Performance and technical debt |
| **`99.x`** | Hardening & Release | Audit and release tag — human approval required |

### Post-Release Hygiene (`vX.Y.Z`)
Triggered exclusively by human instruction to tag a release:
1. **Archive:** Move completed task log from `TASK.md` to `ARCHIVE.md` under `## [vX.Y.Z] - YYYY-MM-DD`.
2. **Consolidate:** Promote definitive architectural decisions to `docs/adr/decisions.md`; prune ephemeral scratch notes in `.agent/NOTES.md` preserving only active contracts.
3. **Perimeter:** Sync `.env.example`, `README.md`, and `README.pt-br.md` to the release tag.
4. **Reset:** Reset task numbering; promote next milestone to the active task; restore closing checklist in `TASK.md`.

## 8. Stack, Skills & Validation Contracts

### Stack
- **OS / shell:** `Bash` — use Bash syntax in terminal commands.
- **Architecture:** Single-package Python compiler + CLI (`src/pixelforge/{core,export,guard,cli}/`) with headless `numpy` + `Pillow` rendering and Svelte 5 `manifest.d.ts` codegen.
- **Runtime & Toolchain:** Python `>= 3.14`, `uv`, `ruff >= 0.17`, `pyright` (`strict`), `pytest` + `pytest-socket`.
- **Downstream Consumer:** Svelte 5 browser game consuming compiled PNGs, spritesheets, emissive masks, optional LUTs, `manifest.json`, and `manifest.d.ts` (live-reloaded via `pixelforge watch`).

### MCP (Model Context Protocol)
`none` (no project-specific MCP servers required for compiler CLI).

### Skills
Read `.agent/skills/<name>/SKILL.md` when a task matches the skill domain.

| Skill | Trigger |
| :--- | :--- |
| `create-pixel-asset` | Authoring or iterating on code-drawn pixel art modules (`assets/**/*.asset.py`) |
| `interface-testing` | Browser/preview verification tasks (combined with `.agent/INVARIANTS.md` Invariant 7) |

### Validation Commands
Run before marking any task complete (configured in `[00.1]`):

- Sync dependencies: `uv sync --frozen`
- Lint & format check: `uv run ruff check . && uv run ruff format --check .` (Exit code MUST be 0)
- Typecheck: `uv run pyright` (Exit code MUST be 0)
- Run tests: `uv run pytest` (Exit code MUST be 0, with `--disable-socket --allow-unix-socket`)

During **Task `[00.1]` (Python V2 Project Bootstrap & Toolchain Setup)**, initialize `pyproject.toml` with these exact canonical commands so every check exits with code 0. Adding new dependencies REQUIRES explicit user approval.

## 9. Git & Commit Standards

- **Atomic Commits:** Each commit MUST represent a single logical change.
- **Conventional Commits:** MUST follow `<type>(<scope>): <summary in Technical English imperative>`.
  - `feat`: new feature with automated test
  - `fix`: bug fix with regression test
  - `refactor`: structural change preserving behavior
  - `test`: test suite addition/update
  - `chore`: maintenance, dependencies, configs
  - `docs`: documentation only
- **No Agent Attribution Trailers:** NEVER append `Co-Authored-By`, `Generated with ...`, or similar AI/agent attribution trailers to commit messages or PR descriptions.
- **Language Invariant:** Author all agent-facing directives, contracts, skills, and logs (`AGENTS.md`, `.agent/*`) in Technical English.
- **Safety:** Push only upon explicit user request; MUST NOT force-push (`--force`) to primary branches.

## 10. Contrast Pairs

Functions SHOULD remain concise (heuristic <= 50 lines of code; ~80 lines acceptable for linear drawing, DTO, or config mapping; refactor when > 100 lines or > 2–3 levels of indentation using early returns and guard clauses) with low cognitive complexity. Purely declarative constructs (palette tables, ASCII sprite grids) are exempt from arbitrary line limits.

### Pixel Determinism & Palette Closure
```python
# BAD: stdlib random, raw hex strings, and fractional float coords
import random

color = "#ffd866" if random.random() > 0.5 else "#f85149"
surface.put(10.5, 4.2, color)

# GOOD: compositional layer, seeded PRNG, integer grid, and semantic palette tokens
# INVARIANT: Indexed writes guarantee zero mixels and lossless LUT swaps across states
spark_idx = P.SPARK_YELLOW if a.rng() > 0.5 else P.FAULT_RED
a.put(10, 4, spark_idx)
```

### Compositional Layers + Surgical Escape Hatch
```python
# BAD: repeating global coordinate offsets and manual bounds checks everywhere
for i in range(16):
    dx = 10 + int(rng() * 42)
    dy = 12 + int(rng() * 40)
    if surface.get(dx, dy) != 255:
        surface.put(dx, dy, P.DUST_LIGHT)

# GOOD: build123d-style layer/plane context + masked scatter + 1px surgical escape hatch
with a.layer("lid", outline=P.OUTLINE):
    with a.plane(p0=(22, 4), p1=(57, 13), p2=(17, 30)) as lid:
        lid.rect(0.0, 0.0, 1.0, 1.0, fill=P.SLATE_DARK)
a.scatter(count=16, colors=(P.DUST_LIGHT, P.DUST_DARK), mask="opaque")
a.put(31, 14, P.CYAN_GLOW)  # 1px surgical polish from contact-sheet ruler
```

### Architectural Separation
```python
# BAD: PNG encoding and AST walking inline inside CLI argument parsing
if args.command == "render":
    img = Image.fromarray(rgba, mode="RGBA")
    # ... 100 lines of rendering and manifest serialization inside cli/main.py

# GOOD: Thin CLI entrypoint delegating strictly typed domain services
if args.command == "render":
    bundle = export_asset_bundle(asset, style, options)
    write_export_bundle(bundle, out_dir)
```

### In-Code Invariants
```python
# BAD: Restating trivial syntax
# Fill buffer with 255
buf.fill(255)

# GOOD: Explaining non-obvious domain rationale
# INVARIANT: Index 255 is permanently reserved as binary transparent alpha (0); indices 0..254 map to active StylePack colors
buf.fill(TRANSPARENT_INDEX)
```

### Commit Messages
```markdown
// BAD: Appending AI/agent attribution trailers to commit messages or PR descriptions
git commit -m "feat(core): add Plane context manager" -m "Co-Authored-By: <Agent> <noreply@example.com>"

// GOOD: Clean commit message without attribution trailers
git commit -m "feat(core): add Plane context manager"
```
