# 審核網站同步

公開頁：`https://moboochen.github.io/p-0787b9ba0911/Cdj1cq3x3gEFyC5WbNqRdjoU/`

GitHub Pages 發佈的是 `main`。推一條審查分支、或開著 PR，都不會改公開頁。

這份授權只涵蓋目前這次網站內容。它不是往後每一包未知變更都可以自動合併。

## 七個階段，前面完成不代表後面完成

| 階段 | 意思 | 這一包現在 |
| --- | --- | --- |
| persisted | 事件寫進 `data/canonical/model.json`，重複的 `event_id` 不會再生一筆 | 會由 `apply` 寫下 |
| built | `Cdj1cq3x3gEFyC5WbNqRdjoU/index.html` 已依這份資料重建 | 會由 `apply` / `build` 寫下 |
| pushed_branch | 審查分支已快轉推上 origin | 不是公開頁 |
| pull_request | 該分支有開著的 PR | https://github.com/moboochen/p-0787b9ba0911/pull/1 |
| merged | PR 已合併進 `main` | 還沒有。需要你明確同意這一次 |
| deployed | Pages 已用 `main` 上的這個修訂對外提供 | 還沒有 |
| verified | `verify` 在公開網址讀到同一個 `review-revision` | 還沒有。`last_successful_sync` 維持 null |

`sync_status.json` 的 `stages` 各自記錄。`deploy` 只填 `pushed_branch`，並清掉較新修訂上的 merged / deployed / verified。只有 `verify` 對上公開頁，才同時填 deployed 與 verified，並寫 `last_successful_sync`。

## Box 上怎麼呼叫

Repo 裡的 `tools/` 還沒裝到 box，不能假設 box 上有 git checkout。可複製的獨立目錄是 `box/review-sync/`（也會另存一份 zip 給這次交接）。**現在還沒安裝到 box。**

複製到 box 之後：

```bash
python3 sync_box.py stage
python3 sync_site.py pack-bundle ... --out /tmp/review-bundle.json
python3 sync_box.py github-commit --dry-run \
  --repo moboochen/p-0787b9ba0911 \
  --branch cursor/shorts-review-sync-f53b \
  --bundle /tmp/review-bundle.json
```

`github-commit` 目前只允許 `--dry-run`。它會列出用已經登入的 `gh` 去快轉更新審查分支的 API 步驟，不讀 token 檔、不把 token 放進指令、不對 `main` 做任何事、也不合併。

真正讓公開頁改變的窄決定只有一個：你同意之後，把 PR #1 合併進 `main`。合併後再執行：

```bash
python3 tools/sync_site.py verify --url https://moboochen.github.io/p-0787b9ba0911/Cdj1cq3x3gEFyC5WbNqRdjoU/
```

安全匯入（只吃已脫敏的 JSON，不把原始證據放進頁面）：

```bash
python3 tools/sync_site.py import-safe --file /path/to/safe_site_import.json
```

這一步只到 persisted 和 built。

## 事件

見 `schema/sync_event.schema.json`。

- `script_approved` 只核准 payload 裡那一份文字。文字不同就分開保留舊的已核准版，目前這份維持待審。
- 檔案 mtime 不合只讓 QC 失效，不取消已經核准的那一版腳本。
- `preview_attached` 只接受對到 `artifact_id` 的 https Drive / YouTube 連結。不合就不掛預覽，也不因此放行。
- `publication_verified` 只改指名的一個平台。沒有正面「未發」證據時，YouTube 顯示未核實，不顯示未發。
