#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path
import argparse

ROOT = Path("/root/sbox")
DOTNET_EXE = r"C:\Program Files\dotnet\dotnet.exe"
CONFIG = os.environ.get("SBOX_CONFIG", "Developer")

# Ignore paths (repo-relative)
IGNORE_DIRS = {
    ".git",
    ".vscode",
    ".idea",
    ".vs",
    "bin",
    "obj",
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


def looks_like_fresh_clone():
    """
    If no build outputs exist, assume it hasn't been built yet.
    """
    engine_bin = ROOT / "engine/bin"
    engine_obj = ROOT / "engine/obj"
    game_bin = ROOT / "game/bin"
    game_obj = ROOT / "game/obj"

    # if any exist, probably already built at least once
    if engine_bin.exists() or engine_obj.exists() or game_bin.exists() or game_obj.exists():
        return False

    return True


def full_build():
    if not SBOXBUILD_CSPROJ.exists():
        print(f"ERROR: missing {SBOXBUILD_CSPROJ}")
        return 1

    proj = wine_path(SBOXBUILD_CSPROJ)

    print("\n==> FULL BUILD (SboxBuild)\n")

    # dotnet run --project ... -- build --config Developer
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


def main():
    parser = argparse.ArgumentParser(description="Smart incremental build for s&box in docker/wine.")
    parser.add_argument("--full", action="store_true", help="Force a full build using SboxBuild.")
    parser.add_argument("--no-auto-full", action="store_true",
                        help="Disable auto full-build detection for fresh clones.")
    args = parser.parse_args()

    os.chdir(ROOT)

    # avoid "dubious ownership" issues
    subprocess.call(["git", "config", "--global", "--add", "safe.directory", str(ROOT)])

    # Forced full build
    if args.full:
        return full_build()

    # Auto full build if looks like never built
    if not args.no_auto_full and looks_like_fresh_clone():
        print("==> No build output detected (fresh clone?). Running full build...")
        return full_build()

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
        build_project(p)

    print("\n==> Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
