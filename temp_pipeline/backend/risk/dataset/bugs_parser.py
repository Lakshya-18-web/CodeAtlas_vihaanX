from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass(frozen=True)
class BugInfo:
    project: str
    bug_id: str
    buggy_commit: str
    fixed_commit: str
    github_url: str = ""
    test_file: str = ""


def parse_kv_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def load_bug_info(bugsinpy_root: Path, project: str, bug_id: str) -> BugInfo:
    info_path = (
        bugsinpy_root / "projects" / project / "bugs" / str(bug_id) / "bug.info"
    )
    if not info_path.exists():
        raise FileNotFoundError(f"Missing bug.info: {info_path}")

    data = parse_kv_file(info_path)
    buggy = data.get("buggy_commit_id", "")
    fixed = data.get("fixed_commit_id", "")
    if not buggy or not fixed:
        raise ValueError(f"bug.info missing commit ids: {info_path}")

    return BugInfo(
        project=project,
        bug_id=str(bug_id),
        buggy_commit=buggy,
        fixed_commit=fixed,
        github_url=data.get("github_url", ""),
        test_file=data.get("test_file", ""),
    )


def discover_projects(bugsinpy_root: Path):
    root = bugsinpy_root / "projects"
    if not root.exists():
        raise FileNotFoundError(f"BugsInPy projects directory not found: {root}")
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def discover_bugs(bugsinpy_root: Path, project: str):
    root = bugsinpy_root / "projects" / project / "bugs"
    if not root.exists():
        return []
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and p.name.isdigit()
    )
