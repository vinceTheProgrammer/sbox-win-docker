#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path
import argparse
import time
import hashlib

ROOT = Path("/root/sbox")
DOTNET_EXE = r"C:\Program Files\dotnet\dotnet.exe"
CONFIG = os.environ.get("SBOX_CONFIG", "Developer")

CACHE_DIR = ROOT / ".sboxbuild_cache"
HOST_UID = os.environ.get("HOST_UID")
HOST_GID = os.environ.get("HOST_GID")

# Ignore paths (repo-relative)
IGNORE_DIRS = {
    ".git",
    ".vscode",
    ".idea",
    ".vs",
    "bin",
    "obj",
    ".sboxbuild_cache",
}

IGNORE_SUFFIXES = {
    ".user",
    ".suo",
    ".cache",
    ".log",
}

RELEVANT_SUFFIXES = {
    ".cs",
    ".csproj",
    ".props",
    ".targets",
    ".sln",
    ".slnx",
    ".json",
    ".razor",
    ".tt",
}

SBOXBUILD_CSPROJ = ROOT / "engine/Tools/SboxBuild/SboxBuild.csproj"


def run(cmd, capture=False):
    print(f"+ {' '.join(cmd)}")
    if capture:
        return subprocess.check_output(cmd, text=False)
    subprocess.check_call(cmd)
    return None


def is_ignored(path: str) -> bool:
    path = path.replace("\\", "/").lstrip("./")
    parts = path.split("/")

    for part in parts[:-1]:
        if part in IGNORE_DIRS:
            return True

    p = Path(path)
    if p.suffix in IGNORE_SUFFIXES:
        return True

    return False


def is_relevant(path: str) -> bool:
    if path.endswith("/"):
        return False
    return Path(path).suffix in RELEVANT_SUFFIXES


def git_changed_files():
    changed = set()

    out = run(["git", "status", "--porcelain", "-z"], capture=True)
    entries = out.split(b"\x00")

    for entry in entries:
        if not entry:
            continue
        if len(entry) < 4:
            continue

        raw_path = entry[3:]
        path = raw_path.decode("utf-8", errors="replace").strip()

        if not path:
            continue
        if is_ignored(path):
            continue
        if not is_relevant(path):
            continue

        changed.add(path)

    return sorted(changed)


def find_csproj_owners(changed_files):
    owners = set()

    for f in changed_files:
        full = ROOT / f
        if not full.exists():
            continue

        p = full.parent
        while p != ROOT and p != p.parent:
            csprojs = sorted(p.glob("*.csproj"))
            if csprojs:
                owners.add(csprojs[0])
                break
            p = p.parent

    return sorted(owners)


def wine_path(path: Path):
    return "Z:/" + str(path.relative_to("/")).replace("\\", "/")


def build_project(csproj: Path):
    proj = wine_path(csproj)
    print(f"\n==> BUILDING: {csproj.relative_to(ROOT)}\n")

    run([
        "xvfb-run", "-a",
        "wine", DOTNET_EXE,
        "build", proj,
        "-c", CONFIG
    ])


def looks_like_fresh_clone(min_hits=4):
    sentinel_paths = [
        ROOT / "game/sbox.exe",
        ROOT / "game/sbox.dll",
        ROOT / "game/bin/managed/Sandbox.Engine.dll",
        ROOT / "game/.source2",
        ROOT / "engine/Tools/CodeGen/bin/CodeGen.dll",
    ]

    hits = sum(1 for p in sentinel_paths if p.exists())
    return hits < min_hits

def full_build():
    if not SBOXBUILD_CSPROJ.exists():
        print(f"ERROR: missing {SBOXBUILD_CSPROJ}")
        return 1

    proj = wine_path(SBOXBUILD_CSPROJ)

    print("\n==> FULL BUILD (SboxBuild)\n")

    run([
        "xvfb-run", "-a",
        "wine", DOTNET_EXE,
        "run",
        "--project", proj,
        "--",
        "build",
        "--config", CONFIG
    ])

    run([
        "xvfb-run", "-a",
        "wine", DOTNET_EXE,
        "run",
        "--project", proj,
        "--",
        "build-shaders"
    ])

    run([
        "xvfb-run", "-a",
        "wine", DOTNET_EXE,
        "run",
        "--project", proj,
        "--",
        "build-content"
    ])

    print("\n==> Full build done.")
    return 0


def iter_project_inputs(project_dir: Path):
    """
    Walk project dir recursively and yield relevant files
    (excluding bin/obj/.git/.vscode/etc).
    """
    for root, dirs, files in os.walk(project_dir):
        root_path = Path(root)

        # prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for f in files:
            p = root_path / f
            if p.suffix in IGNORE_SUFFIXES:
                continue
            if p.suffix not in RELEVANT_SUFFIXES:
                continue
            yield p


def find_directory_build_files(start_dir: Path):
    """
    Collect Directory.Build.props/targets walking up to ROOT.
    """
    out = []
    p = start_dir

    while True:
        props = p / "Directory.Build.props"
        targets = p / "Directory.Build.targets"

        if props.exists():
            out.append(props)
        if targets.exists():
            out.append(targets)

        if p == ROOT:
            break
        if p.parent == p:
            break
        p = p.parent

    return out


def file_hash(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_project_hash(csproj: Path):
    """
    Hash project inputs + directory build files.
    """
    project_dir = csproj.parent

    inputs = [csproj]
    inputs.extend(find_directory_build_files(project_dir))
    inputs.extend(iter_project_inputs(project_dir))

    # remove duplicates, sort stable
    inputs = sorted(set(inputs))

    h = hashlib.sha256()

    for p in inputs:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")

        with open(p, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)

    return h.hexdigest()


def cache_file_for(csproj: Path):
    safe_name = str(csproj.relative_to(ROOT)).replace("/", "__").replace("\\", "__")
    return CACHE_DIR / (safe_name + ".sha256")


def should_build_hash_cache(csproj: Path):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    new_hash = compute_project_hash(csproj)
    cache_file = cache_file_for(csproj)

    if cache_file.exists():
        old_hash = cache_file.read_text().strip()
        if old_hash == new_hash:
            return False

    cache_file.write_text(new_hash + "\n")
    return True

import shutil

def fix_addon_code_case():
    """
    Some builds incorrectly generate game/addons/<addon>/code/* instead of Code/*.
    On Linux this breaks Proton. This function merges `code` into `Code` and deletes `code`.
    """
    addons_dir = ROOT / "game/addons"
    if not addons_dir.exists():
        return

    print("\n==> Fixing addon Code/code case issues...")

    for addon in addons_dir.iterdir():
        if not addon.is_dir():
            continue

        lower = addon / "code"
        proper = addon / "Code"

        if not lower.exists() or not lower.is_dir():
            continue

        # If Code doesn't exist, create it
        proper.mkdir(parents=True, exist_ok=True)

        # Move everything from code/ into Code/
        for src in lower.rglob("*"):
            if src.is_dir():
                continue

            rel = src.relative_to(lower)
            dst = proper / rel

            dst.parent.mkdir(parents=True, exist_ok=True)

            # If destination exists, overwrite it
            if dst.exists():
                dst.unlink()

            shutil.move(str(src), str(dst))

        # Remove empty dirs inside lower
        for d in sorted(lower.rglob("*"), reverse=True):
            if d.is_dir():
                try:
                    d.rmdir()
                except OSError:
                    pass

        # Remove the main lower directory if empty
        try:
            lower.rmdir()
            print(f"   Fixed: {lower.relative_to(ROOT)} -> {proper.relative_to(ROOT)}")
        except OSError:
            print(f"   WARNING: could not delete {lower.relative_to(ROOT)} (not empty?)")

    print("==> Done fixing addon case issues.")

def fix_ownership_since(start_time: float):
    """
    Chown any files/dirs modified since start_time to HOST_UID:HOST_GID.
    This prevents root-owned build outputs on the host bind mount.
    """
    if not HOST_UID or not HOST_GID:
        print("==> HOST_UID/HOST_GID not set, skipping ownership fix.")
        return

    print(f"\n==> Fixing ownership (UID={HOST_UID}, GID={HOST_GID})...")

    ts = int(start_time)

    # Fix repo outputs
    subprocess.call([
        "bash", "-lc",
        f"find {ROOT} -xdev -newermt '@{ts}' -print0 | "
        f"xargs -0 -r chown {HOST_UID}:{HOST_GID}"
    ])

    print("==> Ownership fixed.")


def main():
    start_time = time.time()

    parser = argparse.ArgumentParser(description="Smart incremental build for s&box in docker/wine.")
    parser.add_argument("--full", action="store_true", help="Force a full build using SboxBuild.")
    parser.add_argument("--no-auto-full", action="store_true",
                        help="Disable auto full-build detection for fresh clones.")
    parser.add_argument("--hash-cache", action="store_true",
                        help="Use hash-cache mode (build only if project inputs changed).")
    args = parser.parse_args()

    os.chdir(ROOT)

    # avoid "dubious ownership" issues
    subprocess.call(["git", "config", "--global", "--add", "safe.directory", str(ROOT)])

    try:
        # Forced full build
        if args.full:
            rc = full_build()
            return rc

        # Auto full build if looks like never built
        if not args.no_auto_full and looks_like_fresh_clone():
            print("==> No build output detected (fresh clone?). Running full build...")
            rc = full_build()
            return rc

        # Normal incremental behavior
        changed = git_changed_files()

        if not changed:
            print("==> No relevant git changes detected. Nothing to build.")
            return 0

        print("==> Changed relevant files:")
        for f in changed:
            print("   ", f)

        projects = find_csproj_owners(changed)

        if not projects:
            print("\n==> No owning .csproj found for changed files.")
            print("    (Maybe only non-code files changed?)")
            return 0

        print("\n==> Projects to build:")
        for p in projects:
            print("   ", p.relative_to(ROOT))

        for p in projects:
            if args.hash_cache:
                if not should_build_hash_cache(p):
                    print(f"\n==> SKIPPING (hash match): {p.relative_to(ROOT)}")
                    continue
            build_project(p)

        print("\n==> Done.")
        return 0

    finally:
        fix_addon_code_case()
        fix_ownership_since(start_time)


if __name__ == "__main__":
    sys.exit(main())
