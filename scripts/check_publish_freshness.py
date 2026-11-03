"""Fail closed when a generated-site run no longer matches the latest main.

Food catalog builds can take time and run while the main branch moves.
Do not publish old product data or overwrite newer site contents.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")


def eligible_for_publication(run_sha: str, main_sha: str) -> bool:
    if not SHA.fullmatch(run_sha or ""):
        raise ValueError("Run SHA is absent or invalid")
    if not SHA.fullmatch(main_sha or ""):
        raise ValueError("Remote main SHA is absent or invalid")
    return run_sha == main_sha


def fetch_main_sha() -> str:
    result = subprocess.run(
        ["git", "ls-remote", "origin", "refs/heads/main"],
        capture_output=True, text=True, check=True, timeout=25
    )
    fields = result.stdout.strip().split()
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise RuntimeError("Cannot determine current main HEAD")
    return fields[0]


def main() -> int:
    release_sha = os.environ.get("GITHUB_SHA", "")
    output_path = os.environ.get("GITHUB_OUTPUT", "")
    if not output_path:
        raise RuntimeError("GITHUB_OUTPUT is required")
    remote_sha = fetch_main_sha()
    eligible = eligible_for_publication(release_sha, remote_sha)
    with Path(output_path).open("a", encoding="utf-8") as output:
        output.write(f"publish={'true' if eligible else 'false'}\n")
        output.write(f"main_sha={remote_sha}\n")
    if eligible:
        print(f"PASS: food build {release_sha[:12]} is current main")
    else:
        print(f"::notice::Food build {release_sha[:12]} superseded by "
              f"{remote_sha[:12]} — retain current site, do not push old data. "
              "A fresh run is required for the new commit.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"::error::Cannot verify food release freshness: {error}", file=sys.stderr)
        sys.exit(1)
