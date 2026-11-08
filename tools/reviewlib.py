#!/usr/bin/env python3
"""Canonical review model, QC gate, and idempotent sync mutations.

The public page is rendered from this model. Filesystem paths and tokens never
become public URLs. Publication readiness requires both qc_short and qc_extra
to pass for the same bytes/mtime, or warns listed in that event's
accepted_warns. Notes never become spoken subtitles.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=8))
YT_ID = "e0U-vx2OWc0"
YT_OFFSET_0073 = 1512.504
BANNED_EN = (
    "high-school ones aren't needed",
    "high-school ones aren’t needed",
    "in reality, high-school ones",
)
BLANK_EN = "英文待中文確認後翻譯"
PROVISIONAL_MARK = "（暫譯，待中文確認）"
LEGACY_DRAFT_KEYS = ("pubsched_v2", "props_v1")
PICK_IDS = (
    "EP220-Q2",
    "EP220-Q3",
    "EP220-Q4",
    "EP220-Q5",
    "EP220-Q6",
    "EP220-Q7",
    "EP220-H1",
    "EP220-H2",
    "EP220-H5",
    "EP220-H7",
    "EP198-H7",
)
# Windows named in cake_review_3aff.md. 0072 starts at 0; 0073 starts at 1512.504s.
AUDIO_WINDOWS = {
    "audio/C1_money.mp3": {
        "start": 1138,
        "end": 1154,
        "title": "C1 金額用詞",
        "uncertainty_id": "c1-money",
    },
    "audio/C2_AB.mp3": {
        "start": int(YT_OFFSET_0073 + 1024),
        "end": int(YT_OFFSET_0073 + 1040 + 0.999),
        "title": "C2 A/B 公司與最高／最低",
        "uncertainty_id": "c2-ab",
    },
    "audio/C4_a.mp3": {
        "start": int(YT_OFFSET_0073 + 892),
        "end": int(YT_OFFSET_0073 + 918 + 0.999),
        "title": "C4 字序：長得／順眼／有正當工作",
        "uncertainty_id": "c4-order",
    },
    "audio/C4_c.mp3": {
        "start": int(YT_OFFSET_0073 + 938),
        "end": int(YT_OFFSET_0073 + 950 + 0.999),
        "title": "C4「高中學歷的／不需要」",
        "uncertainty_id": "c4-edu",
    },
}
UNCERTAINTIES = [
    {
        "id": "c1-money",
        "clip": "Cake-C1",
        "title": "C1 金額用詞尚未確認",
        "detail": "SRT 寫「大約一百多萬 其實也沒多少錢」。另一遍小窗聽寫的字句不同，金額「一百多萬」兩邊一致。英文只是暫譯，不能當字幕。",
        "audio_key": "audio/C1_money.mp3",
    },
    {
        "id": "c2-ab",
        "clip": "Cake-C2",
        "title": "C2 的 A/B 公司與最高／最低尚未確認",
        "detail": "兩種轉錄對「B公司」以及「最高／最低」不一致。可能是口誤，也可能是轉錄誤差。本頁不把它定成講者口誤。",
        "audio_key": "audio/C2_AB.mp3",
    },
    {
        "id": "c4-edu",
        "clip": "Cake-C4",
        "title": "C4「高中學歷的／不需要」語意未定",
        "detail": "中文保留原詞，不做推論，也不把聽寫差異寫成事實。這句沒有確定英文。",
        "audio_key": "audio/C4_c.mp3",
    },
    {
        "id": "c4-order",
        "clip": "Cake-C4",
        "title": "C4「長得／順眼／有正當工作」字序未定",
        "detail": "SRT 字序與小窗聽寫不同。英文是暫譯，不是定稿字幕。",
        "audio_key": "audio/C4_a.mp3",
    },
]
HTTPS_PREFIXES = (
    "https://drive.google.com/",
    "https://docs.google.com/",
    "https://www.youtube.com/",
    "https://youtube.com/",
    "https://youtu.be/",
    "https://www.youtube-nocookie.com/",
)


def now_taipei() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def fmt_epoch(epoch) -> str | None:
    if epoch in (None, ""):
        return None
    return datetime.fromtimestamp(float(epoch), TZ).strftime("%Y-%m-%d %H:%M")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def https_url(url) -> str | None:
    if not isinstance(url, str):
        return None
    if url.startswith(HTTPS_PREFIXES):
        return url
    return None


def rel_media(path: str) -> str:
    path = str(path).replace("\\", "/")
    if "/shorts/" in path:
        return path.split("/shorts/", 1)[1]
    return Path(path).name


def yt_window(start: int, end: int, title: str) -> dict:
    return {
        "title": title,
        "start": int(start),
        "end": int(end),
        "watch": f"https://www.youtube.com/watch?v={YT_ID}&t={int(start)}s",
        "embed": f"https://www.youtube.com/embed/{YT_ID}?start={int(start)}&end={int(end)}",
        "hosted": False,
        "note": "播放的是已公開的 YouTube 原片時間窗。本站不存放、不另傳這段音檔。",
    }


def review_audio(key: str) -> dict | None:
    spec = AUDIO_WINDOWS.get(key)
    if not spec:
        return None
    return yt_window(spec["start"], spec["end"], spec["title"]) | {"uncertainty_id": spec["uncertainty_id"]}


def clean_note(note: str) -> str:
    note = note or ""
    note = re.sub(r"/workspace/\S+", "（路徑已省略）", note)
    note = note.replace("local://", "")
    for key, spec in AUDIO_WINDOWS.items():
        pretty = f"YouTube {spec['start']}–{spec['end']} 秒（公開原片，本站無音檔）"
        note = note.replace(key, pretty)
        note = note.replace(Path(key).name, pretty)
    note = re.sub(r"\s+", " ", note).strip()
    return note


def _banned(en: str) -> bool:
    low = en.lower()
    return any(b in low for b in BANNED_EN)


def classify_en(en: str, note: str) -> tuple[str, str]:
    en = (en or "").strip()
    unresolved = "待確認" in (note or "")
    if _banned(en):
        return BLANK_EN, "blanked_unsupported"
    if en in ("", BLANK_EN) or "英文待中文確認後翻譯" in en:
        return BLANK_EN, "blank_pending"
    if en.startswith(PROVISIONAL_MARK) or "暫譯" in en or "待中文確認" in en or unresolved:
        if not en.startswith(PROVISIONAL_MARK):
            en = PROVISIONAL_MARK + en
        return en, "provisional"
    return en, "translation"


def sanitize_sentence(chunk: dict, uncertainty_id: str | None = None) -> dict:
    """Spoken text is zh lines only. Notes, flags, and guesses stay notes."""
    note = clean_note(str(chunk.get("note") or ""))
    flags = chunk.get("flags") or []
    if isinstance(flags, list) and flags:
        note = (note + " " + "；".join(str(x) for x in flags)).strip()
    lines: list[str] = []
    for raw in chunk.get("lines") or []:
        ln = str(raw).strip()
        if not ln:
            continue
        if "待確認" in ln or "whisper" in ln.lower() or "音訊 " in ln or ln == note:
            note = clean_note((note + " " + ln).strip())
            continue
        lines.append(ln)
    zh = str(chunk.get("zh") or "").strip()
    if zh and ("待確認" in zh or "whisper" in zh.lower()):
        note = clean_note((note + " " + zh).strip())
        zh = ""
    if not lines and zh:
        lines = [zh]
    en_display, en_status = classify_en(str(chunk.get("en") or ""), note)
    audio = None
    if uncertainty_id:
        for spec in UNCERTAINTIES:
            if spec["id"] == uncertainty_id:
                audio = review_audio(spec["audio_key"])
                break
    return {
        "start": chunk.get("start"),
        "end": chunk.get("end"),
        "lines": lines,
        "zh": zh or (lines[0] if lines else ""),
        "en_display": en_display,
        "en_status": en_status,
        "note": note,
        "timing_provisional": True if chunk.get("timing_provisional", True) else False,
        "timing": chunk.get("timing") or "SRT cue，暫排，需 paraformer 逐字對齊",
        "uncertainty_id": uncertainty_id,
        "review_audio": audio,
        "spoken_includes_note": False,
    }


def sentence_uncertainty(clip_id: str, chunk: dict) -> str | None:
    note = str(chunk.get("note") or "")
    start = float(chunk.get("start") or 0)
    if "C1_money" in note or (clip_id == "Cake-C1" and abs(start - 1146.27) < 0.2):
        if "待確認" in note or abs(start - 1146.27) < 0.2 and "一百多萬" in str(chunk.get("zh")):
            if "待確認" in note or "暫譯" in str(chunk.get("en") or ""):
                return "c1-money"
    if "C2_AB" in note or (clip_id == "Cake-C2" and 2542 <= start <= 2544.2 and "暫譯" in str(chunk.get("en") or "")):
        return "c2-ab"
    if "C4_a" in note or (clip_id == "Cake-C4" and 2410 <= start <= 2413 and "暫譯" in str(chunk.get("en") or "")):
        return "c4-order"
    if "C4_c" in note or (clip_id == "Cake-C4" and 2454 <= start <= 2458 and ("英文待中文" in str(chunk.get("en") or "") or "暫譯" in str(chunk.get("en") or ""))):
        return "c4-edu"
    return None


def assess_qc(rec: dict | None, file_mtime, file_size, accepted_warns: list | None = None) -> dict:
    accepted = [str(x) for x in (accepted_warns or [])]
    if not rec:
        return {"state": "absent", "pass": False, "identity_match": False, "result_raw": None, "detail": "沒有紀錄"}
    try:
        identity = int(rec.get("mtime")) == int(file_mtime) and int(rec.get("size")) == int(file_size)
    except (TypeError, ValueError):
        identity = False
    fails = list(rec.get("fails") or [])
    warns = [str(w) for w in (rec.get("warns") or [])]
    result = rec.get("result")
    base = {
        "identity_match": identity,
        "result_raw": result,
        "fails": fails,
        "warns": warns,
        "spec": rec.get("spec"),
        "at": rec.get("at"),
        "record_mtime": rec.get("mtime"),
        "file_mtime": file_mtime,
    }
    if not identity:
        return base | {"state": "stale", "pass": False, "detail": "舊紀錄與現檔的 mtime 或大小不一致，不能當成通過"}
    if fails or result == "FAIL":
        return base | {"state": "fail", "pass": False, "detail": "紀錄是失敗"}
    warn_ok = bool(warns) and set(warns) <= set(accepted)
    if result == "PASS" and not warns:
        return base | {"state": "pass", "pass": True, "detail": "qc 通過且身份一致"}
    if result in ("PASS", "WARN") and warn_ok:
        return base | {"state": "warn_accepted", "pass": True, "detail": "警告已在這次事件裡明示接受"}
    if result in ("PASS", "WARN") and warns:
        return base | {"state": "warn_unaccepted", "pass": False, "detail": "有警告，但沒有被這次事件明示接受"}
    return base | {"state": "not_pass", "pass": False, "detail": "不是通過"}


def qc_gate(short_rec, extra_rec, file_mtime, file_size, accepted_warns=None) -> dict:
    short = assess_qc(short_rec, file_mtime, file_size, accepted_warns)
    extra = assess_qc(extra_rec, file_mtime, file_size, accepted_warns)
    if extra_rec is None and extra["state"] == "absent":
        extra["detail"] = "沒有 qc_extra 台帳"
    ready = bool(short["pass"] and extra["pass"])
    reason = ""
    if not ready:
        reason = "不能放行：qc_short=" + short["state"] + "；qc_extra=" + extra["state"]
    return {"short": short, "extra": extra, "ready": ready, "block_reason": reason, "accepted_warns": list(accepted_warns or [])}


def not_run_qc(detail: str) -> dict:
    part = {"state": "not_run", "pass": False, "identity_match": False, "result_raw": None, "detail": detail}
    return {"short": part, "extra": dict(part), "ready": False, "block_reason": "不能放行：" + detail, "accepted_warns": []}


def flags(selected=False, script=False, cut=False, publish=False) -> dict:
    return {
        "proposal_selected": bool(selected),
        "script_approved": bool(script),
        "cut_authorized": bool(cut),
        "publish_approved": bool(publish),
    }


def empty_platforms() -> dict:
    return {
        k: {"label": lab, "published": False, "date": None, "source": None, "url": None}
        for k, lab in (("yt", "YouTube"), ("fb", "Facebook"), ("ig", "Instagram"))
    }


def hms_to_seconds(text: str) -> int | None:
    if not text or not isinstance(text, str):
        return None
    parts = text.strip().split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        return int(nums[0] * 60 + nums[1])
    if len(nums) == 3:
        return int(nums[0] * 3600 + nums[1] * 60 + nums[2])
    return None


def norm_name(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text or "")


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_legacy_html(path: Path) -> dict:
    html = Path(path).read_text(encoding="utf-8")
    i = html.find("var D=")
    j = html.find(";var KEY=")
    if i < 0 or j < 0:
        raise ValueError("legacy scheduler html has no embedded data")
    return json.loads(html[i + 6 : j])


def index_state(state: dict) -> dict:
    out = {}
    for key, row in (state.get("shorts") or {}).items():
        row = dict(row)
        row["_key"] = key
        out[key] = row
        if row.get("drive_id"):
            out[row["drive_id"]] = row
        if row.get("card_id"):
            out[row["card_id"]] = row
            out["local-" + row["card_id"]] = row
    return out


def parse_pick_ids(text: str) -> list[str]:
    ids = []
    for line in text.splitlines():
        m = re.match(r"^(EP\d+-[A-Z]+\d+)\s*\|", line.strip())
        if m:
            ids.append(m.group(1))
    if ids != list(PICK_IDS):
        raise ValueError(f"pick queue ids {ids} != expected {list(PICK_IDS)}")
    return ids


def platforms_from_legacy(raw: dict) -> dict:
    plats = empty_platforms()
    for key in ("yt", "fb", "ig"):
        src = (raw or {}).get(key) or {}
        plats[key]["published"] = bool(src.get("ok"))
        plats[key]["date"] = src.get("date")
        plats[key]["source"] = src.get("src")
        plats[key]["url"] = https_url(src.get("url"))
    return plats


def historical_from_state(row: dict | None) -> dict | None:
    if not row or not row.get("approval"):
        return None
    return {
        "decision": row.get("approval"),
        "at": row.get("approval_at"),
        "source": row.get("approval_source"),
        "applies_to_current_file": False,
        "note": "這是舊卡片上記下的決定，沒有綁到現檔的 bytes/mtime，不能當成這次發佈核准。",
    }


def hold_from_state(row: dict | None) -> dict | None:
    if not row or not row.get("hold"):
        return None
    h = row["hold"]
    return {
        "label": h.get("status_label") or h.get("status"),
        "reason": h.get("reason"),
        "since": h.get("since"),
    }


def public_copy(text: str | None) -> str | None:
    if not text:
        return None
    if "/workspace/" in text or "local://" in text:
        return None
    return text


def review_details(text: str) -> dict[str, str]:
    if "1110.254" not in text or "2402.958" not in text or "64.7" not in text or "61.3" not in text:
        raise ValueError("cake review is not the latest timing")
    if "script_approved=false" not in text or "timing_provisional=true" not in text:
        raise ValueError("cake review flags are not a draft")
    if "已確認口誤" in text or "high-school ones" in text.lower():
        raise ValueError("cake review asserts a guess")
    m = re.search(r"## 仍待使用者確認\n(.*?)(?:\n## |\Z)", text, re.S)
    if not m:
        raise ValueError("cake review missing open checks")
    lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
    mapped = {}
    for ln in lines:
        ln = clean_note(re.sub(r"^\d+\.\s*", "", ln))
        if "一百多萬" in ln:
            mapped["c1-money"] = ln + " 本頁不把聽寫差異寫成字幕。"
        elif "最高" in ln or "A/B" in ln:
            mapped["c2-ab"] = ln + " 本頁不把它定成講者口誤。"
        elif "高中學歷" in ln:
            mapped["c4-edu"] = ln + " 沒有確定英文。"
        elif "長得" in ln or "順眼" in ln:
            mapped["c4-order"] = ln + " 英文只是暫譯。"
    if set(mapped) != {"c1-money", "c2-ab", "c4-edu", "c4-order"}:
        raise ValueError("cake review did not match the four open checks")
    return mapped


def build_baseline(paths: dict) -> tuple[dict, dict]:
    legacy = load_legacy_html(Path(paths["legacy_html"]))
    state = load_json(Path(paths["state"]))
    inventory = load_json(Path(paths["inventory"]))
    proposals = load_json(Path(paths["proposals"]))
    cake = load_json(Path(paths["cake_scripts"]))
    details = review_details(Path(paths["cake_review"]).read_text(encoding="utf-8"))
    pick_ids = parse_pick_ids(Path(paths["pick_queue"]).read_text(encoding="utf-8"))
    state_by = index_state(state)
    stills: dict[str, str] = {}
    items: dict[str, dict] = {}

    ytq = {}
    for row in legacy.get("ytq") or []:
        ytq[(row.get("ep"), row.get("st"))] = public_copy(row.get("d"))

    files = inventory.get("files") or []
    by_state_files: dict[str, list] = {}
    verified = []
    recon_files = []
    for f in files:
        rel = rel_media(f["path"])
        if "/workspace/" in rel or rel.startswith("/"):
            raise ValueError("relative media label escaped")
        if f.get("known_14_unpublished") or f.get("reported_fb_ig_published_20261029"):
            verified.append((rel, f))
        else:
            recon_files.append((rel, f))
        for match in f.get("exact_state_matches") or []:
            sid = match.get("state_id")
            if sid:
                by_state_files.setdefault(sid, []).append((rel, f))

    def file_qc(f):
        return qc_gate(f.get("qc_record"), f.get("qc_extra_record"), f.get("mtime"), f.get("bytes"))

    for row in legacy.get("rows") or []:
        sid = row["id"]
        st = state_by.get(sid)
        matched = by_state_files.get(sid) or []
        identities = []
        for rel, f in matched:
            identities.append({
                "label": rel,
                "bytes": f.get("bytes"),
                "mtime": f.get("mtime"),
                "mtime_taipei": fmt_epoch(f.get("mtime")),
                "qc": file_qc(f),
            })
        ident_blob = dumps([{"b": x["bytes"], "m": x["mtime"], "n": x["label"]} for x in identities])
        artifact = f"card:{sid}|email:{(st or {}).get('approval_at') or ''}|files:{sha256_text(ident_blob)[:12]}"
        plats = platforms_from_legacy(row.get("p") or {})
        published_n = sum(1 for p in plats.values() if p["published"])
        section = "published" if published_n == 3 else "cut"
        gate = not_run_qc("現檔沒有同時通過 qc_short 與 qc_extra")
        if identities:
            # Any current file still blocks unless THAT file passes both. None do today.
            ready_files = [x for x in identities if x["qc"]["ready"]]
            if len(ready_files) == 1 and len(identities) == 1:
                gate = ready_files[0]["qc"]
            else:
                states = ",".join(sorted({x["qc"]["short"]["state"] for x in identities}))
                gate = not_run_qc(f"對到的現檔 qc_short={states}，qc_extra 沒有通過")
                gate["short"]["state"] = identities[0]["qc"]["short"]["state"]
                gate["extra"]["state"] = identities[0]["qc"]["extra"]["state"]
        hold = hold_from_state(st)
        if hold:
            gate = not_run_qc("這張卡暫停：" + (hold.get("label") or ""))
        img = row.get("img") or ""
        if isinstance(img, str) and img.startswith("data:image/"):
            stills[sid] = img
        subs = [s for s in (row.get("subs") or []) if isinstance(s, str)]
        copy = ytq.get((row.get("ep"), row.get("t")))
        items[sid] = {
            "id": sid,
            "kind": "cut",
            "section": section,
            "ep": row.get("ep"),
            "title": row.get("t"),
            "flags": flags(),
            "script_review_status": "none",
            "script_complete": False,
            "script_final": False,
            "platforms": plats,
            "qc": gate,
            "artifact": {"id": artifact, "label": row.get("t") or sid, "bytes": None, "mtime_taipei": None},
            "historical": historical_from_state(st),
            "hold": hold,
            "schedule_label": (st or {}).get("schedule_label") or row.get("slotT") or "",
            "schedule_readonly": True,
            "media": {
                "video": https_url(row.get("drive")),
                "video_label": "既有雲端預覽" if https_url(row.get("drive")) else None,
                "doc": https_url(row.get("doc")),
                "subs": subs,
                "copy": copy,
                "missing": None if https_url(row.get("drive")) else "沒有可公開的預覽網址。本機路徑不會變成連結。",
            },
            "local_identities": identities,
            "still_id": sid if sid in stills else None,
            "related_notes": [],
        }

    for rel, f in verified:
        stem = Path(rel).stem
        ep = rel.split("/", 1)[0]
        plats = empty_platforms()
        if f.get("reported_fb_ig_published_20261029"):
            for key in ("fb", "ig"):
                plats[key]["published"] = True
                plats[key]["date"] = "2026-10-29"
                plats[key]["source"] = "對話紀錄，未寫入舊 state"
            plats["yt"]["published"] = False
            plats["yt"]["source"] = "沒有 YouTube 發佈證據，不猜測"
        gate = file_qc(f)
        iid = "cut:" + rel
        items[iid] = {
            "id": iid,
            "kind": "cut",
            "section": "cut",
            "ep": ep,
            "title": stem,
            "flags": flags(),
            "script_review_status": "none",
            "script_complete": False,
            "script_final": False,
            "platforms": plats,
            "qc": gate,
            "artifact": {
                "id": f"{rel}|{f.get('bytes')}|{f.get('mtime')}",
                "label": rel,
                "bytes": f.get("bytes"),
                "mtime_taipei": fmt_epoch(f.get("mtime")),
            },
            "historical": None,
            "hold": None,
            "schedule_label": "",
            "schedule_readonly": True,
            "media": {
                "video": None,
                "video_label": None,
                "doc": None,
                "subs": [],
                "copy": None,
                "missing": "沒有可公開的預覽網址。盤點到的是本機檔，不會把路徑當成連結，也不補假字幕。",
            },
            "local_identities": [{
                "label": rel,
                "bytes": f.get("bytes"),
                "mtime": f.get("mtime"),
                "mtime_taipei": fmt_epoch(f.get("mtime")),
                "qc": gate,
            }],
            "still_id": None,
            "related_notes": [],
            "cut_file_note": "檔案存在只供審片。沒有開剪授權紀錄，也不等於可以發佈。",
        }

    for rel, f in recon_files:
        if f.get("exact_state_matches"):
            reason = "linked_state"
            label = "已對上既有排程卡，不另開成片卡"
        elif re.search(r"(probe_|clip_|preview|_old|backup|_v\d|v2style|meet_full|_fix)", rel, re.I):
            reason = "not_final"
            label = "看起來是過程檔、舊版或預覽，不是已核對的成片"
        else:
            reason = "unverified"
            label = "沒有核對成獨立未發成片，先放對帳，不開可發卡片"
        iid = "recon:" + rel
        gate = file_qc(f)
        items[iid] = {
            "id": iid,
            "kind": "recon",
            "section": "recon",
            "ep": rel.split("/", 1)[0],
            "title": Path(rel).name,
            "recon_reason": reason,
            "recon_reason_label": label,
            "flags": flags(),
            "platforms": empty_platforms(),
            "qc": gate,
            "artifact": {
                "id": f"recon:{rel}|{f.get('bytes')}|{f.get('mtime')}",
                "label": rel,
                "bytes": f.get("bytes"),
                "mtime_taipei": fmt_epoch(f.get("mtime")),
            },
            "media": {"video": None, "subs": [], "copy": None, "missing": "對帳項目沒有公開預覽。"},
            "still_id": None,
        }

    # Verified finals are not also reconciliation cards.
    verified_rels = {rel for rel, _ in verified}
    recon_rels = {rel for rel, _ in recon_files}
    if verified_rels & recon_rels:
        raise ValueError("file classified twice")
    if len(verified_rels) + len(recon_rels) != len(files):
        raise ValueError("inventory accounting mismatch")

    prop_by_id = {}
    for ep in proposals:
        for it in ep.get("items") or []:
            prop_by_id[it["id"]] = (ep, it)
    legacy_props = {}
    for ep in legacy.get("props") or []:
        for it in ep.get("items") or []:
            legacy_props[it["id"]] = (ep, it)
            img = it.get("img") or ""
            if isinstance(img, str) and img.startswith("data:image/"):
                stills[it["id"]] = img
    if set(prop_by_id) != set(legacy_props):
        raise ValueError("proposal ids differ between json and the existing page")

    verified_stems = [(norm_name(Path(rel).stem), rel) for rel, _ in verified]
    for pid, (ep, it) in prop_by_id.items():
        selected = pid in pick_ids
        lep, lit = legacy_props[pid]
        yt = ep.get("yt") if re.fullmatch(r"[\w-]{6,}", ep.get("yt") or "") else None
        sec = hms_to_seconds(lit.get("s") or it.get("s") or "")
        watch = f"https://www.youtube.com/watch?v={yt}&t={sec}s" if yt and sec is not None else (f"https://www.youtube.com/watch?v={yt}" if yt else None)
        title = lit.get("ttl") or lit.get("pt") or it.get("pt") or pid
        notes = []
        if pid == "EP220-Q5":
            notes.append("舊排程卡 local-EP220-Q5 曾被信件標成不發。那是舊的發佈決定，不會自動變成這次選片的駁回。")
        stem_hit = None
        ntitle = norm_name(title)
        for nstem, rel in verified_stems:
            if nstem and nstem in ntitle:
                stem_hit = rel
                break
        if stem_hit:
            notes.append(f"標題裡看得到成片檔名「{stem_hit}」。只是對照，不是同一張核准；YouTube 也沒有因此標成已發。")
        artifact = f"proposal:{pid}|selected:{int(selected)}|script:excerpt"
        items[pid] = {
            "id": pid,
            "kind": "proposal",
            "section": "script" if selected else "new",
            "ep": ep.get("ep"),
            "episode_title": ep.get("title"),
            "title": title,
            "speaker": it.get("sp") or lit.get("sp"),
            "range": f"{it.get('s')}–{it.get('e')}",
            "duration": it.get("dur"),
            "excerpt": it.get("q") or lit.get("q") or "",
            "why": it.get("why") or lit.get("why") or "",
            "episode_note": ep.get("note") or "",
            "flags": flags(selected=selected),
            "script_review_status": "pending" if selected else "none",
            "script_complete": False,
            "script_final": False,
            "platforms": empty_platforms(),
            "qc": not_run_qc("還沒有成片，不能發佈"),
            "artifact": {"id": artifact, "label": pid, "bytes": None, "mtime_taipei": None},
            "media": {
                "video": watch,
                "video_label": "原集 YouTube 時間點" if watch else None,
                "doc": https_url(ep.get("drive")),
                "subs": [],
                "copy": None,
                "missing": None if watch else "這則提案沒有可公開的原片時間點。",
            },
            "still_id": pid if pid in stills else None,
            "related_notes": notes,
            "selection_note": "2026-11-09 02:18 選片信只授權選這段，不是腳本核准、不是開剪、不是發佈。完整逐句腳本還沒有附上。" if selected else "",
        }

    clips = cake.get("clips") or []
    if [c.get("id") for c in clips] != ["C1", "C2", "C3", "C4", "C5"]:
        raise ValueError("Cake clips must be exactly C1–C5")
    expected_span = {
        "C1": (1110.254, 1174.95, 64.7),
        "C4": (2402.958, 2464.23, 61.3),
    }
    uncertainties = []
    for spec in UNCERTAINTIES:
        audio = review_audio(spec["audio_key"])
        uncertainties.append({
            "id": spec["id"],
            "clip": spec["clip"],
            "title": spec["title"],
            "detail": details[spec["id"]],
            "review_audio": audio,
        })
    for clip in clips:
        cid = "Cake-" + clip["id"]
        if clip["id"] in expected_span:
            t0, t1, dur = expected_span[clip["id"]]
            if abs(float(clip["t0"]) - t0) > 1e-6 or abs(float(clip["t1"]) - t1) > 1e-3 or abs(float(clip["duration"]) - dur) > 1e-6:
                raise ValueError(f"{cid} timing drifted from the latest review")
        if clip.get("script_approved") or clip.get("cut_authorized") or clip.get("publish_approved"):
            raise ValueError(f"{cid} source flags are not a draft")
        if clip.get("qc_status") != "not_run" or clip.get("timing_provisional") is not True:
            raise ValueError(f"{cid} must stay timing_provisional and qc not_run")
        sentences = []
        for ch in clip.get("chunks") or []:
            uid = sentence_uncertainty(cid, ch)
            sentences.append(sanitize_sentence(ch, uid))
        blob = dumps([[s["start"], s["end"], s["lines"], s["en_display"], s["note"]] for s in sentences])
        tsec = int(float(clip["t0"]))
        watch = https_url(clip.get("youtube")) or f"https://www.youtube.com/watch?v={YT_ID}&t={tsec}s"
        items[cid] = {
            "id": cid,
            "kind": "script",
            "section": "script",
            "ep": "Cake",
            "title": clip.get("title"),
            "speaker": clip.get("speaker"),
            "range": f"{float(clip['t0']):.3f}–{float(clip['t1']):.3f}",
            "duration": clip.get("duration"),
            "keywords": clip.get("keywords") or [],
            "flags": flags(selected=True),
            "script_review_status": "pending",
            "script_complete": True,
            "script_final": False,
            "timing_provisional": True,
            "qc_status": "not_run",
            "platforms": empty_platforms(),
            "qc": not_run_qc("腳本 QC 未跑，時間仍是暫排，尚未核准、尚未開剪"),
            "artifact": {"id": f"{cid}|draft:{sha256_text(blob)[:16]}", "label": cid + " 腳本初稿"},
            "sentences": sentences,
            "uncertainties": [u for u in uncertainties if u["clip"] == cid],
            "media": {
                "video": watch,
                "video_label": "講座原片時間點，不是已剪短片",
                "doc": None,
                "subs": [],
                "copy": None,
                "missing": None,
            },
            "still_id": None,
            "draft_banner": "初稿，供審腳本。時間暫排，QC 未跑。不是定稿，沒有腳本核准，沒有開剪，沒有發佈核准。",
            "selection_note": "選了這支提案。腳本仍待審，不能依選片或這份初稿開剪、發佈。",
        }

    receipts = []
    for r in state.get("receipts") or []:
        receipts.append({
            "at": r.get("received_at"),
            "applied": r.get("applied_at"),
            "count": r.get("count"),
            "source": r.get("source") or "email",
        })
    model = {
        "timezone": "Asia/Taipei",
        "contact": {"to": legacy.get("to"), "from": legacy.get("from")},
        "items": items,
        "uncertainties": uncertainties,
        "history": {
            "receipts": receipts,
            "detection_note": "平台自動偵測最後停在 2026-10-13，不能當成現在的發布事實。未登入時 FB/IG 本來就讀不到列表。",
            "schedule_note": "沒有改 08:00／12:00／17:00 的發佈節奏。這一頁不能排程、不能上傳、不能代發。",
        },
        "sources": {
            "cake_scripts": "cake_scripts_ddb4",
            "cake_review": "cake_review_3aff",
            "audio": "youtube-windows-not-hosted",
        },
        "legacy_draft_keys_ignored": list(LEGACY_DRAFT_KEYS),
    }
    problems = invariants(model)
    if problems:
        raise ValueError("baseline invariants failed: " + "; ".join(problems))
    return model, stills


def revision_of(model: dict) -> str:
    return sha256_text(dumps(model))


def invariants(model: dict) -> list[str]:
    problems = []
    items = list(model.get("items", {}).values())
    ids = [it["id"] for it in items]
    if len(ids) != len(set(ids)):
        problems.append("duplicate ids")
    blob = dumps(model)
    for banned in ("/workspace/", "local://", "x-access-token", "high-school ones"):
        if banned in blob:
            problems.append("banned text " + banned)
    if "audio/" in blob and "audio/" in blob:
        # audio filenames may remain only if rewritten; the keys should not.
        if "C1_money.mp3" in blob or "C4_c.mp3" in blob:
            problems.append("audio filename leaked")
    cakes = [it for it in items if str(it["id"]).startswith("Cake-")]
    if sorted(it["id"] for it in cakes) != ["Cake-C1", "Cake-C2", "Cake-C3", "Cake-C4", "Cake-C5"]:
        problems.append("cake set")
    for it in cakes:
        f = it["flags"]
        if not (f["proposal_selected"] and not f["script_approved"] and not f["cut_authorized"] and not f["publish_approved"]):
            problems.append(it["id"] + " flags")
        if it["section"] != "script" or it.get("script_final") or it.get("qc_status") != "not_run":
            problems.append(it["id"] + " section")
        if not it.get("timing_provisional"):
            problems.append(it["id"] + " timing")
        for s in it.get("sentences") or []:
            if s.get("note") and s["note"] in "\n".join(s.get("lines") or []):
                problems.append(it["id"] + " note leaked into spoken")
            if s["en_status"] in ("provisional", "blank_pending", "blanked_unsupported") and s["en_display"] and not (
                s["en_display"].startswith(PROVISIONAL_MARK) or s["en_display"] == BLANK_EN
            ):
                problems.append(it["id"] + " english not marked")
    c1 = model["items"].get("Cake-C1")
    c4 = model["items"].get("Cake-C4")
    if not c1 or not c1["range"].startswith("1110.254"):
        problems.append("C1 range")
    if not c4 or not c4["range"].startswith("2402.958") or "2464.230" not in c4["range"]:
        problems.append("C4 range")
    if any(it["flags"]["publish_approved"] or it["flags"]["cut_authorized"] or it["flags"]["script_approved"] for it in items):
        problems.append("a baseline flag was approved")
    new_ids = {it["id"] for it in items if it["section"] == "new"}
    if set(PICK_IDS) & new_ids:
        problems.append("selected proposal still in new")
    script_ids = {it["id"] for it in items if it["section"] == "script"}
    if not set(PICK_IDS) <= script_ids:
        problems.append("pick ids missing from script review")
    if any(it["section"] == "approved" for it in items):
        problems.append("approved not empty")
    oct29 = [it for it in items if it["id"].startswith("cut:") and it["platforms"]["fb"]["published"] and it["platforms"]["ig"]["published"]]
    if len(oct29) != 3 or any(it["platforms"]["yt"]["published"] for it in oct29):
        problems.append("oct29 platforms")
    full = [it for it in items if it["section"] == "published"]
    if len(full) != 3:
        problems.append("full published count")
    known = [it for it in items if it["id"].startswith("cut:") and not it["platforms"]["fb"]["published"]]
    if len(known) != 14:
        problems.append("known unpublished cuts")
    recon = [it for it in items if it["section"] == "recon"]
    if len(recon) != 105:
        problems.append(f"recon {len(recon)}")
    ready = [it for it in items if it.get("qc", {}).get("ready")]
    if ready:
        problems.append("unexpected qc ready")
    return problems


def empty_model() -> dict:
    return {"timezone": "Asia/Taipei", "contact": {"to": "", "from": ""}, "items": {}, "uncertainties": [], "history": {}, "sources": {}}


def upsert_item(model: dict, item: dict) -> None:
    model["items"][item["id"]] = item


def apply_mutation(model: dict, event: dict) -> dict:
    """Apply one non-baseline event. Raises ValueError on a hard failure (event stays inbox)."""
    et = event["type"]
    payload = event.get("payload") or {}
    if et == "proposal_created":
        item = dict(payload["item"])
        item["flags"] = flags()
        item["section"] = "new"
        item["kind"] = "proposal"
        item["script_approved"] = False
        item["script_review_status"] = "none"
        item["script_complete"] = False
        item["script_final"] = False
        item["qc"] = not_run_qc("新提案沒有成片")
        item.setdefault("platforms", empty_platforms())
        upsert_item(model, item)
        return {"effect": "proposal_created", "id": item["id"]}
    if et == "script_created":
        item = dict(payload["item"])
        sentences = []
        for ch in item.get("sentences") or payload.get("sentences") or []:
            if "lines" in ch or "zh" in ch:
                sentences.append(sanitize_sentence(ch, ch.get("uncertainty_id")))
            else:
                raise ValueError("script sentence missing zh")
        item["sentences"] = sentences
        item["flags"] = flags(selected=True)
        item["section"] = "script"
        item["kind"] = "script"
        item["script_review_status"] = "pending"
        item["script_complete"] = bool(sentences)
        item["script_final"] = False
        item["timing_provisional"] = True
        item["qc_status"] = "not_run"
        item["qc"] = not_run_qc("新腳本尚未 QC，也尚未核准")
        item.setdefault("platforms", empty_platforms())
        upsert_item(model, item)
        return {"effect": "script_created_pending", "id": item["id"]}
    if et == "script_approved":
        item = model["items"].get(payload.get("item_id"))
        if not item:
            return {"effect": "rejected", "reason": "missing item"}
        if payload.get("artifact_id") and payload.get("artifact_id") != item.get("artifact", {}).get("id"):
            return {"effect": "rejected", "reason": "artifact mismatch"}
        if not item.get("script_complete") or not item.get("sentences"):
            return {"effect": "rejected", "reason": "no full script"}
        if payload.get("confirm") is not True:
            return {"effect": "rejected", "reason": "confirm required"}
        item["flags"]["script_approved"] = True
        item["flags"]["cut_authorized"] = False
        item["flags"]["publish_approved"] = False
        item["script_review_status"] = "approved"
        item["script_final"] = True
        item["section"] = "approved"
        return {"effect": "script_approved", "id": item["id"]}
    if et == "email_parsed":
        kind = payload.get("kind")
        if kind == "selection":
            touched = []
            for iid in payload.get("selections") or []:
                item = model["items"].get(iid)
                if not item:
                    continue
                item["flags"]["proposal_selected"] = True
                item["flags"]["script_approved"] = False
                item["flags"]["cut_authorized"] = False
                item["flags"]["publish_approved"] = False
                if item.get("kind") == "proposal" and item.get("section") == "new":
                    item["section"] = "script"
                    item["script_review_status"] = "pending"
                    item["script_complete"] = False
                touched.append(iid)
            model.setdefault("history", {}).setdefault("parsed_emails", []).append({
                "message_id": payload.get("message_id"),
                "kind": "selection",
                "ids": touched,
            })
            return {"effect": "selection_only", "ids": touched}
        if kind == "publish":
            blocked = []
            applied = []
            for dec in payload.get("decisions") or []:
                item = model["items"].get(dec.get("item_id"))
                if not item:
                    blocked.append({"id": dec.get("item_id"), "reason": "missing"})
                    continue
                if dec.get("artifact_id") != item.get("artifact", {}).get("id"):
                    blocked.append({"id": item["id"], "reason": "artifact mismatch"})
                    continue
                if dec.get("publish_approved") is True:
                    if not item.get("qc", {}).get("ready"):
                        item["flags"]["publish_approved"] = False
                        item.setdefault("blocked_decisions", []).append({"event": event["event_id"], "reason": "qc"})
                        blocked.append({"id": item["id"], "reason": "qc"})
                        continue
                    item["flags"]["publish_approved"] = True
                    item["publish_approval"] = {"event_id": event["event_id"], "artifact_id": item["artifact"]["id"]}
                    applied.append(item["id"])
            return {"effect": "publish_decisions", "applied": applied, "blocked": blocked}
        return {"effect": "email_recorded_ignored", "kind": kind}
    if et == "artifact_created":
        item = dict(payload["item"])
        file_mtime = payload.get("file_mtime")
        file_size = payload.get("file_size")
        gate = qc_gate(payload.get("qc_short"), payload.get("qc_extra"), file_mtime, file_size, payload.get("accepted_warns"))
        item["qc"] = gate
        item["kind"] = "cut"
        item["section"] = "cut"
        item["flags"] = flags(cut=bool(payload.get("cut_authorized")))
        item["flags"]["publish_approved"] = False
        item.setdefault("platforms", empty_platforms())
        upsert_item(model, item)
        return {"effect": "artifact_created", "id": item["id"], "qc_ready": gate["ready"]}
    if et == "QC_completed":
        item = model["items"].get(payload.get("item_id"))
        if not item:
            return {"effect": "rejected", "reason": "missing item"}
        if payload.get("artifact_id") != item.get("artifact", {}).get("id"):
            return {"effect": "rejected", "reason": "artifact mismatch"}
        gate = qc_gate(
            payload.get("qc_short"),
            payload.get("qc_extra"),
            payload.get("file_mtime"),
            payload.get("file_size"),
            payload.get("accepted_warns"),
        )
        item["qc"] = gate
        item["flags"]["publish_approved"] = False
        return {"effect": "qc_updated", "id": item["id"], "ready": gate["ready"]}
    if et == "publication_verified":
        item = model["items"].get(payload.get("item_id"))
        if not item:
            return {"effect": "rejected", "reason": "missing item"}
        platform = payload.get("platform")
        if platform not in ("yt", "fb", "ig"):
            raise ValueError("bad platform")
        before = {k: dict(v) for k, v in item.get("platforms", empty_platforms()).items()}
        item.setdefault("platforms", empty_platforms())
        item["platforms"][platform]["published"] = bool(payload.get("published"))
        item["platforms"][platform]["date"] = payload.get("date")
        item["platforms"][platform]["source"] = payload.get("evidence")
        item["platforms"][platform]["url"] = https_url(payload.get("url"))
        published_n = sum(1 for p in item["platforms"].values() if p["published"])
        if item.get("kind") == "cut" or item.get("section") in ("cut", "published"):
            item["section"] = "published" if published_n == 3 else "cut"
        return {"effect": "platform_only", "id": item["id"], "platform": platform, "unchanged": [k for k in before if k != platform and before[k] == item["platforms"][k]]}
    raise ValueError("unsupported event " + et)


def merge_baseline(model: dict, incoming: dict) -> dict:
    if not model.get("items"):
        return incoming
    for iid, item in incoming.get("items", {}).items():
        model["items"][iid] = item
    for key in ("contact", "history", "sources", "uncertainties", "timezone", "legacy_draft_keys_ignored"):
        if key in incoming:
            model[key] = incoming[key]
    return model
