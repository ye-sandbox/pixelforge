---
name: blind-critic
description: Unbiased, read-only multimodal visual critique of compiled pixel art contact sheets, diffs, and animated previews by a subagent without reading source asset code first.
---

# Blind Visual Critic (`pixelforge`)

## 1. Context and Objective

Authoring agents often suffer from confirmation bias because they know what they *intended* to draw in `.asset.py` or `.scene.py`. The **Blind Visual Critic** is a strictly read-only reviewer that evaluates only compiled visual artifacts (`.contact.png`, `.diff.png`, `.gif`) and optional public metadata (`SPEC` dimensions/states/anchors), without inspecting the drawing implementation beforehand.

---

## 2. When to Use (Triggers)

Activate this skill whenever:
- A visual review subagent is delegated to grade a newly authored or refactored pixel asset or scene.
- An asset passes `pixelforge check` and needs an objective second opinion on `1×` readability, lighting, silhouette, or animation cleanliness.
- A PR or diff modifies `assets/**/*.asset.py` or `styles/*.style.py` and requires unbiased regression review.

---

## 3. Associated Tools and MCP Servers

- **MCP Servers:** `None`
- **Allowed Artifacts (Read-Only):**
  - `.pixelforge/sheets/<id>.contact.png` (primary 1× dark/light strips, 4px-ruled zoomed panel, anchors, hitboxes, state/frame matrix, palette swatches)
  - `.pixelforge/previews/<id>_<state>.gif` (animated multi-frame preview when `frames > 1`)
  - `.pixelforge/diffs/<id>.diff.png` (when reviewing a change against a baseline)
- **Allowed CLI (Read-Only Diagnostics Only):**
  - `uv run pixelforge probe <asset_id> [--region x,y,w,h] [--state <name>] [--frame <n>] [--layers]` (to verify exact pixel coordinates or orphan pixels reported on the contact sheet)

---

## 4. Blind Review Protocol (Step-by-Step)

### Step 1: Enforce Blindness (Zero Source Leakage)
- **DO NOT** read `assets/**/*.asset.py`, `assets/**/*.scene.py`, or git diffs of drawing code before completing your visual evaluation.
- **DO NOT** modify any files in the repository.

### Step 2: Inspect Visual Artifacts
Inspect the provided `.contact.png` (and `.gif` / `.diff.png` if present) against the 5-criteria rubric:

1. **1× Silhouette & Readability (0–20):** Is the subject immediately recognizable at native `1×` resolution on both dark (`#0d1117`) and light (`#e6edf3`) checkerboards?
2. **Lighting Consistency (0–20):** Do highlights sit consistently on the lit side (typically `top-left`) and shadows on the opposite side (`bottom-right`), matching the asset's perspective?
3. **Pixel Cluster Cleanliness (0–20):** Are outlines continuous without broken corners, mixels, stray `1×1` orphan pixels, or unintended stair-stepping?
4. **State & Frame Legibility (0–20):** Are declared states (`healthy`, `dusty`, `faulty`, `day`, `night`, etc.) visually distinct, and do animation frames cycle smoothly without unintentional jitter?
5. **Anchor, Hitbox & Palette Discipline (0–20):** Do anchor crosshairs and hitbox rectangles land on their exact semantic features, and do emissive/bright highlights avoid bleeding into non-glowing painted surfaces?

### Step 3: Emit Structured Verdict
Return a concise, falsifiable review in this exact structure:

```yaml
verdict: "PASS | FAIL"
score: <0-100>
criteria:
  silhouette_1x: <0-20>
  lighting_consistency: <0-20>
  cluster_cleanliness: <0-20>
  state_frame_legibility: <0-20>
  anchors_and_palette: <0-20>
strengths:
  - "<observed visual strength>"
issues:
  - "<exact defect with (x, y) coordinates from the 4px contact-sheet ruler>"
fixes:
  - "<concrete coordinate or parametric adjustment for the author>"
```

- **PASS threshold:** `score >= 70` and zero critical readability/silhouette blockers.
- **FAIL:** `score < 70` or any critical silhouette/orphan/anchor misalignment defect.

---

## 5. Known Gotchas and Anti-Patterns

- **DO NOT** guess intent from filenames alone—if the `1×` sprite looks ambiguous on `#0d1117` or `#e6edf3`, report it as a silhouette/contrast failure.
- **DO NOT** give vague feedback like "looks a bit off"; always anchor issues to `(x, y)` coordinates read from the contact sheet's 4px ruler or specific `(state, frame)` cells.
- **DO NOT** edit files or run `pixelforge render` / `pixelforge check --sync-stubs`; report findings back to the authoring agent.
