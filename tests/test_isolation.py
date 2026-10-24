"""The agent side (oncall/, tools/) and the injector (dev/) must stay completely separate."""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DYNAMIC_IMPORTS = {"__import__", "import_module"}


def imported_roots(path: Path) -> set[str]:
    """Top-level names a Python file imports (absolute imports only), plus dynamic-import calls."""
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in DYNAMIC_IMPORTS:
                roots.add(f"<dynamic import in {path.name}>")
    return roots


def offenders(package_dirs: list[str], forbidden: set[str]) -> list[str]:
    found = []
    for package in package_dirs:
        for path in sorted((REPO / package).rglob("*.py")):
            bad = imported_roots(path) & forbidden
            bad |= {r for r in imported_roots(path) if r.startswith("<dynamic")}
            if bad:
                found.append(f"{path.relative_to(REPO)}: {sorted(bad)}")
    return found


def test_agent_side_never_imports_dev():
    assert offenders(["oncall", "tools"], {"dev"}) == []


def test_faultctl_never_imports_agent_side():
    assert offenders(["dev"], {"oncall", "tools"}) == []


# The flag service name and the flag UI path may appear in exactly one agent-side file.
SANITISER = REPO / "tools" / "sanitize.py"
FORBIDDEN_TEXT = ("flagd", "/feature")


def agent_side_files() -> list[Path]:
    return sorted(
        p for package in ("oncall", "tools") for p in (REPO / package).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".md", ".json", ".txt", ".yaml", ".yml", ".toml"}
    )


def test_only_the_sanitiser_names_the_flag_service_or_ui_path():
    leaks = [
        f"{p.relative_to(REPO)}: {word!r}"
        for p in agent_side_files() if p != SANITISER
        for word in FORBIDDEN_TEXT if word in p.read_text(encoding="utf-8").lower()
    ]
    assert leaks == []


def test_sanitiser_contains_no_url():
    text = SANITISER.read_text(encoding="utf-8")
    assert "://" not in text and "localhost" not in text
