# P2 大檔收斂契約

Angel Heart 的 Cary `2.2.3+cary.1` 已有完整 Python 3.11／3.12 測試、compileall 與 WebUI 可重現建置閘門。本 P2 約束只處理剩餘的 source architecture debt，不改現有功能或發版語義。

## Shrink-only budget

以 2026-08-31 canonical `master` 為基線：

- `roles/front_desk.py`：最多 **85,577 bytes**；
- `core/conversation_ledger.py`：最多 **65,445 bytes**。

`tests/test_architecture_shrink_budget.py` 會由既有全量 pytest 執行。兩個檔案都只能保持或縮小；後續若成功抽離邏輯，應同步把上限降到新的實際大小。

不要透過刪註解、壓行、縮短名稱或提高 budget 來繞過門禁。目標是降低責任密度，不是降低文字量。

## 後續抽離原則

- `FrontDesk` 保留角色入口與 orchestration；可獨立描述的媒體、引用、喚醒、發送狀態、上下文整理策略應落到小型 helper／core module，並各自有 regression test。
- `ConversationLedger` 保留 ledger authority 與一致性邊界；格式化、查詢投影、清理策略、純轉換邏輯優先拆成可單測元件。
- 已存在的 `roles/cary_front_desk_patch.py` 是兼容補丁邊界，不應重新演變成第二個大 `front_desk.py`。
- WebUI `pages/chat-config/assets/*.js` 是 `webui/` source + lockfile 的生成產物；大小不是 source architecture 指標，繼續由 release gate 的 reproducible-build 檢查管理。

## 不改變的契約

本 P2 gate 不改：

- 雙防抖與 patience／streaming 狀態機；
- familiarity、reply-to-self wake、quoted-media cache；
- conversation/work ledger 資料語義；
- prompt/context 注入；
- 配置 schema；
- WebUI 行為與 build output；
- `2.2.3+cary.1` 版本與發版流程。

核心原則：**已經形成的大檔可以漸進拆解，但新功能不再讓它們重新膨脹。**
