import pathlib
import re

BAD = re.compile(r"^\s*(#.*\n)*\s*(pass|...|raise NotImplementedError)\s*$", re.DOTALL)


def test_no_empty_stub_files():
    for p in pathlib.Path("app").rglob("*.py"):
        if p.name == "__init__.py":
            continue
        text = p.read_text(encoding="utf-8")
        assert not BAD.match(text), f"Empty stub file: {p}"
