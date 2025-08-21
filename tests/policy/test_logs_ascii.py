import ast
import pathlib
import re

LOG_CALLS = {"debug", "info", "warning", "error", "exception", "critical"}
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF]")


def iter_log_strs(tree):
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in LOG_CALLS
        ):
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    yield a.value


def test_no_emoji_in_log_literals():
    for py in pathlib.Path("app").rglob("*.py"):
        t = ast.parse(py.read_text(encoding="utf-8"))
        for s in iter_log_strs(t):
            assert not EMOJI.search(s), f"Emoji in log string: {py}: {s!r}"


def test_ascii_only_log_literals():
    for py in pathlib.Path("app").rglob("*.py"):
        t = ast.parse(py.read_text(encoding="utf-8"))
        for s in iter_log_strs(t):
            try:
                s.encode("ascii")
            except UnicodeEncodeError as e:
                raise AssertionError(f"Non-ASCII log string: {py}: {s!r}") from e
