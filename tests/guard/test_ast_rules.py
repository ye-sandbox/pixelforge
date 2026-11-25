"""Hermetic unit tests for AST static guard rules."""

from __future__ import annotations

from pathlib import Path

from pixelforge.guard.ast_rules import check_ast_source, infer_scope


def test_infer_scope() -> None:
    """Verify scope inference for asset, style, and core paths."""
    assert infer_scope(Path("assets/homelab/crate.asset.py")) == "asset"
    assert infer_scope(Path("styles/homelab_16bit.style.py")) == "style"
    assert infer_scope(Path("src/pixelforge/core/builder.py")) == "core"
    assert infer_scope(Path("src/pixelforge/cli/main.py")) is None


def test_no_stdlib_random_across_scopes() -> None:
    """Ban random, secrets, and numpy.random across asset, style, and core scopes."""
    bad_sources = [
        "import random\n",
        "import secrets\n",
        "from random import randint\n",
        "from numpy import random\n",
        "from numpy.random import default_rng\n",
        "import numpy as np\nx = np.random.randint(0, 5)\n",
    ]
    for scope in ("asset", "style", "core"):
        for src in bad_sources:
            violations = check_ast_source(src, "test.py", scope=scope)
            assert any(v.rule == "no-stdlib-random" for v in violations), (scope, src)


def test_no_external_assets() -> None:
    """Ban PIL/Image imports and raster/SVG path literals in asset modules."""
    bad = 'from PIL import Image\nimport PIL\nIMG = "textures/laptop.png"\nSVG = "icon.SVG"\n'
    violations = check_ast_source(bad, "assets/a.asset.py", scope="asset")
    ext = [v for v in violations if v.rule == "no-external-assets"]
    assert len(ext) == 4


def test_no_raw_hex_ignores_spr_grids() -> None:
    """Ban raw hex color literals in assets while allowing `spr()` ASCII grids."""
    src = 'def render(a):\n    bad = "#ff00aa"\n    a.spr(0, 0, ["..##..", "#abcdef"], {"#": 1})\n'
    violations = check_ast_source(src, "assets/a.asset.py", scope="asset")
    hex_violations = [v for v in violations if v.rule == "no-raw-hex"]
    assert len(hex_violations) == 1
    assert hex_violations[0].line == 2

    style_violations = check_ast_source('HEX = "#ff00aa"\n', "styles/s.style.py", scope="style")
    assert style_violations == []


def test_no_io_or_eval() -> None:
    """Ban filesystem I/O, clock access, and dynamic code execution in asset modules."""
    bad = (
        "import os\n"
        "import pathlib\n"
        "import subprocess\n"
        "import time\n"
        "from datetime import datetime\n"
        'f = open("secret.txt")\n'
        'x = eval("1 + 1")\n'
        'exec("pass")\n'
    )
    violations = check_ast_source(bad, "assets/a.asset.py", scope="asset")
    io_violations = [v for v in violations if v.rule == "no-io-or-eval"]
    assert len(io_violations) == 8


def test_syntax_error_reported_cleanly() -> None:
    """Report Python syntax errors as structured guard violations."""
    violations = check_ast_source("def broken(:\n    pass\n", "assets/broken.asset.py")
    assert len(violations) == 1
    assert violations[0].rule == "syntax-error"
