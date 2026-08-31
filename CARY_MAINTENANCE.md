# AngelHeart Cary 維護基線

## 正式版本

- 上游功能基線：`2.2.3`
- Cary 客製版本：`2.2.3+cary.1`
- 正式整合分支：`cary/2.2.3`
- 正式部署分支：`master`
- 修復整合一律先進 PR，不直接改部署分支。

## 已吸收的歷史修復

| 原分支／修復 | 2.2.3 狀態 | 處理 |
|---|---:|---|
| `fix/consecutive-echo-detection` | 已包含 | 保留新版連續純文字復讀判斷，不合併舊分支 |
| `fix/familiarity-timeout-property` | 已包含 | 保留 grouped-config accessor，不合併舊分支 |
| `codex/streaming-send-state` | 程式已包含 | 補回 `_has_send_oper` 空鏈回歸測試 |
| 舊 `cancel_patience_timer` 清理 | 已包含 | 保留 v2 雙防抖狀態收口測試 |
| `agent/fix-quoted-media-cache` | 原先缺失 | 以 `roles/cary_front_desk_patch.py` 最小兼容層移植 |
| `custom/cary-production-0.9` | 已過時且落後 | 僅作歷史參考，禁止直接 merge |

## 引用附件補丁的邊界

- 遞迴處理 `Reply.chain` 中的圖片與文字檔。
- 巢狀／循環引用不會無限遞迴。
- 同一媒體物件只快取一次。
- 引用正文仍由 2.2.3 原有格式化器處理；補丁不把引用文字混入喚醒正文。
- 未包含引用附件時完全走原始 `FrontDesk.cache_message`。

## 發布閘門

每次合入正式分支前必須同時通過：

1. Python 3.11、3.12 全量 pytest。
2. 全插件 `compileall`。
3. metadata 必須明確標記 Cary 客製版本與 Cary repo。
4. WebUI 使用 lockfile 重新建置後，產物必須與提交內容一致。
5. Git 追蹤內容不得含 `.venv`、`node_modules`、`__pycache__` 或 `.pyc`。

## 分支退場原則

本基線驗證完成後，舊修復分支只保留到各功能的「已吸收」證據確認完畢；不再從落後 50+ commits 的分支做 merge。後續新修復從正式部署分支建立短期 PR 分支。
