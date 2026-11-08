#!/usr/bin/env python3
"""Render the existing review URL from the canonical model."""
from __future__ import annotations

import json
from pathlib import Path

from reviewlib import revision_of

ROOT = Path(__file__).resolve().parents[1]
CSS = (Path(__file__).parent / "page.css").read_text(encoding="utf-8")
JS = (Path(__file__).parent / "page.js").read_text(encoding="utf-8")


def _public_sync(sync: dict, revision: str) -> dict:
    last = sync.get("last_successful_sync") if sync else None
    verified = bool(last) and sync.get("built_revision") == revision and sync.get("canonical_revision") == revision
    return {
        "last_successful_sync": last if verified else None,
        "verified_this_revision": verified,
        "pending": bool(sync.get("pending")) if sync else True,
    }


def render(model: dict, stills: dict | None = None, sync: dict | None = None) -> str:
    stills = stills or {}
    revision = revision_of(model)
    items = []
    for item in model["items"].values():
        row = dict(item)
        sid = row.get("still_id")
        blob = stills.get(sid or "")
        if isinstance(blob, str) and (blob.startswith("data:image/") or blob.startswith("https://")):
            row["still"] = blob
        else:
            row.pop("still", None)
        items.append(row)
    items.sort(key=lambda it: (it.get("section") or "", it.get("ep") or "", it.get("title") or "", it.get("id") or ""))
    payload = {
        "revision": revision,
        "timezone": "Asia/Taipei",
        "to": (model.get("contact") or {}).get("to"),
        "from": (model.get("contact") or {}).get("from"),
        "sync": _public_sync(sync or {}, revision),
        "history": model.get("history") or {},
        "items": items,
    }
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    if "x-access-token" in data or "/workspace/" in data or "local://" in data:
        raise ValueError("public payload failed sanitization")
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="review-revision" content="{revision}">
<title>科技工作講｜審核</title>
<style>
{CSS}
</style>
</head>
<body data-canonical-revision="{revision}">
<header id="hd">
<h1>科技工作講<b>｜</b>審核</h1>
<p class="sync" id="sync">修訂 {revision[:12]}。公開網址若不是這個修訂，代表網站還沒更新。</p>
<div class="tabs" id="tabs" role="tablist">
<button type="button" data-tab="new" data-label="新提案">新提案</button>
<button type="button" data-tab="script" data-label="腳本待審">腳本待審</button>
<button type="button" data-tab="approved" data-label="已審核">已審核</button>
<button type="button" data-tab="cut" data-label="成片待審">成片待審</button>
<button type="button" data-tab="published" data-label="已發佈">已發佈</button>
<button type="button" data-tab="recon" data-label="對帳">對帳</button>
</div>
<div class="flt">
<select id="ep" aria-label="集數"><option value="">所有集數</option></select>
<input id="q" placeholder="搜尋標題" aria-label="搜尋">
</div>
<div class="rowbtns" id="actions">
<button type="button" class="act" id="copy-pick">複製選片草稿</button>
<button type="button" class="act" id="mail-pick">開啟選片郵件草稿</button>
<button type="button" class="act" id="copy-script">複製腳本意見草稿</button>
<button type="button" class="act" id="mail-script">開啟腳本意見郵件草稿</button>
</div>
<p id="msg" role="status"></p>
</header>
<main id="list"></main>
<footer>
<p>建立資料使用台北時間。寄件草稿給 {model.get("contact", {}).get("to")}，請用 {model.get("contact", {}).get("from")} 寄出。打開郵件程式不代表已寄出。</p>
<p>{(model.get("history") or {}).get("schedule_note") or ""}</p>
<p>{(model.get("history") or {}).get("detection_note") or ""}</p>
<p>修訂 {revision}。本頁不宣布自己已經部署。</p>
</footer>
<script id="payload" type="application/json">{data}</script>
<script>
{JS}
</script>
</body>
</html>
"""


def write_page(path: Path, model: dict, stills: dict | None = None, sync: dict | None = None) -> str:
    html = render(model, stills, sync)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return revision_of(model)
