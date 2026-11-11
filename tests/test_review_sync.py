#!/usr/bin/env python3
"""Sync contract and review-page invariants."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import reviewlib as rv
import sync_site as sync

MODEL = json.loads((ROOT / "data/canonical/model.json").read_text(encoding="utf-8"))
HTML = (ROOT / "Cdj1cq3x3gEFyC5WbNqRdjoU/index.html").read_text(encoding="utf-8")


def test_committed_model_invariants():
    assert rv.invariants(MODEL) == []
    assert rv.revision_of(MODEL) in HTML
    for banned in ("/workspace/", "local://", "C1_money.mp3", ".mp3", "aren't needed", "x-access-token", "high-school ones"):
        assert banned not in HTML
        assert banned not in json.dumps(MODEL, ensure_ascii=False)


def test_cake_draft_flags_and_ranges():
    c1 = MODEL["items"]["Cake-C1"]
    c4 = MODEL["items"]["Cake-C4"]
    assert c1["range"] == "1110.254–1174.950"
    assert c1["duration"] == 64.7
    assert c4["range"] == "2402.958–2464.230"
    assert c4["duration"] == 61.3
    assert len(c1["sentences"]) == 23
    assert len(c4["sentences"]) == 26
    for cid in ("Cake-C1", "Cake-C2", "Cake-C3", "Cake-C4", "Cake-C5"):
        it = MODEL["items"][cid]
        assert it["section"] == "script"
        assert it["flags"] == {
            "proposal_selected": True,
            "script_approved": False,
            "cut_authorized": False,
            "publish_approved": False,
        }
        assert it["qc_status"] == "not_run" and it["timing_provisional"] is True
        assert it["qc"]["ready"] is False
    edu = next(s for s in c4["sentences"] if s["en_status"] == "blank_pending")
    assert edu["en_display"] == "英文待中文確認後翻譯"
    assert "不需要" in "\n".join(edu["lines"])
    assert "待確認" not in "\n".join(edu["lines"])
    assert edu["review_audio"]["hosted"] is False
    assert edu["review_audio"]["watch"].startswith("https://www.youtube.com/watch")
    money = next(s for s in c1["sentences"] if s["uncertainty_id"] == "c1-money")
    assert "15%也100多萬" in money["note"]
    assert "15%也100多萬" not in "\n".join(money["lines"])
    c2 = MODEL["items"]["Cake-C2"]
    assert any("不把它定成講者口誤" in u["detail"] or "不把它定成講者口誤" in (c2.get("selection_note") or "") for u in c2["uncertainties"]) or any(
        "口誤" in u["detail"] and "不把" in u["detail"] for u in c2["uncertainties"]
    )


def test_views_and_platforms():
    items = list(MODEL["items"].values())
    new = {it["id"] for it in items if it["section"] == "new"}
    script = {it["id"] for it in items if it["section"] == "script"}
    assert len(new) == 48 and not (set(rv.PICK_IDS) & new)
    assert set(rv.PICK_IDS) <= script
    approved = [it for it in items if it["section"] == "approved"]
    assert len(approved) == 16
    assert all(it["flags"]["script_approved"] and not it["flags"]["publish_approved"] and not it["flags"]["cut_authorized"] for it in approved)
    assert MODEL["items"]["script:C"]["flags"]["script_approved"] is False
    previews = [it for it in items if (it.get("preview") or {}).get("access") == "private_owner_sign_in"]
    assert len(previews) == 14
    assert all(it["media"]["video_label"] == "開啟Drive審片" and it["media"]["video"].startswith("https://drive.google.com/") for it in previews)
    assert all(not it["flags"]["publish_approved"] and not it["qc"]["ready"] for it in previews)
    assert "4年升Meta主管" not in json.dumps(MODEL, ensure_ascii=False)
    oct29 = [it for it in items if it["id"].startswith("cut:") and it["platforms"]["fb"]["published"]]
    assert len(oct29) == 3
    assert all(it["platforms"]["ig"]["published"] and not it["platforms"]["yt"]["published"] for it in oct29)
    assert all(it["section"] == "cut" for it in oct29)
    assert sum(1 for it in items if it["section"] == "published") == 3
    assert all(not it["qc"]["ready"] for it in items)
    assert all(not it["flags"]["publish_approved"] for it in items)


def test_sanitize_blocks_guess_and_notes():
    sent = rv.sanitize_sentence({
        "start": 1,
        "end": 2,
        "zh": "那實際上高中學歷的不需要",
        "lines": ["那實際上高中學歷的不需要", "待確認：這是註記不是字幕"],
        "en": "In reality, high-school ones aren't needed,",
        "note": "待確認：語意未定。音訊 audio/C4_c.mp3",
        "timing_provisional": True,
    }, "c4-edu")
    assert sent["en_display"] == "英文待中文確認後翻譯"
    assert sent["en_status"] == "blanked_unsupported"
    assert all("待確認" not in ln for ln in sent["lines"])
    assert "C4_c.mp3" not in sent["note"]
    assert sent["review_audio"]["embed"].startswith("https://www.youtube.com/embed/")
    assert sent["spoken_includes_note"] is False


def test_qc_gate_requires_both_and_identity():
    short = {"result": "PASS", "mtime": 1, "size": 2, "fails": [], "warns": []}
    extra = {"result": "PASS", "mtime": 1, "size": 2, "fails": [], "warns": []}
    assert rv.qc_gate(short, None, 1, 2)["ready"] is False
    assert rv.qc_gate(short, extra, 9, 2)["ready"] is False
    assert rv.qc_gate(short, extra, 1, 2)["ready"] is True
    warned = {"result": "WARN", "mtime": 1, "size": 2, "fails": [], "warns": ["行長"]}
    assert rv.qc_gate(short, warned, 1, 2)["ready"] is False
    assert rv.qc_gate(short, warned, 1, 2, ["行長"])["ready"] is True


def _base_item():
    return {
        "id": "X1",
        "kind": "cut",
        "section": "cut",
        "title": "測試",
        "ep": "EP1",
        "flags": rv.flags(),
        "platforms": rv.empty_platforms(),
        "qc": rv.not_run_qc("none"),
        "artifact": {"id": "art-1", "label": "x"},
        "script_complete": False,
        "sentences": [],
    }


def test_events_are_idempotent_and_do_not_cross_flags(tmp_path: Path):
    root = tmp_path
    model = rv.empty_model()
    model["items"]["X1"] = _base_item()
    sync.dumpj(sync.paths(root)["model"], model)
    sync.dumpj(sync.paths(root)["stills"], {})
    sync.write_jsonl(sync.paths(root)["applied"], [])
    sync.write_jsonl(sync.paths(root)["inbox"], [])
    sync.write_jsonl(sync.paths(root)["results"], [])
    event = {
        "event_id": "pub-fb-1",
        "type": "publication_verified",
        "occurred_at": "2026-11-09T12:00:00+08:00",
        "payload": {"item_id": "X1", "platform": "fb", "published": True, "date": "2026-10-29", "evidence": "對話"},
    }
    bundle = {"bundle_version": 1, "events": [event]}
    html = tmp_path / "index.html"
    # publication events don't need a full page; point html at tmp and skip by using apply
    # apply always builds. The model is tiny.
    status = sync.apply_bundle(root, bundle, html)
    assert status["error"] is None
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["X1"]
    assert item["platforms"]["fb"]["published"] is True
    assert item["platforms"]["yt"]["published"] is False
    assert item["flags"]["publish_approved"] is False
    status2 = sync.apply_bundle(root, bundle, html)
    assert status2["error"] is None
    applied = sync.read_jsonl(sync.paths(root)["applied"])
    assert [r["event_id"] for r in applied].count("pub-fb-1") == 1
    qc = {
        "event_id": "qc-short-only",
        "type": "QC_completed",
        "occurred_at": "2026-11-09T12:01:00+08:00",
        "payload": {
            "item_id": "X1",
            "artifact_id": "art-1",
            "file_mtime": 1,
            "file_size": 2,
            "qc_short": {"result": "PASS", "mtime": 1, "size": 2, "fails": [], "warns": []},
            "qc_extra": None,
        },
    }
    sync.apply_bundle(root, {"bundle_version": 1, "events": [qc]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["X1"]
    assert item["qc"]["ready"] is False
    assert item["flags"]["publish_approved"] is False
    both = dict(qc)
    both["event_id"] = "qc-both"
    both["payload"] = dict(qc["payload"])
    both["payload"]["qc_extra"] = {"result": "PASS", "mtime": 1, "size": 2, "fails": [], "warns": []}
    sync.apply_bundle(root, {"bundle_version": 1, "events": [both]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["X1"]
    assert item["qc"]["ready"] is True
    assert item["flags"]["publish_approved"] is False
    claim = {
        "event_id": "email-publish-1",
        "type": "email_parsed",
        "occurred_at": "2026-11-09T12:02:00+08:00",
        "payload": {"kind": "publish", "message_id": "m1", "decisions": [
            {"item_id": "X1", "artifact_id": "wrong", "publish_approved": True},
        ]},
    }
    sync.apply_bundle(root, {"bundle_version": 1, "events": [claim]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["X1"]
    assert item["flags"]["publish_approved"] is False
    claim["event_id"] = "email-publish-2"
    claim["payload"]["decisions"][0]["artifact_id"] = "art-1"
    sync.apply_bundle(root, {"bundle_version": 1, "events": [claim]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["X1"]
    assert item["flags"]["publish_approved"] is True
    assert item["flags"]["script_approved"] is False
    assert item["flags"]["cut_authorized"] is False


def test_script_events_do_not_authorize_cut_or_publish(tmp_path: Path):
    root = tmp_path
    sync.dumpj(sync.paths(root)["model"], rv.empty_model())
    sync.dumpj(sync.paths(root)["stills"], {})
    for name in ("applied", "inbox", "results"):
        sync.write_jsonl(sync.paths(root)[name], [])
    created = {
        "event_id": "script-new",
        "type": "script_created",
        "occurred_at": "2026-11-09T12:00:00+08:00",
        "payload": {"item": {
            "id": "Cake-C9",
            "title": "不該核准",
            "ep": "Cake",
            "artifact": {"id": "cake-c9-art", "label": "Cake-C9"},
            "sentences": [{"start": 1, "end": 2, "zh": "你好", "en": "Hi", "lines": ["你好"], "note": "待確認：也許"}],
        }},
    }
    html = tmp_path / "index.html"
    sync.apply_bundle(root, {"bundle_version": 1, "events": [created]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["Cake-C9"]
    assert item["flags"]["script_approved"] is False
    assert item["flags"]["cut_authorized"] is False
    assert item["section"] == "script"
    assert item["sentences"][0]["en_status"] == "provisional"
    approved = {
        "event_id": "script-ok",
        "type": "script_approved",
        "occurred_at": "2026-11-09T12:03:00+08:00",
        "payload": {"item_id": "Cake-C9", "artifact_id": item["artifact"]["id"], "confirm": True},
    }
    sync.apply_bundle(root, {"bundle_version": 1, "events": [approved]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["Cake-C9"]
    assert item["section"] == "approved"
    assert item["flags"]["script_approved"] is True
    assert item["flags"]["cut_authorized"] is False
    assert item["flags"]["publish_approved"] is False


def test_failed_verify_keeps_outbox(tmp_path: Path, monkeypatch):
    root = tmp_path
    status = {
        "canonical_revision": "abc",
        "built_revision": "abc",
        "last_successful_sync": None,
        "verified_revision": None,
        "pending": {"revision": "abc"},
        "error": None,
        "outbox": [{"revision": "abc", "event_ids": ["e1"], "verified": False}],
    }
    sync.dumpj(sync.paths(root)["status"], status)

    def boom(url, timeout=60):
        raise OSError("offline")

    monkeypatch.setattr(sync.urllib.request, "urlopen", boom)
    got = sync.verify(root, "https://example.invalid/")
    assert got["last_successful_sync"] is None
    assert got["outbox"][0]["event_ids"] == ["e1"]
    assert got["error"]["message"].startswith("verify fetch failed")


def test_youtube_without_absence_is_unverified():
    slot = rv.platform_slot("YouTube", published=False, source="sheet 沒勾")
    assert slot["verification"] == "unverified"
    assert slot["published"] is False
    absent = rv.platform_slot("YouTube", published=False, confirmed_absent=True, source="人工確認未上傳")
    assert absent["verification"] == "not_published"
    posted = rv.platform_slot("YouTube", published=True, url="https://www.youtube.com/shorts/abc", date="2026-09-30", source="detected")
    assert posted["verification"] == "published"
    for it in MODEL["items"].values():
        yt = (it.get("platforms") or {}).get("yt")
        if not yt or yt["published"]:
            continue
        assert yt["verification"] == "unverified"


def test_script_approval_is_version_scoped_and_survives_qc_mismatch(tmp_path: Path):
    root = tmp_path
    sync.dumpj(sync.paths(root)["model"], rv.empty_model())
    sync.dumpj(sync.paths(root)["stills"], {})
    for name in ("applied", "inbox", "results"):
        sync.write_jsonl(sync.paths(root)[name], [])
    html = tmp_path / "index.html"
    created = {
        "event_id": "script-v",
        "type": "script_created",
        "occurred_at": "2026-11-09T12:00:00+08:00",
        "payload": {"item": {
            "id": "EP-S",
            "title": "版本",
            "ep": "EP1",
            "artifact": {"id": "art-s", "label": "EP-S", "bytes": 10},
            "sentences": [{"start": 1, "end": 2, "zh": "舊稿", "en": "old", "lines": ["舊稿"]}],
        }},
    }
    sync.apply_bundle(root, {"bundle_version": 1, "events": [created]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["EP-S"]
    old_sha = rv.script_text_sha(item["sentences"])
    approved = {
        "event_id": "approve-old",
        "type": "script_approved",
        "occurred_at": "2026-11-09T12:10:00+08:00",
        "payload": {"item_id": "EP-S", "confirm": True, "text_sha256": old_sha, "source": "review_20261026.md", "version_id": "v-old"},
    }
    sync.apply_bundle(root, {"bundle_version": 1, "events": [approved]}, html)
    changed = {
        "event_id": "script-new-text",
        "type": "script_created",
        "occurred_at": "2026-11-09T12:20:00+08:00",
        "payload": {"item": {
            "id": "EP-S",
            "title": "版本",
            "ep": "EP1",
            "artifact": {"id": "art-s", "label": "EP-S", "bytes": 10},
            "sentences": [{"start": 1, "end": 2, "zh": "新稿", "en": "new", "lines": ["新稿"]}],
            "approved_versions": json.loads(sync.paths(root)["model"].read_text())["items"]["EP-S"]["approved_versions"],
        }},
    }
    sync.apply_bundle(root, {"bundle_version": 1, "events": [changed]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["EP-S"]
    assert item["flags"]["script_approved"] is False
    assert item["section"] == "script"
    assert item["approved_versions"][0]["script_approved"] is True
    assert item["approved_versions"][0]["text_sha256"] == old_sha
    assert rv.script_text_sha(item["sentences"]) != old_sha
    qc = {
        "event_id": "qc-stale",
        "type": "QC_completed",
        "occurred_at": "2026-11-09T12:30:00+08:00",
        "payload": {
            "item_id": "EP-S",
            "artifact_id": "art-s",
            "file_mtime": 5,
            "file_size": 10,
            "qc_short": {"result": "PASS", "mtime": 1, "size": 10, "fails": [], "warns": []},
            "qc_extra": {"result": "PASS", "mtime": 1, "size": 10, "fails": [], "warns": []},
        },
    }
    sync.apply_bundle(root, {"bundle_version": 1, "events": [qc]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["EP-S"]
    assert item["qc"]["ready"] is False
    assert item["approved_versions"][0]["script_approved"] is True
    assert item["flags"]["script_approved"] is False


def test_preview_requires_matching_artifact_and_https(tmp_path: Path):
    root = tmp_path
    model = rv.empty_model()
    item = _base_item()
    item["media"] = {"video": None, "missing": "none"}
    model["items"]["X1"] = item
    sync.dumpj(sync.paths(root)["model"], model)
    sync.dumpj(sync.paths(root)["stills"], {})
    for name in ("applied", "inbox", "results"):
        sync.write_jsonl(sync.paths(root)[name], [])
    html = tmp_path / "index.html"
    bad = {
        "event_id": "prev-bad",
        "type": "preview_attached",
        "occurred_at": "2026-11-09T12:00:00+08:00",
        "payload": {"item_id": "X1", "artifact_id": "art-1", "video_url": "file:///tmp/a.mp4"},
    }
    sync.apply_bundle(root, {"bundle_version": 1, "events": [bad]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["X1"]
    assert not item["media"].get("video")
    mismatch = dict(bad)
    mismatch["event_id"] = "prev-mismatch"
    mismatch["payload"] = {"item_id": "X1", "artifact_id": "other", "video_url": "https://drive.google.com/file/d/abc/view"}
    sync.apply_bundle(root, {"bundle_version": 1, "events": [mismatch]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["X1"]
    assert not item["media"].get("video")
    ok = dict(bad)
    ok["event_id"] = "prev-ok"
    ok["payload"] = {"item_id": "X1", "artifact_id": "art-1", "video_url": "https://drive.google.com/file/d/abc/view"}
    sync.apply_bundle(root, {"bundle_version": 1, "events": [ok]}, html)
    item = json.loads(sync.paths(root)["model"].read_text())["items"]["X1"]
    assert item["media"]["video"].startswith("https://drive.google.com/")
    assert item["qc"]["ready"] is False
    assert item["flags"]["publish_approved"] is False


def test_build_does_not_mark_deployed(tmp_path: Path):
    root = tmp_path
    model = rv.empty_model()
    model["items"]["X1"] = _base_item()
    sync.dumpj(sync.paths(root)["model"], model)
    sync.dumpj(sync.paths(root)["stills"], {})
    status = sync.build_only(root, tmp_path / "index.html")
    assert status["stages"]["built"]["revision"]
    assert status["stages"]["pushed_branch"] is None
    assert status["stages"]["merged"] is None
    assert status["stages"]["deployed"] is None
    assert status["stages"]["verified"] is None
    assert status["last_successful_sync"] is None


def test_box_plan_does_not_publish_or_merge(tmp_path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("sync_box", ROOT / "box" / "review-sync" / "sync_box.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    bundle = tmp_path / "bundle.json"
    bundle.write_text("{}", encoding="utf-8")
    plan = mod.github_commit_plan("moboochen/p-0787b9ba0911", "cursor/shorts-review-sync-f53b", bundle)
    assert plan["publishes_pages"] is False and plan["merges"] is False and plan["force"] is False
    try:
        mod.github_commit_plan("moboochen/p-0787b9ba0911", "main", bundle)
    except RuntimeError as exc:
        assert "refuse" in str(exc)
    else:
        raise AssertionError("main was allowed")


def test_deploy_refuses_force_and_main():
    try:
        rv_argv = sync.deploy_argv("cursor/shorts-review-sync-f53b", force=True)
    except RuntimeError as exc:
        assert "force" in str(exc)
    else:
        raise AssertionError(rv_argv)
    try:
        sync.deploy_argv("main")
    except RuntimeError as exc:
        assert "protected" in str(exc) or "refuse" in str(exc)
    else:
        raise AssertionError("main was allowed")
    argv = sync.deploy_argv("cursor/shorts-review-sync-f53b")
    assert argv == ["git", "push", "-u", "origin", "cursor/shorts-review-sync-f53b"]
    assert "--force" not in argv
    assert sync.main(["--force", "status"]) == 2
