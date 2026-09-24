# Copyright 2026 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass, field
import fnmatch
import os
from pathlib import Path
import subprocess

IGNORE_MARKERS = {'AMENT_IGNORE', 'COLCON_IGNORE', 'CATKIN_IGNORE'}
SKIP_DIRS = {'.git', '.hg', '.svn', '.tox', '.venv', 'venv', '__pycache__', 'build', 'install', 'log'}


@dataclass
class LintTarget:
    """Represents a logical repository, ROS package, or directory target to lint."""

    name: str
    root: Path
    git_root: Path | None = None
    custom_config: Path | None = None
    explicit_files: list[Path] = field(default_factory=list)


def find_git_root(path: Path) -> Path | None:
    """Return the enclosing Git repository root if one exists."""
    curr = path.resolve()
    if curr.is_file():
        curr = curr.parent
    while True:
        if (curr / '.git').exists():
            return curr
        if curr.parent == curr:
            return None
        curr = curr.parent


def find_custom_pre_commit_config(target_root: Path, git_root: Path | None) -> Path | None:
    """Return a custom .pre-commit-config.yaml if present in the target or its git root."""
    candidate = target_root / '.pre-commit-config.yaml'
    if candidate.is_file():
        return candidate
    if git_root is not None:
        git_candidate = git_root / '.pre-commit-config.yaml'
        if git_candidate.is_file():
            return git_candidate
    return None


def _has_ignore_marker(directory: Path) -> bool:
    return any((directory / marker).exists() for marker in IGNORE_MARKERS)


def discover_targets(paths: list[str]) -> list[LintTarget]:
    """Discover lint targets (ROS packages, git repositories, or explicit files/dirs)."""
    targets: list[LintTarget] = []
    seen_roots: set[Path] = set()

    for raw_path in paths:
        p = Path(raw_path).resolve()
        if not p.exists():
            continue

        if p.is_file():
            git_root = find_git_root(p)
            root = git_root if git_root else p.parent
            custom_cfg = find_custom_pre_commit_config(p.parent, git_root)
            targets.append(
                LintTarget(
                    name=p.name,
                    root=root,
                    git_root=git_root,
                    custom_config=custom_cfg,
                    explicit_files=[p],
                )
            )
            continue

        # If the directory itself is a ROS package or has a .pre-commit-config.yaml, treat it as a target
        if (p / 'package.xml').is_file() or (p / '.pre-commit-config.yaml').is_file():
            if not _has_ignore_marker(p) and p not in seen_roots:
                seen_roots.add(p)
                git_root = find_git_root(p)
                targets.append(
                    LintTarget(
                        name=p.name,
                        root=p,
                        git_root=git_root,
                        custom_config=find_custom_pre_commit_config(p, git_root),
                    )
                )
            continue

        # Walk the directory tree looking for ROS packages (package.xml) or sub-repos (.git)
        found_subtargets = False
        for dirpath, dirnames, filenames in os.walk(p, topdown=True):
            curr = Path(dirpath)
            if curr != p and _has_ignore_marker(curr):
                dirnames[:] = []
                continue

            # Filter out skipped directories
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.'))

            if 'package.xml' in filenames or '.pre-commit-config.yaml' in filenames:
                if curr not in seen_roots:
                    seen_roots.add(curr)
                    git_root = find_git_root(curr)
                    targets.append(
                        LintTarget(
                            name=curr.name,
                            root=curr,
                            git_root=git_root,
                            custom_config=find_custom_pre_commit_config(curr, git_root),
                        )
                    )
                found_subtargets = True
                dirnames[:] = []

        if not found_subtargets and p not in seen_roots:
            seen_roots.add(p)
            git_root = find_git_root(p)
            targets.append(
                LintTarget(
                    name=p.name,
                    root=p,
                    git_root=git_root,
                    custom_config=find_custom_pre_commit_config(p, git_root),
                )
            )

    return targets


def collect_target_files(
    target: LintTarget,
    exclude_patterns: list[str] | None = None,
    git_diff_ref: str | None = None,
    git_staged: bool = False,
) -> list[Path]:
    """Collect candidate files inside a LintTarget, respecting ignore markers and git filters."""
    exclude_patterns = exclude_patterns or []

    if target.explicit_files:
        candidates = list(target.explicit_files)
    elif (git_diff_ref is not None or git_staged) and target.git_root is not None:
        cmd = ['git', '-C', str(target.git_root), 'diff', '--name-only', '--diff-filter=ACMR']
        if git_staged:
            cmd.append('--cached')
        elif git_diff_ref:
            cmd.append(f'{git_diff_ref}...HEAD')
        cmd.extend(['--', str(target.root)])
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        candidates = []
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line:
                    fp = (target.git_root / line).resolve()
                    if fp.is_file() and fp.is_relative_to(target.root):
                        candidates.append(fp)
    else:
        candidates = []
        for dirpath, dirnames, filenames in os.walk(target.root, topdown=True):
            curr = Path(dirpath)
            if curr != target.root and _has_ignore_marker(curr):
                dirnames[:] = []
                continue
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.'))
            for fname in sorted(filenames):
                if fname in IGNORE_MARKERS or fname.startswith('.'):
                    continue
                candidates.append((curr / fname).resolve())

    filtered: list[Path] = []
    for fp in candidates:
        try:
            rel = str(fp.relative_to(target.root))
        except ValueError:
            rel = str(fp)
        if any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(fp.name, pat) for pat in exclude_patterns):
            continue
        filtered.append(fp)

    return filtered
