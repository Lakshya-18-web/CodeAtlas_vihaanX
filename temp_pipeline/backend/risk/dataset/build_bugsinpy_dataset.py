from __future__ import annotations

import argparse
import csv
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

from backend.risk.dataset.bugs_parser import discover_bugs, discover_projects, load_bug_info
from backend.risk.dataset.codeatlas_features import FEATURES, analyze_with_features
from backend.risk.dataset.function_mapper import map_bug_to_functions

COLUMNS = [
    "sample_id", "repository", "bug_id", "commit", "file", "function", *FEATURES, "label"
]


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def checkout_commit(git_url: str, commit: str, destination: Path):
    run(["git", "clone", "--no-checkout", git_url, str(destination)])
    run(["git", "checkout", "--detach", commit], cwd=destination)


def sample_negatives(rows: List[Dict], positives: set, rng: random.Random, ratio: int):
    candidates = [r for r in rows if (r["file"], r["function"]) not in positives]
    count = min(len(candidates), max(1, len(positives) * ratio)) if positives else 0
    return rng.sample(candidates, count) if count else []


def process_bug(bugsinpy_root: Path, project: str, bug_id: str, work_root: Path, rng: random.Random, negative_ratio: int):
    info = load_bug_info(bugsinpy_root, project, bug_id)
    project_info = bugsinpy_root / "projects" / project / "project.info"
    metadata = {}
    if project_info.exists():
        from backend.risk.dataset.bugs_parser import parse_kv_file
        metadata = parse_kv_file(project_info)
    git_url = info.github_url or metadata.get("github_url", "")
    if not git_url:
        raise ValueError(f"No github_url for {project} bug {bug_id}")
    if git_url.endswith(".git") is False:
        git_url += ".git"

    buggy = work_root / f"{project}_{bug_id}_buggy"
    fixed = work_root / f"{project}_{bug_id}_fixed"
    checkout_commit(git_url, info.buggy_commit, buggy)
    checkout_commit(git_url, info.fixed_commit, fixed)

    positives = map_bug_to_functions(buggy, fixed)
    positive_keys = {(p["file"], p["name"]) for p in positives}
    if not positive_keys:
        raise ValueError("No changed Python function could be mapped from diff")

    rows = analyze_with_features(buggy)
    by_key = {(r["file"], r["function"]): r for r in rows}
    selected_pos = [by_key[k] for k in positive_keys if k in by_key]
    if not selected_pos:
        raise ValueError("Changed functions were not present in the buggy CodeAtlas parse")

    negatives = sample_negatives(rows, positive_keys, rng, negative_ratio)
    output = []
    for row in selected_pos:
        output.append({"repository": project, "bug_id": bug_id, "commit": info.buggy_commit, **row, "label": 1})
    for row in negatives:
        output.append({"repository": project, "bug_id": bug_id, "commit": info.buggy_commit, **row, "label": 0})
    return output, len(selected_pos), len(negatives)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugsinpy-root", required=True, type=Path)
    parser.add_argument("--output", default=Path("backend/risk/data/bugsinpy_features.csv"), type=Path)
    parser.add_argument("--projects", nargs="*", help="Projects to process; default: first 5")
    parser.add_argument("--max-bugs", type=int, default=0)
    parser.add_argument("--negative-ratio", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    projects = args.projects or discover_projects(args.bugsinpy_root)[:5]
    work_root = Path(tempfile.mkdtemp(prefix="codeatlas_bugsinpy_"))
    rows = []
    attempted = 0
    skipped = 0
    try:
        for project in projects:
            bugs = discover_bugs(args.bugsinpy_root, project)
            for bug_id in bugs:
                if args.max_bugs and attempted >= args.max_bugs:
                    break
                attempted += 1
                print(f"\nProject {project}\nBug {bug_id}")
                try:
                    bug_rows, pos, neg = process_bug(
                        args.bugsinpy_root, project, bug_id, work_root, rng, args.negative_ratio
                    )
                    print("  checkout + analysis successful")
                    print(f"  positive functions found: {pos}")
                    print(f"  negative functions sampled: {neg}")
                    rows.extend(bug_rows)
                except Exception as exc:
                    skipped += 1
                    print(f"  FAILED: {exc}")
            if args.max_bugs and attempted >= args.max_bugs:
                break
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(rows, start=1):
        row["sample_id"] = f"{row['repository']}_{row['bug_id']}_{i}"
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    positives = sum(r["label"] == 1 for r in rows)
    negatives = sum(r["label"] == 0 for r in rows)
    print("\n" + "=" * 60)
    print(f"Projects attempted: {len(projects)}")
    print(f"Bugs attempted:     {attempted}")
    print(f"Bugs skipped:       {skipped}")
    print(f"Positive samples:   {positives}")
    print(f"Negative samples:   {negatives}")
    print(f"Total samples:      {len(rows)}")
    print(f"CSV:                {args.output.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
