"""Smoke tests for pixelforge v2 bootstrap and CLI entrypoint."""

from __future__ import annotations

import numpy as np
import PIL
import pydantic
import pydantic_settings
import pytest

import pixelforge
from pixelforge.cli.main import main


def test_package_version() -> None:
    """Verify the package version string is exposed."""
    assert pixelforge.__version__ == "0.2.0"


def test_core_dependencies_importable() -> None:
    """Verify approved runtime dependencies are installed and importable."""
    assert np.__version__
    assert PIL.__version__
    assert pydantic.__version__
    assert pydantic_settings.__version__


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `pixelforge --help` prints usage and exits cleanly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "pixelforge" in captured.out


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `pixelforge --version` prints the package version and exits cleanly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert f"pixelforge {pixelforge.__version__}" in captured.out
