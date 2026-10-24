"""Dedicated working copy of Shi et al.'s tree for Study 2 runs.

Upstream resolves task files against the current directory (`runner.py`: repo_root = Path.cwd())
and writes temporary test files under `<cwd>/results/tmp_tests`. Runs therefore execute with the
working directory set to a copy of the upstream tree, never the submodule itself. The copy is an
exact `git archive` of the pinned commit (experiments/, task/, LICENSE), so it holds no local edits
and no bytecode. A marker file records the commit and a content hash; `verify_tree` recomputes it.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

from src.upstream import UPSTREAM, UPSTREAM_COMMIT

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TREE = ROOT / "work" / "study2" / "upstream"
PATHS = ("experiments", "task", "LICENSE")
MARKER = "STUDY2_UPSTREAM_COPY.json"


def _archive_bytes() -> bytes:
    return subprocess.run(["git", "-C", str(UPSTREAM), "archive", "--format=tar", UPSTREAM_COMMIT, *PATHS],
                          check=True, capture_output=True).stdout


def content_hash(tree: Path) -> str:
    """SHA-256 over (relative path, file bytes) of every file under PATHS, sorted; ignores
    __pycache__ and results/ (runtime output)."""
    h = hashlib.sha256()
    files = sorted(p for name in PATHS for p in ([tree / name] if (tree / name).is_file()
                                                 else (tree / name).rglob("*"))
                   if p.is_file() and "__pycache__" not in p.parts)
    for p in files:
        h.update(str(p.relative_to(tree)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def ensure_tree(dest: Path = DEFAULT_TREE) -> Path:
    """Create the copy if absent; verify it otherwise. Returns the tree path."""
    dest = Path(dest)
    if (dest / MARKER).exists():
        verify_tree(dest)
        return dest
    if dest.exists() and any(dest.iterdir()):
        raise RuntimeError(f"{dest} exists without a marker; refusing to overwrite")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(_archive_bytes())) as tar:
        tar.extractall(dest, filter="data")
    (dest / MARKER).write_text(json.dumps({"upstream_commit": UPSTREAM_COMMIT, "paths": PATHS,
                                           "content_sha256": content_hash(dest)}, indent=1))
    return dest


def verify_tree(dest: Path = DEFAULT_TREE) -> dict:
    meta = json.loads((Path(dest) / MARKER).read_text())
    if meta["upstream_commit"] != UPSTREAM_COMMIT:
        raise RuntimeError(f"upstream copy is at {meta['upstream_commit']}, expected {UPSTREAM_COMMIT}")
    now = content_hash(Path(dest))
    if now != meta["content_sha256"]:
        raise RuntimeError(f"upstream copy {dest} was modified (content hash {now[:12]} != "
                           f"{meta['content_sha256'][:12]})")
    return meta


def check_import_location(experiments_init: Path, tree: Path = DEFAULT_TREE):
    """`experiments` must come from the verified copy, or from the submodule clean at the pin."""
    loc = Path(experiments_init).resolve().parent
    if loc == (Path(tree) / "experiments").resolve():
        return "copy"
    if loc == (UPSTREAM / "experiments").resolve():
        head = subprocess.run(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(UPSTREAM), "status", "--porcelain"], check=True,
                               capture_output=True, text=True).stdout.strip()
        if head != UPSTREAM_COMMIT or dirty:
            raise RuntimeError(f"submodule at {head} (dirty={bool(dirty)}), expected clean {UPSTREAM_COMMIT}")
        return "submodule"
    raise RuntimeError(f"experiments imported from unexpected location {loc}")


if __name__ == "__main__":
    t = ensure_tree()
    print(t, verify_tree(t))
