"""CLN-2: every name in ``finamt.__all__`` is importable."""

import importlib


def test_star_import_works():
    namespace: dict = {}
    exec("from finamt import *", namespace)  # raised AttributeError before CLN-2
    pkg = importlib.import_module("finamt")
    for name in pkg.__all__:
        assert name in namespace, name
