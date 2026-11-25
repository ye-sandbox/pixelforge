"""AST-based static guard rules for pixel determinism and palette closure."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final, Literal

from pixelforge.guard.types import GuardViolation

GuardScope = Literal["asset", "style", "core"]

_HEX_COLOR_RE: Final[re.Pattern[str]] = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")
_EXTERNAL_ASSET_RE: Final[re.Pattern[str]] = re.compile(
    r"\.(?:png|jpe?g|webp|svg|gif|bmp|ico)(?:$|[?#\"'\s])",
    re.IGNORECASE,
)

_BANNED_RANDOM_MODULES: Final[frozenset[str]] = frozenset({"random", "secrets", "numpy.random"})
_BANNED_EXTERNAL_IMPORTS: Final[frozenset[str]] = frozenset({"PIL", "Image"})
_BANNED_IO_MODULES: Final[frozenset[str]] = frozenset(
    {
        "os",
        "sys",
        "pathlib",
        "subprocess",
        "time",
        "datetime",
        "io",
        "importlib",
        "shutil",
        "tempfile",
        "socket",
        "urllib",
        "http",
        "builtins",
    }
)
_BANNED_IO_CALLS: Final[frozenset[str]] = frozenset(
    {"open", "eval", "exec", "__import__", "compile"}
)
_BANNED_BUILTIN_ATTR_BASES: Final[frozenset[str]] = frozenset({"builtins", "__builtins__"})


def infer_scope(path: Path) -> GuardScope | None:
    """Infer the guard scope from a file path, or return `None` if outside guarded trees."""
    parts = path.as_posix().split("/")
    if path.name.endswith(".asset.py") or "assets" in parts:
        return "asset"
    if path.name.endswith(".style.py") or "styles" in parts:
        return "style"
    if "core" in parts and "pixelforge" in parts:
        return "core"
    return None


def _is_spr_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "spr"
    if isinstance(func, ast.Attribute):
        return func.attr == "spr"
    return False


class _AstGuardVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, scope: GuardScope) -> None:
        self.file_path = file_path
        self.scope = scope
        self.violations: list[GuardViolation] = []
        self._numpy_aliases: set[str] = {"numpy"}
        self._in_spr_call = 0

    def _add(self, node: ast.AST, rule: str, detail: str) -> None:
        line = getattr(node, "lineno", 1)
        col = getattr(node, "col_offset", 0)
        self.violations.append(
            GuardViolation(
                file=self.file_path,
                line=line,
                col=col,
                rule=rule,
                detail=detail,
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if alias.name == "numpy" and alias.asname:
                self._numpy_aliases.add(alias.asname)

            if alias.name in _BANNED_RANDOM_MODULES or root in {"random", "secrets"}:
                self._add(
                    node,
                    "no-stdlib-random",
                    f"Banned non-deterministic import {alias.name!r}; use Asset.rng() / mulberry32",
                )
            if self.scope == "asset":
                if root in _BANNED_EXTERNAL_IMPORTS:
                    self._add(
                        node,
                        "no-external-assets",
                        f"Banned image library import {alias.name!r} inside asset module",
                    )
                if root in _BANNED_IO_MODULES:
                    self._add(
                        node,
                        "no-io-or-eval",
                        f"Banned I/O or clock module {alias.name!r} inside asset module",
                    )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        root = module.split(".")[0]
        imported_names = {alias.name for alias in node.names}

        if module in _BANNED_RANDOM_MODULES or root in {"random", "secrets"}:
            self._add(
                node,
                "no-stdlib-random",
                f"Banned non-deterministic import from {module!r}; use Asset.rng() / mulberry32",
            )
        elif root == "numpy" and "random" in imported_names:
            self._add(
                node,
                "no-stdlib-random",
                "Banned import 'from numpy import random'; use Asset.rng() / mulberry32",
            )

        if self.scope == "asset":
            if root in _BANNED_EXTERNAL_IMPORTS or (
                module == "" and bool(imported_names & _BANNED_EXTERNAL_IMPORTS)
            ):
                self._add(
                    node,
                    "no-external-assets",
                    f"Banned image library import from {module or '.'!r} inside asset module",
                )
            if root in _BANNED_IO_MODULES:
                self._add(
                    node,
                    "no-io-or-eval",
                    f"Banned I/O or clock import from {module!r} inside asset module",
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            node.attr == "random"
            and isinstance(node.value, ast.Name)
            and node.value.id in self._numpy_aliases
        ):
            self._add(
                node,
                "no-stdlib-random",
                f"Banned {node.value.id}.random access; use Asset.rng() / mulberry32",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.scope == "asset":
            if isinstance(node.func, ast.Name) and node.func.id in _BANNED_IO_CALLS:
                self._add(
                    node,
                    "no-io-or-eval",
                    f"Banned call {node.func.id}() inside asset module",
                )
            elif (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in _BANNED_BUILTIN_ATTR_BASES
            ):
                self._add(
                    node,
                    "no-io-or-eval",
                    f"Banned call {node.func.value.id}.{node.func.attr}() inside asset module",
                )

        if _is_spr_call(node):
            self._in_spr_call += 1
            try:
                self.generic_visit(node)
            finally:
                self._in_spr_call -= 1
            return

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if self.scope != "asset" or not isinstance(node.value, str):
            return

        val = node.value.strip()
        if _EXTERNAL_ASSET_RE.search(val):
            self._add(
                node,
                "no-external-assets",
                f"External raster/SVG reference {val!r} is forbidden inside asset modules",
            )
        # INVARIANT: String literals inside `spr(...)` calls are ASCII sprite grids/key maps
        # and are excluded from raw hex color detection to prevent false positives.
        if self._in_spr_call == 0 and _HEX_COLOR_RE.match(val):
            self._add(
                node,
                "no-raw-hex",
                f"Raw hex literal {val!r} is forbidden in assets; use StylePack tokens",
            )


def check_ast_source(
    source: str,
    file_path: str,
    *,
    scope: GuardScope = "asset",
) -> list[GuardViolation]:
    """Run AST static guard rules against Python source code."""
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        return [
            GuardViolation(
                file=file_path,
                line=exc.lineno or 1,
                col=exc.offset or 0,
                rule="syntax-error",
                detail=exc.msg,
            )
        ]

    visitor = _AstGuardVisitor(file_path, scope)
    visitor.visit(tree)
    return visitor.violations


def check_ast_file(path: Path, *, scope: GuardScope | None = None) -> list[GuardViolation]:
    """Read a Python file and run AST static guard rules for its scope."""
    resolved_scope = scope or infer_scope(path) or "asset"
    source = path.read_text(encoding="utf-8")
    return check_ast_source(source, str(path), scope=resolved_scope)
