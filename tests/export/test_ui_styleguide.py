"""Hermetic unit tests for `generate_ui_styleguide_sheet` and `UI_THEME_PRESETS`."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pixelforge.core.prefabs.ui import UI_THEME_NAMES, UiThemeName, get_ui_theme_config
from pixelforge.export.ui_styleguide import (
    UI_STYLEGUIDE_SECTIONS,
    UiStyleguideOptions,
    generate_ui_styleguide_sheet,
)
from pixelforge.presets import load_preset_style


@pytest.mark.parametrize("theme", UI_THEME_NAMES)
def test_generate_ui_styleguide_sheet_all_themes(theme: UiThemeName) -> None:
    """Every UI theme preset must render a valid comparative styleguide PNG."""
    style = load_preset_style("sweetie-16")
    result = generate_ui_styleguide_sheet(style, UiStyleguideOptions(theme=theme, zoom=2))

    assert result.theme == theme
    assert result.style_id == "sweetie-16"
    assert result.sections == UI_STYLEGUIDE_SECTIONS
    assert result.width > 200
    assert result.height > 150
    assert result.rgba.shape == (result.height, result.width, 4)
    assert result.png.startswith(b"\x89PNG\r\n\x1a\n")

    with Image.open(io.BytesIO(result.png)) as img:
        assert img.size == (result.width, result.height)
        assert img.mode == "RGBA"


def test_ui_styleguide_zoom_and_invalid_inputs() -> None:
    """Verify integer zoom scaling and error handling for invalid theme/zoom."""
    style = load_preset_style("scifi-neon")
    res_1x = generate_ui_styleguide_sheet(style, UiStyleguideOptions(theme="flat_crt", zoom=1))
    res_3x = generate_ui_styleguide_sheet(style, UiStyleguideOptions(theme="flat_crt", zoom=3))
    assert res_3x.width > res_1x.width
    assert res_3x.height > res_1x.height

    with pytest.raises(ValueError, match="Unknown UI theme"):
        get_ui_theme_config("nonexistent_theme")

    with pytest.raises(ValueError, match="zoom must be >= 1"):
        generate_ui_styleguide_sheet(style, UiStyleguideOptions(zoom=0))
