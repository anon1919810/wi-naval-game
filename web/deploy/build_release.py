#!/usr/bin/env python3
"""Package one immutable Plimsoll web release from an allowlist of owned inputs.

Standard library only. The archive is built from git-tracked files under
``tools/plimsoll`` and ``web/backend``, an explicit list of ``web/deploy`` files and the
compiled ``web/frontend/dist`` output. It never walks the whole checkout, so game
assets, research notes, local databases and operator secrets cannot leak in.

Operator rules enforced here:

* the source freeze must be validated by the operator (``--confirm-source-frozen``);
* a dirty worktree is never reported as clean, and a dirty worktree can never be
  confirmed frozen;
* path traversal, absolute names, symlinks and escaping paths are refused;
* every archived file, and the archive itself, is hashed into a JSON manifest.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile

TOOL_VERSION = "1.0"
MANIFEST_VERSION = 1
ARCHIVE_ROOT_NAME = "plimsoll-web"

TRACKED_ROOTS = ("tools/plimsoll", "web/backend")
FRONTEND_DIST_ROOT = "web/frontend/dist"
FRONTEND_DIST_REQUIRED = ("index.html",)
DEFAULT_OUTPUT = ".superpowers/releases"

# New deployment files are explicitly listed: until they are committed they are not in
# `git ls-files`, and the release must not depend on an untracked accidental file.
DEPLOY_FILES = (
    "web/deploy/Dockerfile",
    "web/deploy/Dockerfile.dockerignore",
    "web/deploy/README.md",
    "web/deploy/build_release.py",
    "web/deploy/compose.yaml",
    "web/deploy/nginx/plimsoll.conf.template",
    "web/deploy/nginx/rate-limit-zones.conf",
    "web/deploy/production.env.example",
    "web/deploy/requirements-build.txt",
    "web/deploy/requirements-runtime.txt",
    "web/deploy/tests/test_build_release.py",
)

DENIED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".superpowers",
        ".venv",
        "__pycache__",
        "node_modules",
        "private",
        "tests",
        "venv",
    }
)
DENIED_FILE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".netrc",
        ".pgpass",
        "id_rsa",
        "production.env",
    }
)
DENIED_FILE_SUFFIXES = (
    ".db",
    ".key",
    ".log",
    ".pem",
    ".pyd",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
)
DENIED_DIRECTORY_SUFFIXES = (".egg-info", ".dist-info")


class ReleaseError(RuntimeError):
    """A release precondition failed; nothing was written."""


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_member_name(name: str) -> str:
    """Return a clean relative POSIX name or refuse anything unsafe."""
    text = str(name).replace("\\", "/").strip()
    if not text:
        raise ReleaseError("empty archive member name")
    if text.startswith("/") or (len(text) > 1 and text[1] == ":"):
        raise ReleaseError(f"absolute path refused: {name!r}")
    parts: list[str] = []
    for part in text.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ReleaseError(f"path traversal refused: {name!r}")
        parts.append(part)
    if not parts:
        raise ReleaseError(f"empty archive member name: {name!r}")
    return "/".join(parts)


def is_denied_path(member: str) -> bool:
    """True for secrets, caches, virtualenvs and test trees."""
    for part in PurePosixPath(member).parts:
        if part in DENIED_DIRECTORY_NAMES:
            return True
        if part.endswith(DENIED_DIRECTORY_SUFFIXES):
            return True
    name = PurePosixPath(member).name
    if name in DENIED_FILE_NAMES or name.startswith(".env."):
        return True
    return name.lower().endswith(DENIED_FILE_SUFFIXES)


def is_link(path: Path) -> bool:
    return path.is_symlink()


def _resolve_inside(repo_root: Path, member: str) -> Path:
    root = repo_root.resolve()
    candidate = (root / PurePosixPath(member)).resolve()
    if candidate != root and root not in candidate.parents:
        raise ReleaseError(f"path escapes the repository: {member!r}")
    return root / PurePosixPath(member)


def assert_safe_member_file(
    repo_root: Path,
    member: str,
    link_probe: Callable[[Path], bool] | None = None,
) -> Path:
    """Refuse symlinked or escaping inputs, then return the absolute path."""
    probe = link_probe or is_link
    root = repo_root.resolve()
    current = root
    for part in PurePosixPath(normalize_member_name(member)).parts:
        current = current / part
        if probe(current):
            raise ReleaseError(f"symlinked input refused: {member!r}")
    absolute = _resolve_inside(repo_root, member)
    if not absolute.is_file():
        raise ReleaseError(f"missing input file: {member!r}")
    return absolute


def git_output(repo_root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout


def git_head(repo_root: Path) -> str | None:
    head = git_output(repo_root, "rev-parse", "HEAD")
    return head.strip() if head else None


def git_dirty(repo_root: Path) -> bool | None:
    status = git_output(repo_root, "status", "--porcelain", "--untracked-files=normal")
    if status is None:
        return None
    return bool(status.strip())


def git_tracked_files(repo_root: Path) -> list[str] | None:
    listing = git_output(repo_root, "ls-files", "-z", "--", *TRACKED_ROOTS)
    if listing is None:
        return None
    return [normalize_member_name(part) for part in listing.split("\0") if part]


def _tracked_release_files(tracked: Iterable[str]) -> list[str]:
    roots = tuple(PurePosixPath(root).parts for root in TRACKED_ROOTS)
    selected: list[str] = []
    for raw in tracked:
        member = normalize_member_name(raw)
        parts = PurePosixPath(member).parts
        if not any(parts[: len(root)] == root for root in roots):
            continue
        if is_denied_path(member):
            continue
        selected.append(member)
    return selected


def _deploy_release_files(deploy_files: Sequence[str]) -> list[str]:
    return [normalize_member_name(name) for name in deploy_files]


def _dist_release_files(dist_members: Sequence[str]) -> list[str]:
    members = sorted({normalize_member_name(name) for name in dist_members})
    if not members:
        raise ReleaseError(
            f"{FRONTEND_DIST_ROOT} is empty: run 'npm --prefix web/frontend run build' first"
        )
    present = {PurePosixPath(member).name for member in members}
    missing = [name for name in FRONTEND_DIST_REQUIRED if name not in present]
    if missing:
        raise ReleaseError(f"{FRONTEND_DIST_ROOT} is missing {', '.join(missing)}")
    return [member for member in members if not is_denied_path(member)]


def walk_dist(repo_root: Path, dist_root: str = FRONTEND_DIST_ROOT) -> list[str]:
    base = repo_root / PurePosixPath(dist_root)
    if not base.is_dir() or base.is_symlink():
        raise ReleaseError(
            f"{dist_root} not found: build the frontend before packaging a release"
        )
    members: list[str] = []
    for directory, subdirs, filenames in os.walk(base, followlinks=False):
        subdirs[:] = sorted(
            name for name in subdirs if name not in DENIED_DIRECTORY_NAMES
        )
        for filename in sorted(filenames):
            members.append(
                normalize_member_name(
                    str(Path(directory, filename).relative_to(repo_root))
                )
            )
    return members


def collect_release_files(
    repo_root: Path,
    *,
    tracked_files: Sequence[str],
    deploy_files: Sequence[str] = DEPLOY_FILES,
    dist_files: Sequence[str] | None = None,
    dist_root: str = FRONTEND_DIST_ROOT,
) -> list[str]:
    """Return the sorted, de-duplicated allowlist of release members."""
    members = _tracked_release_files(tracked_files)
    members.extend(_deploy_release_files(deploy_files))
    members.extend(
        _dist_release_files(
            walk_dist(repo_root, dist_root) if dist_files is None else dist_files
        )
    )
    unique = sorted(set(members))
    if not unique:
        raise ReleaseError("release allowlist is empty")
    return unique


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o644
    return info


def _archive_stem(git_head_value: str | None, dirty: bool | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = (git_head_value or "nogit")[:7]
    suffix = "-dirty" if dirty else ""
    return f"{ARCHIVE_ROOT_NAME}-{stamp}-{short}{suffix}"


def build_release(
    repo_root: Path,
    output_dir: Path,
    *,
    confirm_source_frozen: bool = False,
    allow_missing_git: bool = False,
    tracked_files: Sequence[str] | None = None,
    deploy_files: Sequence[str] = DEPLOY_FILES,
    dist_files: Sequence[str] | None = None,
    dist_root: str = FRONTEND_DIST_ROOT,
    head: str | None = None,
    dirty: bool | None = None,
    link_probe: Callable[[Path], bool] | None = None,
) -> dict:
    """Write one archive plus its manifest and return the manifest."""
    repo_root = Path(repo_root)
    if tracked_files is None:
        tracked_files = git_tracked_files(repo_root)
        if tracked_files is None:
            if not allow_missing_git:
                raise ReleaseError(
                    "git ls-files failed; run inside the repository or pass tracked files"
                )
            tracked_files = []
    if head is None:
        head = git_head(repo_root)
    if dirty is None:
        dirty = git_dirty(repo_root)
    if dirty is None and head is None and not allow_missing_git:
        raise ReleaseError("git metadata unavailable; cannot label the release")

    if confirm_source_frozen and dirty:
        raise ReleaseError(
            "worktree is dirty: it cannot be confirmed frozen. Commit the pending "
            "anonymous-auth sources first, or drop --confirm-source-frozen and treat "
            "the manifest's dirty=true as a non-releasable build."
        )

    members = collect_release_files(
        repo_root,
        tracked_files=tracked_files,
        deploy_files=deploy_files,
        dist_files=dist_files,
        dist_root=dist_root,
    )

    entries: list[dict] = []
    for member in members:
        absolute = assert_safe_member_file(repo_root, member, link_probe=link_probe)
        entries.append(
            {
                "path": member,
                "bytes": absolute.stat().st_size,
                "sha256": sha256_file(absolute),
            }
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = _archive_stem(head, dirty)
    archive_path = output_dir / f"{stem}.tar.gz"
    manifest_path = output_dir / f"{stem}.manifest.json"

    with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for member in members:
            archive.add(
                repo_root / PurePosixPath(member),
                arcname=f"{stem}/{member}",
                recursive=False,
                filter=_tar_filter,
            )

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "tool_version": TOOL_VERSION,
        "built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "archive": {
            "name": archive_path.name,
            "prefix": stem,
            "bytes": archive_path.stat().st_size,
            "sha256": sha256_file(archive_path),
        },
        "git": {
            "head": head,
            "head_short": head[:7] if head else None,
            "dirty": dirty,
            "source_freeze_confirmed": bool(confirm_source_frozen),
        },
        "file_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "files": entries,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest["manifest_path"] = str(manifest_path)
    manifest["archive_path"] = str(archive_path)
    return manifest


def _report(manifest: dict) -> None:
    git_state = manifest["git"]
    state = "clean" if git_state["dirty"] is False else (
        "dirty" if git_state["dirty"] else "unknown"
    )
    print(f"archive   : {manifest['archive_path']}")
    print(f"sha256    : {manifest['archive']['sha256']}")
    print(f"manifest  : {manifest['manifest_path']}")
    print(f"files     : {manifest['file_count']} ({manifest['total_bytes']} bytes)")
    print(f"git head  : {git_state['head_short'] or 'unknown'} ({state})")
    if not git_state["source_freeze_confirmed"]:
        print(
            "WARNING   : source freeze NOT confirmed. Re-run with "
            "--confirm-source-frozen on a clean, committed worktree before deploying."
        )
    if git_state["dirty"]:
        print("WARNING   : archive was built from a dirty worktree.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an immutable Plimsoll web release archive."
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="directory that receives the archive and manifest "
        f"(default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--confirm-source-frozen",
        action="store_true",
        help="operator attests the worktree is committed and frozen; refused when dirty",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    if args.confirm_source_frozen:
        head = git_head(repo_root)
        if head is None:
            print(
                "WARNING   : cannot read git HEAD; source freeze cannot be verified.",
                file=sys.stderr,
            )
        elif git_dirty(repo_root):
            print(
                "git status --porcelain is not empty. Commit the pending sources "
                "before confirming the freeze.",
                file=sys.stderr,
            )
            return 2

    try:
        manifest = build_release(
            repo_root,
            output_dir,
            confirm_source_frozen=args.confirm_source_frozen,
        )
    except ReleaseError as error:
        print(f"release refused: {error}", file=sys.stderr)
        return 1
    _report(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
