#!/usr/bin/env python3
"""Box-side review sync. This directory is a copy you can place on the box.

It is not installed on the box yet. It does not need a git checkout.
It does not merge pull requests, force-push, or read token files.

Stages, in order, are not implied by one another:
  persisted, built, pushed_branch, pull_request, merged, deployed, verified

GitHub Pages for this repo publishes the default branch (main) only.
Pushing the review branch updates the open PR. It does not change the public URL.
Merging that PR is a separate, explicit permission and is not granted for future bundles.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sync_site as sync  # noqa: E402


def github_commit_plan(repo: str, branch: str, bundle: Path) -> dict:
    if branch in ("main", "master") or branch.startswith("-") or "--force" in branch:
        raise RuntimeError("refuse merge/force/protected branch")
    if not repo or "/" not in repo or repo.startswith("-"):
        raise RuntimeError("bad repo")
    if not bundle.exists():
        raise RuntimeError("bundle missing")
    # Dry plan only. A real commit must be a fast-forward update of this branch
    # via `gh api` using whatever auth the operator already has. Do not put a token
    # on the command line. Do not set force=true on the ref update.
    return {
        "publishes_pages": False,
        "merges": False,
        "force": False,
        "steps": [
            f"gh api repos/{repo}/git/ref/heads/{branch}",
            f"gh api repos/{repo}/git/blobs -f content=... -f encoding=utf-8",
            f"gh api repos/{repo}/git/trees -f base_tree=<parent> ...",
            f"gh api repos/{repo}/git/commits -f message=review-sync -f tree=<tree> -f parents[]=<parent>",
            f"gh api -X PATCH repos/{repo}/git/refs/heads/{branch} -f sha=<new> ",
        ],
        "note": "PATCH the branch ref only when it fast-forwards. Do not call merge. Pages stays on main until a person merges the PR.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone review sync (not installed on the box)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stage")
    plan = sub.add_parser("github-commit")
    plan.add_argument("--repo", required=True)
    plan.add_argument("--branch", required=True)
    plan.add_argument("--bundle", required=True)
    plan.add_argument("--dry-run", action="store_true")
    args, rest = parser.parse_known_args(argv)
    if args.cmd == "stage":
        path = HERE / "data" / "canonical" / "sync_status.json"
        print(path.read_text(encoding="utf-8") if path.exists() else json.dumps(sync.empty_status(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "github-commit":
        if not args.dry_run:
            print("refusing live GitHub write from this copy; pass --dry-run. A person merges the PR.", file=sys.stderr)
            return 2
        print(json.dumps(github_commit_plan(args.repo, args.branch, Path(args.bundle)), ensure_ascii=False, indent=2))
        return 0
    return sync.main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
