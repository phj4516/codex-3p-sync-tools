#!/usr/bin/env python3
"""codex-sync ? Cross-platform Codex conversation sync via GitHub.

Usage:
  python sync.py push   # Push recent sessions to GitHub (paths auto-converted)
  python sync.py pull   # Pull sessions from GitHub (paths auto-converted)
  python sync.py status # Show sync status
Config:  KEEP_SESSIONS = 10 (edit in sync.py)
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from pathspec import PathSpec
    from pathspec.patterns import GitWildMatchPattern
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False

SYNC_REPO = "https://github.com/phj4516/codex-sync.git"
IS_WINDOWS = platform.system() == "Windows"

def codex_home():   return Path.home() / ".codex"
def script_dir():   return Path(__file__).resolve().parent
def sync_dir():     return Path.home() / "CodexSync"

KEEP_SESSIONS = 300  # max sessions to sync


# ?? git helpers ???????????????????????????????????????????????????

def run_git(args, cwd):
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True)

def ensure_repo():
    repo = sync_dir()
    if not (repo / ".git").is_dir():
        repo.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "clone", SYNC_REPO, str(repo)], capture_output=True, text=True)
        if r.returncode == 0:
            print(f"Cloned {SYNC_REPO}")
            return repo
        err = r.stderr.strip().split("\n")[0]
        print(f"Clone failed ({err}), initializing locally...")
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", SYNC_REPO], cwd=str(repo), capture_output=True)
        r2 = subprocess.run(["git", "pull", "origin", "main", "--allow-unrelated-histories"],
                            cwd=str(repo), capture_output=True, text=True)
        run_git(["branch", "-M", "main"], repo)
        if r2.returncode != 0:
            (repo / ".gitkeep").write_text("")
            run_git(["add", ".gitkeep"], repo)
            run_git(["commit", "-m", "init codex-sync"], repo)
            r3 = run_git(["push", "-u", "origin", "main"], repo)
            if r3.returncode != 0:
                stderr = r3.stderr.strip()
                if "Permission denied" in stderr or "publickey" in stderr:
                    print("\n*** SSH key not configured for GitHub.\n"
                          "    Run: ssh -T git@github.com  to test.\n")
                else:
                    print(f"git push failed: {stderr}")
            else:
                print("Initialized empty repo and pushed to GitHub.")
        else:
            print("Pulled existing content.")
    return repo

def git_pull(repo):
    r = run_git(["pull", "--rebase", "origin", "main"], repo)
    if r.returncode != 0:
        print(f"git pull failed: {r.stderr.strip()}")
        return False
    return True

def git_push(repo, message):
    r = run_git(["status", "--porcelain"], repo)
    if not r.stdout.strip():
        print("No changes to push.")
        return True
    run_git(["add", "-A"], repo)
    run_git(["commit", "-m", message], repo)
    r = run_git(["push", "origin", "main"], repo)
    if r.returncode != 0:
        print(f"git push failed: {r.stderr.strip()}")
        return False
    print("Pushed to GitHub.")
    return True

# ?? pathmap ???????????????????????????????????????????????????????

def parse_pathmap(path):
    mappings = {}
    if not path.exists():
        print(f"[WARN] pathmap.conf not found at {path} ? no path conversion")
        return mappings
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line or "|" not in line:
            continue
        name, _, rest = line.partition("=")
        win_part, _, mac_part = rest.strip().partition("|")
        win_path = win_part.strip().replace("\\\\", "\\")
        mac_path = mac_part.strip()
        mappings[name.strip()] = (win_path, mac_path)
    return mappings

def build_replacements(mappings, direction):
    pairs = []
    for _name, (win_path, mac_path) in mappings.items():
        if direction == "to-mac":
            pairs.append((win_path.replace("\\", "\\\\"), mac_path))
        else:
            pairs.append((mac_path, win_path.replace("\\", "\\\\")))
    # Sort by search-string length descending: longer paths first to
    # avoid prefix-shorter partial matching longer paths.
    pairs.sort(key=lambda p: len(p[0]), reverse=True)

    return pairs

def convert_file(filepath, replacements):
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception:
        return 0
    changed = False
    for s, r in replacements:
        if s in text:
            text = text.replace(s, r)
            changed = True
    if changed:
        filepath.write_text(text, encoding="utf-8")
        return 1
    return 0

# ?? core sync ?????????????????????????????????????????????????????

def load_gitignore_rules():
    gi_path = codex_home() / ".gitignore"
    if not gi_path.exists():
        return None
    if not HAS_PATHSPEC:
        return None
    lines = gi_path.read_text(encoding="utf-8").splitlines()
    return PathSpec.from_lines(GitWildMatchPattern, lines)

def copy_other_files(src_root, dst_root, gitignore_spec, base_rel=""):
    """Copy files from src_root to dst_root, respecting gitignore patterns."""
    import filecmp
    for item in src_root.iterdir():
        if item.name in (".git", "sessions", "archived_sessions"):
            continue
        rel = f"{base_rel}/{item.name}" if base_rel else item.name
        rel = rel.replace("\\", "/")
        if item.is_dir():
            rel += "/"
        if gitignore_spec and gitignore_spec.match_file(rel):
            continue
        dst = dst_root / item.name
        try:
            if item.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                copy_other_files(item, dst, gitignore_spec, rel.rstrip('/'))
            else:
                if dst.exists():
                    try:
                        if filecmp.cmp(str(item), str(dst), shallow=False):
                            continue
                    except (PermissionError, OSError):
                        pass
                shutil.copy2(item, dst)
        except PermissionError:
            pass

def cleanup_stale_files(src_root, dst_root, gitignore_spec, base_rel=""):
    """Delete files from dst_root that no longer exist in src_root."""
    import shutil
    for item in list(dst_root.iterdir()):
        if item.name in (".git", "sessions", "archived_sessions"):
            continue
        rel = f"{base_rel}/{item.name}" if base_rel else item.name
        rel = rel.replace("\\", "/")
        if item.is_dir():
            rel += "/"
        if gitignore_spec and gitignore_spec.match_file(rel):
            continue
        src_item = src_root / item.name
        if not src_item.exists():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                print(f"  Removed stale dir:  {rel}")
            else:
                item.unlink(missing_ok=True)
                print(f"  Removed stale file: {rel}")
        elif item.is_dir() and src_item.is_dir():
            cleanup_stale_files(src_item, item, gitignore_spec, rel.rstrip("/"))

def list_session_files(root):
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.jsonl"))

def session_mtime(f):
    try:
        return f.stat().st_mtime
    except Exception:
        return 0


def _push_sessions_dir(source_rel, keep_sessions, mappings, direction):
    """Push JSONL files from a directory with path conversion."""
    source = codex_home() / source_rel
    dest_root = sync_dir() / source_rel

    all_files = list_session_files(source)
    all_files.sort(key=session_mtime, reverse=True)
    if keep_sessions:
        recent = all_files[:keep_sessions]
    else:
        recent = all_files

    # Clean up remote files that were deleted locally
    remote_files = list_session_files(dest_root)
    for rf in remote_files:
        rel = rf.relative_to(dest_root)
        local = source / rel
        if not local.exists():
            rf.unlink(missing_ok=True)

    if not recent:
        return 0, 0

    # Copy and convert
    replacements = build_replacements(mappings, direction)
    dest_root.mkdir(parents=True, exist_ok=True)
    copied, converted = 0, 0
    for src in recent:
        rel = src.relative_to(source)
        dst = dest_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
        if replacements:
            if convert_file(dst, replacements):
                converted += 1

    return copied, converted


def _pull_sessions_dir(source_rel, mappings, direction):
    """Pull JSONL files from a directory with path conversion and cleanup."""
    source = sync_dir() / source_rel
    if not source.is_dir():
        return 0, 0, 0

    dest_root = codex_home() / source_rel
    dest_root.mkdir(parents=True, exist_ok=True)

    files = list_session_files(source)
    if not files:
        return 0, 0, 0

    replacements = build_replacements(mappings, direction)
    copied, converted = 0, 0
    for src in files:
        rel = src.relative_to(source)
        dst = dest_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
        if replacements:
            if convert_file(dst, replacements):
                converted += 1

    # Clean up local files that were deleted from remote
    remote_relpaths = {f.relative_to(source) for f in files}
    local_files = list_session_files(dest_root)
    cleaned = 0
    for lf in local_files:
        if lf.relative_to(dest_root) not in remote_relpaths:
            lf.unlink(missing_ok=True)
            cleaned += 1
            print(f"  Removed stale {source_rel}: {lf.name}")

    return copied, converted, cleaned

def sync_push(mappings, keep_sessions):
    repo = ensure_repo()
    git_pull(repo)

    if IS_WINDOWS:
        direction, target_os = "to-mac", "macOS"
    else:
        direction, target_os = "to-win", "Windows"

    total_copied, total_converted = 0, 0

    # Sessions (with keep limit)
    all_files = list_session_files(codex_home() / "sessions")
    all_files.sort(key=session_mtime, reverse=True)
    skipped = max(0, len(all_files) - keep_sessions)
    if skipped:
        print(f"Sessions: keeping {keep_sessions} most recent, skipping {skipped} older")

    c, v = _push_sessions_dir("sessions", keep_sessions, mappings, direction)
    total_copied += c
    total_converted += v

    # Archived sessions (no keep limit — all pushed)
    c, v = _push_sessions_dir("archived_sessions", None, mappings, direction)
    total_copied += c
    total_converted += v

    print(f"Paths converted for {target_os} ({len(build_replacements(mappings, direction))} mapping(s))")
    gi = load_gitignore_rules()
    if gi:
        copy_other_files(codex_home(), repo, gi)
        cleanup_stale_files(codex_home(), repo, gi)
        gi_src = codex_home() / ".gitignore"
        gi_dst = repo / ".gitignore"
        shutil.copy2(gi_src, gi_dst)
    git_push(repo, f"push from {platform.system()}: {total_copied} files")

def sync_pull(mappings):
    repo = ensure_repo()
    git_pull(repo)

    if IS_WINDOWS:
        direction = "to-win"
    else:
        direction = "to-mac"

    total_copied, total_converted, total_cleaned = 0, 0, 0

    c, v, cl = _pull_sessions_dir("sessions", mappings, direction)
    total_copied += c
    total_converted += v
    total_cleaned += cl

    c, v, cl = _pull_sessions_dir("archived_sessions", mappings, direction)
    total_copied += c
    total_converted += v
    total_cleaned += cl

    if total_copied == 0:
        print("No files to pull")
        return

    gi = load_gitignore_rules()
    if gi:
        copy_other_files(repo, codex_home(), gi)
        cleanup_stale_files(repo, codex_home(), gi)
    print(f"Pulled {total_copied} file(s)")
    if total_cleaned:
        print(f"Cleaned up {total_cleaned} stale local file(s)")
    print(f"Paths converted in {total_converted} file(s)")

def sync_status(mappings):
    local_files = list_session_files(codex_home() / "sessions")
    local_files.sort(key=session_mtime, reverse=True)

    repo = sync_dir()
    if (repo / ".git").is_dir():
        git_pull(repo)
        r = subprocess.run(["git", "log", "-1", "--format=%h %s"],
                           cwd=str(repo), capture_output=True, text=True)
        last_commit = r.stdout.strip() or "(no commits)"
        remote_files = list_session_files(repo / "sessions")
    else:
        last_commit = "(not cloned yet)"
        remote_files = []

    archived_local = list_session_files(codex_home() / "archived_sessions")
    archived_remote = list_session_files(repo / "archived_sessions") if (repo / ".git").is_dir() else []

    print(f"Local sessions   : {len(local_files)} file(s) (keep {KEEP_SESSIONS})")
    if local_files:
        print(f"  Newest: {local_files[0].name}")
    print(f"Local archived   : {len(archived_local)} file(s)")
    print(f"GitHub sessions  : {len(remote_files)} file(s)")
    print(f"GitHub archived  : {len(archived_remote)} file(s)")
    print(f"Last commit      : {last_commit}")
    print(f"Path mappings    : {len(mappings)}")
    for name, (w, m) in mappings.items():
        print(f"  {name}:  {w}  <->  {m}")

# ?? CLI ???????????????????????????????????????????????????????????

def main():
    parser = argparse.ArgumentParser(description="Codex cross-device conversation sync via GitHub")
    parser.add_argument("command", choices=["push", "pull", "status"])
    parser.add_argument("--pathmap", default=None, help="Path to pathmap.conf")
    parser.add_argument("--keep-sessions", type=int, default=None,
                        help="Override KEEP_SESSIONS from sync.conf")
    args = parser.parse_args()

    pathmap_conf = (Path(args.pathmap).expanduser().resolve() if args.pathmap
                    else script_dir() / "pathmap.conf")
    mappings = parse_pathmap(pathmap_conf)

    keep = args.keep_sessions if args.keep_sessions else KEEP_SESSIONS

    if args.command == "push":
        sync_push(mappings, keep)
    elif args.command == "pull":
        sync_pull(mappings)
    elif args.command == "status":
        sync_status(mappings)

if __name__ == "__main__":
    main()
