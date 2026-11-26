# Multimodal Visual Critic Loop & `pixelforge critic`

## 1. Manual Multimodal Visual Critic Loop (2–4 Surgical Passes Max)

After `uv run pixelforge check <asset_id>` passes, render the contact sheet and animated previews:

```bash
uv run pixelforge render <asset_id> --sheet --animate --emissive
```

Inspect `.pixelforge/sheets/<asset_id>.contact.png` (and `.pixelforge/previews/<asset_id>_<state>.gif` when `frames > 1`) against five criteria:

1. **1× Silhouette & Readability:** Is the object immediately recognizable at `1×` on both dark (`#0d1117`) and light (`#e6edf3`) checkerboards?
2. **Lighting Consistency:** Do highlights sit on `top-left` edges and shadows on `bottom-right` edges (matching `style.lighting_angle`)?
3. **Pixel Cluster Cleanliness:** Are there stray `1×1` orphan pixels, broken outlines, or unintentional stair-stepping?
4. **State & Frame Legibility:** Are states (`healthy`/`dusty`/`faulty` or `day`/`night`) clearly distinguishable, and do animation frames (`frame 0` vs `frame 1`) change cleanly without jitter?
5. **Anchor & Hitbox Alignment:** Do the crosshairs and bounding boxes on the zoomed panel land on the exact intended pixel features?

**Surgical Refinement:**
- Read exact `(x, y)` coordinates from the contact sheet's every-4px ruler.
- Apply targeted coordinate or parametric edits in `assets/<pack>/<id>.asset.py`.
- Re-run `uv run pixelforge check <asset_id> && uv run pixelforge render <asset_id> --sheet --animate --emissive`.
- Optionally verify minimal pixel deltas with `uv run pixelforge diff <asset_id> --base HEAD`.
- Repeat for **2–4 passes maximum**. Never commit `.pixelforge/` scratch artifacts.

---

## 2. Automated Multimodal Critic (`pixelforge critic`)

Score one asset, all assets, or only git-changed assets via an OpenAI v1 multimodal endpoint (e.g., `hydra-llm-router`):

```bash
# Score a single asset (threshold default: 70)
uv run pixelforge critic <asset_id> --threshold 75

# Score only assets/styles modified since HEAD with diff context
uv run pixelforge critic --base HEAD --threshold 70

# Emit strict JSON for CI pipelines
uv run pixelforge critic --base HEAD --json
```

### Configuration (`.env` / Environment Variables)
- `LLM_BASE_URL`: OpenAI v1 gateway endpoint (default: `http://127.0.0.1:3000/v1`)
- `LLM_API_KEY`: Gateway bearer token
- `LLM_MODEL_FAST`: Multimodal vision model / virtual model (default: `fast`)
- `LLM_TIMEOUT_SECONDS`: Request timeout in seconds (default: `30`)

### Interpreting Output
- Exit `0`: All scored assets meet `--threshold` (or zero changed assets when `--base` is set).
- Exit `1`: One or more assets scored below `--threshold`, or gateway/config error occurred.
- Use the returned `strengths`, `issues`, and `fixes` to apply surgical coordinate edits, then re-check and re-score.
