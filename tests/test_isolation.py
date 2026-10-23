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
