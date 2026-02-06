#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/root/sbox")
DOTNET = r"C:\Program Files\dotnet\dotnet.exe"
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

# Ignore by suffix
IGNORE_SUFFIXES = {
    ".user",
    ".suo",
    ".cache",
    ".log",
}

# Only treat these as "code changes that should trigger a build"
# You can expand this if you want content files to trigger builds too.
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
    ".txt",
}


def run(cmd, check=True, capture=False):
    print(f"+ {' '.join(cmd)}")
    if capture:
        return subprocess.check_output(cmd, text=False)
    else:
        subprocess.check_call(cmd)


def is_ignored(path: str) -> bool:
    # normalize slashes
    path = path.replace("\\", "/").lstrip("./")

    parts = path.split("/")

    # ignore if any directory component is in IGNORE_DIRS
    for part in parts[:-1]:
        if part in IGNORE_DIRS:
            return True

    # ignore if filename suffix matches
    p = Path(path)
    if p.suffix in IGNORE_SUFFIXES:
        return True

    return False


def is_relevant(path: str) -> bool:
    p = Path(path)
    if p.suffix in RELEVANT_SUFFIXES:
        return True

    # if it's a directory entry, ignore
    if path.endswith("/"):
        return False

    return False


def git_changed_files():
    """
    Returns repo-relative paths of changed files.
    Includes staged + unstaged + untracked.
    Uses -z to avoid whitespace/path parsing bugs.
    """
    changed = set()

    out = run(["git", "status", "--porcelain", "-z"], capture=True)

    # output is: XY<space>path\0 or "?? path\0"
    entries = out.split(b"\x00")

    for entry in entries:
        if not entry:
            continue

        # entry begins with status, then space, then filename
        # examples:
        # b" M engine/foo.cs"
        # b"?? .vscode/"
        if len(entry) < 4:
            continue

        # status = entry[:2]  # unused
        raw_path = entry[3:]  # everything after "XY "
        path = raw_path.decode("utf-8", errors="replace").strip()

        if not path:
            continue

        # ignore directories and junk
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

        # walk upward until we find a csproj
        p = full.parent
        while p != ROOT and p != p.parent:
            csprojs = sorted(p.glob("*.csproj"))
            if csprojs:
                owners.add(csprojs[0])
                break
            p = p.parent

    return sorted(owners)


def wine_path(path: Path):
    # convert /root/sbox/engine/... into Z:/root/sbox/engine/...
    return "Z:/" + str(path.relative_to("/")).replace("\\", "/")


def build_project(csproj: Path):
    proj = wine_path(csproj)
    print(f"\n==> BUILDING: {csproj.relative_to(ROOT)}\n")

    run([
        "xvfb-run", "-a",
        "wine", DOTNET,
        "build", proj,
        "-c", CONFIG
    ])


def main():
    os.chdir(ROOT)

    # defensively avoid "dubious ownership" issues
    subprocess.call(["git", "config", "--global", "--add", "safe.directory", str(ROOT)])

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
