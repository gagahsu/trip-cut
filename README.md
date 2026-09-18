# trip-cut

出遊照片＋影片 → 本機 AI 分析 → 腳本 → 剪輯決策 → 回憶影片。全程素材不離開本機，AI 決策交給 Claude Code。

## 快速開始

1. 依 `docs/SETUP.md` 完成 WSL2 環境。
2. 建立旅行專案：`mkdir -p projects/2026-10-okinawa/raw`，把照片影片丟進 `raw/`。
3. 在 repo 根目錄開 Claude Code，說：「幫我處理 projects/2026-10-okinawa，我沒有腳本」（或「腳本在 script.md」）。
4. 依 `CLAUDE.md` §5 的流程跑到成品。

## 文件

- `CLAUDE.md` — agent 入口與規則
- `docs/ARCHITECTURE.md` — 架構
- `docs/PIPELINE.md` — 每階段規格
- `docs/SETUP.md` — 環境
- `docs/TASKS.md` — 待辦
- `docs/DECISIONS.md` — 決策紀錄
- `docs/REFERENCES.md` — 參考連結
