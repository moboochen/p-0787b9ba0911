# 審核網站同步

公開頁：`https://moboochen.github.io/p-0787b9ba0911/Cdj1cq3x3gEFyC5WbNqRdjoU/`

這一頁的資料以 `data/canonical/model.json` 為準。本機狀態改變、郵件草稿、或 `git push` 成功，都不代表網站已更新。只有 `verify` 在公開網址讀到同一個 `review-revision`，才會寫下 `last_successful_sync`。

不要用舊的 `deploy_scheduler.py`。那個流程會讀 token 並強推。這個介面拒絕 `--force`，也不會推 `main`。

## 在 box 上打包（來源只在 box 時）

把這個 repo 的 `tools/sync_site.py`、`tools/reviewlib.py`、`tools/render_page.py`、`tools/page.js`、`tools/page.css` 放到 box，或在 box 上 clone repo。只使用 Python 3 標準庫。

```bash
python3 tools/sync_site.py pack-bundle \
  --legacy-html Cdj1cq3x3gEFyC5WbNqRdjoU/index.html \
  --state /workspace/shorts/publish/state.json \
  --proposals /workspace/shorts/publish/proposals.json \
  --inventory /path/to/inventory.json \
  --qc /workspace/shorts/publish/qc_results.json \
  --qc-extra /workspace/shorts/publish/qc_extra_results.json \
  --cake-scripts /path/to/cake_scripts.json \
  --cake-review /path/to/cake_review.md \
  --pick-queue /workspace/shorts/publish/pick_queue.md \
  --out /tmp/review-bundle.json
```

`qc-extra` 檔案不存在時會記成台帳缺失，不會編成通過。bundle 不含影片、不含 mp3。不確定句的試聽使用已公開的 YouTube 時間窗。

之後把 `/tmp/review-bundle.json` 拷到有 git repo 的機器。

## 寫入、建頁、推分支、驗證

```bash
python3 tools/sync_site.py apply --bundle /tmp/review-bundle.json
python3 tools/sync_site.py build
python3 tools/sync_site.py status
python3 tools/sync_site.py deploy --dry-run --branch cursor/shorts-review-sync-f53b
python3 tools/sync_site.py deploy --branch cursor/shorts-review-sync-f53b
```

`deploy` 只執行 `git push -u origin <branch>`。失敗時事件留在 `data/canonical/outbox` 與 `inbox`，`last_successful_sync` 不會被寫成成功。

公開頁要更新，還需要把該 PR 合併進 `main`。GitHub Pages 從 `main` 發佈。合併不是這個指令會做的事。

合併完成後：

```bash
python3 tools/sync_site.py verify --url https://moboochen.github.io/p-0787b9ba0911/Cdj1cq3x3gEFyC5WbNqRdjoU/
```

成功時 `data/canonical/sync_status.json` 的 `last_successful_sync` 會是台北時間，對應的 outbox 列會移除。失敗時 outbox 保留，下次同一批可以再跑 `verify` 或 `deploy`。

## 後續單筆事件

`apply --bundle` 也接受只有 `events` 的小 bundle。`event_id` 重複會略過，不會產生第二筆。

| type | 會改什麼 | 不會改什麼 |
| --- | --- | --- |
| `email_parsed` `kind=selection` | `proposal_selected=true`，提案改到腳本待審 | 腳本核准、開剪、發佈核准 |
| `email_parsed` `kind=publish` | 只有 artifact 相符且 qc_short 與 qc_extra 都過，才設 `publish_approved` | 不符或 QC 未過的決定只記為封鎖 |
| `proposal_created` | 新提案，四個旗標都是否 | |
| `script_created` | 腳本待審、pending、時間暫排 | 不能藉此核准 |
| `script_approved` | 需 `confirm: true`、完整腳本、artifact 相符；進已審核 | 不開剪、不發佈 |
| `artifact_created` | 成片卡 | 不自動發佈核准 |
| `QC_completed` | 更新 QC。兩項都過才 `ready` | 不把 `publish_approved` 設成 true |
| `publication_verified` | 只改 payload 指定的一個平台 | 不猜測其他平台 |

事件形狀見 `schema/sync_event.schema.json`。

套用失敗的事件留在 `data/canonical/inbox.jsonl`，下次 `apply` 會從那裡繼續。已套用的 id 在 `applied_events.jsonl`。
