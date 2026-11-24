# Agent Guidelines and Rules — pixelforge

You are the lead software engineer developing this project: **pixelforge** (Code-Drawn Indexed Pixel Art Engine, CLI/SDK, and Multimodal Agent Visual Critic Loop).

> **Greenfield** baseline: explicit contracts, formal ADRs, strict typing, deterministic indexed framebuffers, and falsifiable visual/guard verification.

## 1. Scope & Blast Radius

- **MUTATION BOUNDARY:**
  - All file mutations (creates, edits, deletes) MUST be strictly contained within this project repository.
  - Writing outside the project directory or touching/inspecting host credentials (`~/.ssh`, `~/.aws`, auth tokens, host dotfiles) is strictly forbidden.
- **MUTABLE PATHS:**
  - Project source code (`src/**`), style packs (`styles/**`), pilot/sample assets (`assets/**`), tests (`tests/**`), documentation (`docs/**`), and configuration files.
  - `AGENTS.md`, `.agent/TASK.md`, `.agent/NOTES.md`, `.agent/ARCHIVE.md`, `.agent/INVARIANTS.md`, `.agent/skills/**`, `docs/adr/decisions.md`.
- **IMMUTABLE PATHS:**
  - `.env` files, production credentials, and private tokens.
  - Host credentials and environments (`~/.ssh`, `~/.aws`, auth tokens, host dotfiles).
- **FORBIDDEN ACTIONS:**
  - `[P0]` MUST NOT mutate files outside this project repository (writing outside the project directory is strictly forbidden).
  - `[P0]` MUST NOT touch or inspect host credentials (`~/.ssh`, `~/.aws`, auth tokens, host dotfiles).
  - `[P0]` MUST NOT expose tokens, passwords, or commit unscrubbed credentials.
  - `[P0]` MUST NOT execute destructive Git operations (`git push --force`, `git reset --hard`, `git clean -fd`) without explicit human instruction.
  - `[P0]` MUST NOT commit reference photographs or copyrighted third-party images into the repository.
  - `[P1]` MUST NOT use loose typing (`any`). All interfaces, palettes, surfaces, manifests, and return types MUST be explicitly typed.
  - `[P1]` MUST NOT break payload, manifest, or CLI contracts documented in `.agent/NOTES.md` or `docs/DESIGN_MVP.md`.
  - `[P1]` MUST NOT create task-specific headings (`## [Task XX.Y]`) in `.agent/NOTES.md`. Task completion history belongs in `git log` and `.agent/ARCHIVE.md`. Architectural decisions belong in `docs/adr/decisions.md`.
  - `[P1]` MUST NOT create separate `.agent/adr/` directories or individual ADR files. All decisions MUST append to `docs/adr/decisions.md`.
  - `[P1]` MUST NOT use `Math.random()` inside pixel asset modules, palettes, or rendering primitives (seeded deterministic PRNG only).
  - `[P2]` MUST NOT place core rendering or guard logic inside CLI argument parsing handlers; domain logic MUST reside in `src/core/`, `src/export/`, and `src/guard/`.
  - `[P2]` MUST NOT invent ad-hoc test compilation loops, dynamic eval imports, or inline bundler scripts to bypass a missing test runner. The test suite MUST run via the project's canonical test command (`pnpm test`).
  - `[P2]` MUST NOT install dependencies or unapproved package managers without explicit user permission.
  - `[P2]` MUST NOT mark tasks complete with mock implementations, syntax errors, or unresolved `TODO` comments.

## 2. Priority Ranking & Precedence

Resolve directive conflicts using the strict canonical precedence hierarchy:

| Priority | Tier | Rules & Invariants |
| :---: | :--- | :--- |
| **`[P0]`** | **Security & Secrets Isolation** | Repository mutation containment (zero writes outside project, zero touching/inspecting host credentials `~/.ssh`/`~/.aws`), NEVER expose tokens, passwords, or commit unscrubbed credentials or copyrighted reference photos; prohibit destructive git operations. |
| **`[P1]`** | **Payload Invariants & Automated Contracts** | Single ADR diary (`docs/adr/decisions.md`), `NOTES.md` heading ban, strict typing (zero unchecked `any`), deterministic indexed framebuffer & binary alpha invariants, CLI and `manifest.json` contracts in `.agent/NOTES.md`. |
| **`[P2]`** | **Architecture & Test Harness** | Domain logic separated from CLI entrypoint; canonical test runner (`pnpm test`); consultative dependencies and stable/LTS versioning. |
| **`[P3]`** | **Code Style & Complexity** | Concise single-purpose functions (heuristic <= 50 LOC; ~80 LOC acceptable for linear drawing/DTO/config mapping; refactor > 100 LOC or deep nesting) with low cognitive complexity; formatters pass; Technical English for agent directives and commits. |

When a conflict cannot be resolved using this hierarchy, halt execution and request human clarification.

## 3. Modular Context Triggers

Optimize context consumption via progressive disclosure:

- **Default Context (Loaded on start):** Read `AGENTS.md`, `.agent/TASK.md`, and `.agent/NOTES.md` (Active Contracts only).
- **Architectural Decisions (`docs/adr/decisions.md`):** Canonical progressive disclosure diary; MUST load when creating new modules, researching historical trade-offs, or changing system boundaries. Prohibit separate `.agent/adr/` trees to prevent dual-source drift.
- **Product & Architecture Spec (`docs/DESIGN_MVP.md`):** Canonical MVP design, indexed framebuffer contracts, palette semantics, contact sheet layout, guard rules, CLI surface, and `homelab-16bit` pilot benchmark.
- **System Invariants (`.agent/INVARIANTS.md`):** Load when modifying rendering core, export pipelines, guard tests, or any UI/preview tooling (includes shared Invariant 7).
- **Domain Skills (`.agent/skills/<name>/SKILL.md`):** Load only when the active task touches that skill's trigger.
- **Hermetic Skills & Context Contract:** Procedural guidelines and skills must be self-contained within `.agent/skills/` or injected directly into the task dispatch prompt by the orchestrator. If a task references an external organizational skill not present in `.agent/skills/`, the agent must not wander the host filesystem; it should request the skill to be injected into the prompt or provisioned locally in `.agent/skills/`.
- **Interface & UI Verification:** Read `.agent/INVARIANTS.md` (Invariant 7) and `.agent/skills/interface-testing/SKILL.md` on-demand exclusively for UI, preview, or Phase 2 Web Studio tasks.
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
- [ ] Strict Typing: `pnpm typecheck` exits with code 0.
- [ ] Automated Tests: `pnpm test` exits with code 0 (hermetic unit tests and guard suite).
- [ ] Linters: `pnpm lint` exits with code 0.
- [ ] Build: `pnpm build` exits with code 0.
- [ ] Git Cleanliness: `git diff --check` exits with code 0.
- [ ] Visual Verification (when asset modules or renderers change): Render `.contact.png`, inspect visually for 1x readability, silhouette, palette compliance, and anchor alignment; do not commit generated `.pixelforge/` scratch contact sheets.
- [ ] Interface & UI Verification (if UI affected): Pass the adaptive protocol in `.agent/skills/interface-testing/SKILL.md` and Invariant 7 — interactive preview/device MCPs within T3 Code; non-blocking headless component/build validation outside T3 Code.
- [ ] Documentation Perimeter: If CLI flags, `.env.example` variables, manifest schemas, or validation commands changed, synchronize `README.md` and `README.pt-br.md` (zero heading emojis, Mermaid diagrams, falsifiable metrics).
- [ ] Knowledge Preservation: Document obscure platform/runtime gotchas or workarounds as an atomic card in `.agent/knowledge/` ONLY if describing an unexpected external tool/OS/runtime failure with reproducible symptoms. Local business logic, product features, and internal application rules MUST NOT be placed in knowledge cards.
- [ ] Atomic Commit: Conventional Commits in Technical English (`feat(scope): ...`).
- [ ] Task Log: Active task logged in `.agent/TASK.md` with commit hash; next task promoted.

## 5. Fail-Stop Protocol & Escalation Hierarchy (Circuit Breaker)

If an automated command (test, build, typecheck, lint) fails **3 consecutive times** with the same root cause:
1. Halt execution immediately.
2. MUST NOT attempt unapproved speculative refactorings.
3. Escalate to the user with a structured diagnostic payload:
```yaml
failure_stage: "test | typecheck | lint | build | guard"
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
When a non-trivial capability is required that is standardly addressed by established open-source libraries (for example, PNG encoding in `[00.1]` / `[01.2]`):
- MUST NOT silently invent complex in-house logic from scratch using stdlib to avoid asking.
- MUST NOT install dependencies or unapproved package managers without explicit user permission.
- Recommend the standard, battle-tested library in the implementation plan alongside a zero-dependency/stdlib alternative.
- Document trade-offs: maintenance burden, security attack surface, bundle/binary size impact, and ecosystem maturity.
- Await explicit user decision before adding dependencies to `package.json`.

### Dependency & Runtime Versioning
When selecting libraries, frameworks, runtimes, or base images:
- **Default to Latest Stable / LTS:** Select the newest generally available (GA) stable release as of the current date, favoring active LTS versions for foundational runtimes (Node.js 26 Active LTS; floor 24).
- **Prohibit Pre-releases:** MUST NOT adopt `alpha`, `beta`, `rc`, `preview`, or `canary` releases unless explicitly requested by the user.
- **Preserve Compatibility:** Existing peer dependencies and project invariants take precedence over latest major versions.
- **Verify Registry State:** Use official CLI commands (`pnpm view <pkg> version`) rather than relying on model training cutoff assumptions.

### In-Code Invariants
MUST document non-obvious domain logic constraints, ordering dependencies, pixel-math quirks, and safety invariants as in-code comments using explicit invariant prefixes (`// INVARIANT: <rationale>`), explaining the architectural or domain *why* rather than restating the syntax.

## 7. Task Lifecycle & Numbering (`[XX.Y]`)

Format: `[Epic].[Sequence]` with two-digit epics. Exactly **one** active task in `.agent/TASK.md`.

| Prefix | Phase | Focus |
| :---: | :--- | :--- |
| **`00.x`** | Bootstrap & Setup | Stack selection, test harness setup, linters, types, CLI skeleton |
| **`01.x`** | Foundation & Engine | Indexed framebuffer core, semantic palettes, PNG/spritesheet/contact-sheet exporter |
| **`02.x`–`89.x`** | Epics | Guard runner, CLI commands, agent skill (`create-pixel-asset`), pilot asset packs, Phase 2 Web Studio |
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
- **Architecture:** Single-package TypeScript engine + CLI (`src/core/`, `src/export/`, `src/guard/`, `src/cli/`) with headless Node-native PNG and contact-sheet rendering.
- **Runtime & Toolchain:** Node.js 26 Active LTS (floor 24), `pnpm`, TypeScript (`strict: true`), Vitest (hermetic unit + guard tests), ESLint flat + Prettier (or Biome, finalized in `[00.1]`).
- **Phase 2 (Optional Web Studio):** Svelte 5 (Runes) + Tailwind v4 + WebGL2 post-processing preview (deferred until CLI + Agent Visual Critic Loop passes the `[03.1]` pilot benchmark).

### MCP (Model Context Protocol)
`none` (no project-specific MCP servers required for MVP).

### Skills
Read `.agent/skills/<name>/SKILL.md` when a task matches the skill domain.

| Skill | Trigger |
| :--- | :--- |
| `create-pixel-asset` | Authoring or iterating on code-drawn pixel art modules (`assets/**/*.asset.ts`) |
| `interface-testing` | Phase 2 Web Studio UI, preview, or frontend component tasks (combined with `.agent/INVARIANTS.md` Invariant 7) |

### Validation Commands
Run before marking any task complete (configured in `[00.1]`):

- Sync dependencies: `pnpm install --frozen-lockfile`
- Run tests: `pnpm test` (Exit code MUST be 0)
- Typecheck: `pnpm typecheck` (Exit code MUST be 0)
- Lint / format: `pnpm lint` (Exit code MUST be 0)
- Build: `pnpm build` (Exit code MUST be 0)

During **Task `[00.1]` (Project Bootstrap & Toolchain Setup)**, initialize `package.json` with these exact canonical commands so every check exits with code 0. Adding new dependencies REQUIRES explicit user approval.

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
```typescript
// BAD: Non-deterministic randomness and raw RGB strings bypassing the indexed palette
const sparkle = Math.random() > 0.5 ? '#ffd866' : '#f85149';
ctx.fillStyle = sparkle;
ctx.fillRect(x, y, 1.5, 1.5); // fractional coordinates create anti-aliased mixels

// GOOD: Seeded PRNG, integer pixel coordinates, and semantic palette indices
// INVARIANT: Indexed writes guarantee zero mixels and lossless LUT swaps across states
const sparkleIdx = rng() > 0.5 ? PAL.SPARK : PAL.FAULT_RED;
surface.put(x, y, sparkleIdx);
```

### Architectural Separation
```typescript
// BAD: PNG encoding and palette math inline inside CLI argument parsing
if (cmd === 'render') {
  const rgba = new Uint8Array(w * h * 4);
  // ... 120 lines of rendering and PNG header encoding inside bin/cli.ts
}

// GOOD: Thin CLI entrypoint delegating strictly typed domain services
if (cmd === 'render') {
  const result = await renderAssetBundle(assetModule, stylePack, options);
  await writeExportBundle(result, options.outDir);
}
```

### Test Harness Configuration
```typescript
// BAD: Ad-hoc inline bundler or eval scripts to bypass the canonical test runner
import esbuild from 'esbuild';
const mod = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);

// GOOD: Canonical Vitest suite invoked via pnpm test
import { describe, expect, it } from 'vitest';
import { createSurface } from '../src/core/surface.js';
```

### In-Code Invariants
```typescript
// BAD: Restating trivial syntax
// Set transparent pixel to 255
buf.fill(255);

// GOOD: Explaining non-obvious domain rationale
// INVARIANT: Index 255 is permanently reserved as binary transparent alpha (0); indices 0..254 map to active StylePack colors
buf.fill(TRANSPARENT_INDEX);
```

### Commit Messages
```markdown
// BAD: Appending AI/agent attribution trailers to commit messages or PR descriptions
git commit -m "feat(core): add isometric box primitive" -m "Co-Authored-By: <Agent> <noreply@example.com>"

// GOOD: Clean commit message without attribution trailers
git commit -m "feat(core): add isometric box primitive"
```

### Task Tracking (Tier 1 vs Tier 2)
```markdown
// BAD: Orchestration ceremony inside the interactive checklist
### [01.1] Core framebuffer engine
- Status: APPROVED | Type: code | Read: .agent/scratch/specs/01-01.md | Paths: src/core/surface.ts | Verify: pnpm test

// GOOD: Lean Tier 1 checklist; micro-contract lives in .harness/queue/01-01.yaml for dev-harness
### [01.1] Core framebuffer engine
Objective: implement indexed Uint8Array surface and seeded primitives.
- [ ] Add `IndexedSurface` and `StylePack` types
- [ ] Add deterministic unit tests (`pnpm test` exits 0)
```
