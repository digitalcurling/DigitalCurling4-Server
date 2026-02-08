import sys
from pathlib import Path


def pytest_configure() -> None:
    # Ensure repository root is on sys.path so `import src...` works when running pytest
    # without installing the package.
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
