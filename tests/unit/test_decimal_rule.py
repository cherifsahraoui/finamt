"""
tests/unit/test_decimal_rule.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Guard: money in src/finamt/tax/ is Decimal only.

Fails if any tax module uses the name ``float`` (calls, annotations) or a float
literal. Use ``Decimal("0.19")``, never ``0.19``. Format with f-strings, not float().
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TAX_DIR = Path(__file__).resolve().parents[2] / "src" / "finamt" / "tax"
TAX_FILES = sorted(TAX_DIR.glob("*.py"))


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "float":
            found.append(f"{path.name}:{node.lineno} uses 'float'")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            found.append(f"{path.name}:{node.lineno} float literal {node.value!r}")
    return found


def test_tax_dir_found():
    assert TAX_FILES, f"no modules found in {TAX_DIR}"


@pytest.mark.parametrize("path", TAX_FILES, ids=lambda p: p.name)
def test_no_float_in_tax_code(path):
    assert _violations(path) == []
