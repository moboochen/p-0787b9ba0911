#!/usr/bin/env python3
"""Idempotent review-site sync. Canonical data is written before the HTML build.

No force push, no token reading, no polling. A push or a local file change is
not a successful sync until `verify` sees this revision on the public URL.

  python3 tools/sync_site.py pack-bundle --legacy-html ... --state ... \\
      --proposals ... --inventory ... --qc ... --cake-scripts ... \\
      --cake-review ... --pick-queue ... --out /tmp/review-bundle.json
  python3 tools/sync_site.py apply --bundle /tmp/review-bundle.json
  python3 tools/sync_site.py build
  python3 tools/sync_site.py status
  python3 tools/sync_site.py deploy --branch cursor/shorts-review-sync-f53b
  python3 tools/sync_site.py verify --url https://moboochen.github.io/p-0787b9ba0911/Cdj1cq3x3gEFyC5WbNqRdjoU/
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reviewlib as rv
from render_page import write_page

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "data" / "canonical"
PAGE = ROOT / "Cdj1cq3x3gEFyC5WbNqRdjoU" / "index.html"
LIVE = "https://moboochen.github.io/p-0787b9ba0911/Cdj1cq3x3gEFyC5WbNqRdjoU/"


def redact(text: str) -> str:
    text = re.sub(r"x-access-token:[^@\s]+", "x-access-token:[REDACTED]", text or "")
    text = re.sub(r"ghp_[A-Za-z0-9]+", "[REDACTED]", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "[REDACTED]", text)
    return text


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def loadj(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dumpj(path: Path, obj) -> None:
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def paths(root: Path) -> dict[str, Path]:
    base = root / "data" / "canonical"
    return {
        "model": base / "model.json",
        "stills": base / "stills.json",
        "applied": base / "applied_events.jsonl",
        "inbox": base / "inbox.jsonl",
        "results": base / "event_results.jsonl",
        "status": base / "sync_status.json",
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    atomic_write(path, text)


def empty_status() -> dict:
    return {
        "canonical_revision": None,
        "built_revision": None,
        "last_successful_sync": None,
        "pending": None,
        "error": None,
        "outbox": [],
    }


def applied_ids(root: Path) -> set[str]:
    return {r.get("event_id") for r in read_jsonl(paths(root)["applied"])}


def remember_outbox(status: dict, revision: str, event_id: str) -> None:
    for row in status["outbox"]:
        if row["revision"] == revision:
            if event_id not in row["event_ids"]:
                row["event_ids"].append(event_id)
            row["verified"] = False
            return
    status["outbox"].append({"revision": revision, "event_ids": [event_id], "verified": False})


def pack_bundle(args) -> dict:
    qc_extra_note = "absent"
    if args.qc_extra:
        p = Path(args.qc_extra)
        qc_extra_note = "present" if p.exists() else "absent"
        if p.exists():
            # Presence is recorded. Records are not turned into cards here.
            json.loads(p.read_text(encoding="utf-8"))
    if not args.cake_review:
        raise SystemExit("cake-review is required")
    model, stills = rv.build_baseline({
        "legacy_html": args.legacy_html,
        "state": args.state,
        "inventory": args.inventory,
        "proposals": args.proposals,
        "cake_scripts": args.cake_scripts,
        "cake_review": args.cake_review,
        "pick_queue": args.pick_queue,
    })
    model["sources"]["qc_extra_ledger"] = qc_extra_note
    if args.qc and not Path(args.qc).exists():
        raise SystemExit("qc file missing")
    revision = rv.revision_of(model)
    event = {
        "event_id": "baseline-" + revision[:16],
        "type": "baseline_imported",
        "occurred_at": rv.now_taipei(),
        "payload": {"model_sha256": revision, "qc_extra_ledger": qc_extra_note},
    }
    bundle = {"bundle_version": 1, "revision": revision, "events": [event], "model": model, "stills": stills}
    text = json.dumps(bundle, ensure_ascii=False)
    if args.out:
        atomic_write(Path(args.out), text)
    return bundle


def apply_bundle(root: Path, bundle: dict, html_path: Path) -> dict:
    p = paths(root)
    status = loadj(p["status"], empty_status())
    applied = read_jsonl(p["applied"])
    known = {r["event_id"] for r in applied}
    inbox = read_jsonl(p["inbox"])
    queued = {r["event_id"] for r in inbox}
    for event in bundle.get("events") or []:
        eid = event.get("event_id")
        if not eid or not event.get("type"):
            raise SystemExit("event missing id or type")
        if eid in known or eid in queued:
            continue
        inbox.append(event)
        queued.add(eid)
    write_jsonl(p["inbox"], inbox)
    model = loadj(p["model"], rv.empty_model())
    stills = loadj(p["stills"], {})
    results = []
    remaining = []
    failed = None
    for event in inbox:
        if event["event_id"] in known:
            remaining_skip = True
            results.append({"event_id": event["event_id"], "status": "duplicate"})
            continue
        try:
            if event["type"] == "baseline_imported":
                incoming = bundle.get("model")
                if not incoming:
                    raise ValueError("baseline bundle missing model")
                if rv.sha256_text(rv.dumps(incoming)) != event.get("payload", {}).get("model_sha256") and event.get("payload", {}).get("model_sha256"):
                    # The pack step stores the hash. A hand-edited bundle must still match.
                    if rv.revision_of(incoming) != event["payload"]["model_sha256"]:
                        raise ValueError("baseline hash mismatch")
                model = rv.merge_baseline(model, incoming)
                if bundle.get("stills"):
                    stills.update(bundle["stills"])
                effect = {"effect": "baseline_upsert"}
            else:
                effect = rv.apply_mutation(model, event)
            problems = rv.invariants(model) if event["type"] == "baseline_imported" else []
            if problems:
                raise ValueError("invariants " + "; ".join(problems))
            applied.append({
                "event_id": event["event_id"],
                "type": event["type"],
                "applied_at": rv.now_taipei(),
                "effect": effect,
            })
            known.add(event["event_id"])
            results.append({"event_id": event["event_id"], "status": "applied", "effect": effect})
            dumpj(p["model"], model)
            dumpj(p["stills"], stills)
            write_jsonl(p["applied"], applied)
        except Exception as exc:  # noqa: BLE001 — keep the event for the next batch
            failed = {"event_id": event["event_id"], "error": str(exc)}
            remaining.append(event)
            results.append({"event_id": event["event_id"], "status": "error", "error": str(exc)})
            break
        else:
            remaining_skip = False
    else:
        remaining_skip = False
    if failed:
        # events after the failure stay queued, including the failed one
        idx = [e["event_id"] for e in inbox].index(failed["event_id"])
        remaining = inbox[idx:]
    write_jsonl(p["inbox"], remaining if failed else [])
    write_jsonl(p["results"], read_jsonl(p["results"]) + results)
    revision = rv.revision_of(model) if model.get("items") else None
    status["canonical_revision"] = revision
    status["last_successful_sync"] = status.get("last_successful_sync")
    if failed:
        status["error"] = {"at": rv.now_taipei(), "message": failed["error"], "event_id": failed["event_id"]}
        status["pending"] = {"revision": revision, "reason": "事件沒套完，已留在 inbox"}
        dumpj(p["status"], status)
        return status
    for event in bundle.get("events") or []:
        if event["event_id"] in known and revision:
            remember_outbox(status, revision, event["event_id"])
    status["error"] = None
    status["pending"] = {"revision": revision, "reason": "資料已寫入，公開網址尚未驗證"}
    try:
        built = write_page(html_path, model, stills, status)
        status["built_revision"] = built
    except Exception as exc:  # noqa: BLE001
        status["error"] = {"at": rv.now_taipei(), "message": "build failed: " + str(exc)}
        status["built_revision"] = None
    dumpj(p["status"], status)
    return status


def build_only(root: Path, html_path: Path) -> dict:
    p = paths(root)
    model = loadj(p["model"], None)
    if not model:
        raise SystemExit("no canonical model")
    stills = loadj(p["stills"], {})
    status = loadj(p["status"], empty_status())
    revision = rv.revision_of(model)
    status["canonical_revision"] = revision
    try:
        built = write_page(html_path, model, stills, status)
        status["built_revision"] = built
        status["error"] = None
        if status.get("last_successful_sync") and status.get("pending") is None:
            pass
        else:
            status["pending"] = {"revision": revision, "reason": "頁面已重建，公開網址尚未驗證"}
            status["last_successful_sync"] = None if status.get("built_revision") != revision else status.get("last_successful_sync")
    except Exception as exc:  # noqa: BLE001
        status["error"] = {"at": rv.now_taipei(), "message": str(exc)}
    dumpj(p["status"], status)
    return status


def verify(root: Path, url: str) -> dict:
    p = paths(root)
    status = loadj(p["status"], empty_status())
    local = status.get("built_revision")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            html = resp.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        status["error"] = {"at": rv.now_taipei(), "message": "verify fetch failed: " + redact(str(exc))}
        status["pending"] = {"revision": local, "reason": "驗證沒有連上公開網址"}
        dumpj(p["status"], status)
        return status
    m = re.search(r'name="review-revision" content="([0-9a-f]+)"', html)
    saw = m.group(1) if m else None
    if saw and saw == local and saw == status.get("canonical_revision"):
        status["last_successful_sync"] = rv.now_taipei()
        status["verified_revision"] = saw
        status["pending"] = None
        status["error"] = None
        status["outbox"] = [row for row in status.get("outbox") or [] if row.get("revision") != saw]
    else:
        status["error"] = {"at": rv.now_taipei(), "message": "公開頁修訂不符", "saw": saw, "expected": local}
        status["pending"] = {"revision": local, "reason": "公開網址還沒有這個修訂"}
        if status.get("verified_revision") != local:
            status["last_successful_sync"] = None
    dumpj(p["status"], status)
    return status


def deploy_argv(branch: str, force: bool = False) -> list[str]:
    if force or branch.startswith("-") or "--force" in branch:
        raise RuntimeError("force push refused")
    if branch in ("main", "master"):
        raise RuntimeError("refuse push to protected branch; open a PR and merge it")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
        raise RuntimeError("bad branch name")
    return ["git", "push", "-u", "origin", branch]


def deploy(root: Path, branch: str, dry_run: bool) -> dict:
    argv = deploy_argv(branch, force=False)
    status = loadj(paths(root)["status"], empty_status())
    if dry_run:
        print(json.dumps({"argv": argv, "force": False, "claims_synced": False}, ensure_ascii=False))
        return status
    proc = subprocess.run(argv, cwd=root, text=True, capture_output=True)
    out = redact(proc.stdout + "\n" + proc.stderr)
    if proc.returncode != 0:
        status["error"] = {"at": rv.now_taipei(), "message": "push failed", "detail": out[-2000:]}
        status["pending"] = {"revision": status.get("canonical_revision"), "reason": "push 失敗，outbox 保留"}
        dumpj(paths(root)["status"], status)
        sys.stderr.write(out)
        raise SystemExit(proc.returncode)
    status["pending"] = {"revision": status.get("built_revision"), "reason": "分支已推送，尚未合併，也尚未驗證公開網址"}
    status["error"] = None
    # A push is not a verified deploy.
    status["last_successful_sync"] = None
    dumpj(paths(root)["status"], status)
    print(json.dumps({"pushed_branch": branch, "last_successful_sync": None, "pending": status["pending"]}, ensure_ascii=False))
    return status


def self_check(root: Path) -> int:
    model = loadj(paths(root)["model"], None)
    if not model:
        print("no model")
        return 1
    problems = rv.invariants(model)
    html = PAGE.read_text(encoding="utf-8") if PAGE.exists() else ""
    rev = rv.revision_of(model)
    if f'content="{rev}"' not in html:
        problems.append("html revision mismatch")
    for banned in ("/workspace/", "local://", "C1_money.mp3", "aren't needed", "x-access-token"):
        if banned in html:
            problems.append("html banned " + banned)
    if problems:
        print("\n".join(problems))
        return 1
    print(json.dumps({"ok": True, "revision": rev, "items": len(model["items"])}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if any(a in ("--force", "-f") or a.startswith("--force") for a in argv):
        print("force push refused", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description="Sync the shorts review site without force-pushing")
    parser.add_argument("--root", default=str(ROOT))
    sub = parser.add_subparsers(dest="cmd", required=True)

    pack = sub.add_parser("pack-bundle")
    pack.add_argument("--legacy-html", required=True)
    pack.add_argument("--state", required=True)
    pack.add_argument("--proposals", required=True)
    pack.add_argument("--inventory", required=True)
    pack.add_argument("--qc")
    pack.add_argument("--qc-extra")
    pack.add_argument("--cake-scripts", required=True)
    pack.add_argument("--cake-review")
    pack.add_argument("--pick-queue", required=True)
    pack.add_argument("--out", required=True)

    apply_p = sub.add_parser("apply")
    apply_p.add_argument("--bundle", required=True)
    apply_p.add_argument("--html", default=str(PAGE))

    build_p = sub.add_parser("build")
    build_p.add_argument("--html", default=str(PAGE))

    sub.add_parser("status")

    ver = sub.add_parser("verify")
    ver.add_argument("--url", default=LIVE)

    dep = sub.add_parser("deploy")
    dep.add_argument("--branch", required=True)
    dep.add_argument("--dry-run", action="store_true")

    sub.add_parser("self-check")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.cmd == "pack-bundle":
        bundle = pack_bundle(args)
        print(json.dumps({"out": args.out, "revision": bundle["revision"], "events": [e["event_id"] for e in bundle["events"]]}, ensure_ascii=False))
        return 0
    if args.cmd == "apply":
        bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
        status = apply_bundle(root, bundle, Path(args.html))
        print(json.dumps({"canonical_revision": status.get("canonical_revision"), "built_revision": status.get("built_revision"), "last_successful_sync": status.get("last_successful_sync"), "pending": status.get("pending"), "error": status.get("error")}, ensure_ascii=False))
        return 0 if not status.get("error") else 1
    if args.cmd == "build":
        status = build_only(root, Path(args.html))
        print(json.dumps({"built_revision": status.get("built_revision"), "last_successful_sync": status.get("last_successful_sync"), "error": status.get("error")}, ensure_ascii=False))
        return 0 if not status.get("error") else 1
    if args.cmd == "status":
        print(paths(root)["status"].read_text(encoding="utf-8") if paths(root)["status"].exists() else "{}")
        return 0
    if args.cmd == "verify":
        status = verify(root, args.url)
        print(json.dumps({"last_successful_sync": status.get("last_successful_sync"), "pending": status.get("pending"), "error": status.get("error")}, ensure_ascii=False))
        return 0 if status.get("last_successful_sync") else 1
    if args.cmd == "deploy":
        deploy(root, args.branch, args.dry_run)
        return 0
    if args.cmd == "self-check":
        return self_check(root)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
