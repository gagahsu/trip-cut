# TASKS

> Claude：開工前先讀「當前階段」。完成一項就勾掉並在 Log 加一行（日期、做了什麼、產物）。
> 不要跳階段；一個階段的驗收條件沒過不進下一階段。

## 當前階段：Phase 0

---

## Phase 0 — 環境與骨架
- [ ] 依 `docs/SETUP.md` 建好 WSL2 環境，通過驗證清單
- [ ] 確認 Kinocut MCP 啟動指令，更新 `.mcp.json`，Claude Code `/mcp` 連線成功
- [ ] 建 `pyproject.toml`（套件名 `tripcut`，CLI 入口 `tripcut`），ruff/pyright 設定
- [ ] 建 `remotion/` 專案骨架（`npx create-video@latest`，TypeScript，blank template）
- [ ] 準備一個測試專案 `projects/_sample/`（10 張照片 + 2 支短影片，非真實出遊素材也可）
- **驗收**：`tripcut --help` 可跑；`npx remotion studio` 可開；kinocut 已連線

## Phase 1 — 分析層（ingest / frames / transcribe）
- [ ] `ingest.py`：exiftool + ffprobe → `manifest.json`，通過 schema
- [ ] HEIC 轉 jpg
- [ ] `frames.py`：場景切換抽幀 + 等距 fallback + 每支上限
- [ ] `contact_sheet.py`：影片 sheet + 照片 sheet，含標籤
- [ ] `transcribe.py`：faster-whisper，CUDA→CPU fallback，volumedetect 跳過純環境音
- [ ] 用 `_sample` 跑完整分析，Claude 讀 contact sheet 能正確描述內容
- **驗收**：`tripcut ingest && tripcut frames && tripcut transcribe` 在 `_sample` 上一次跑完，產物齊全

## Phase 2 — 腳本與 EDL（情境 B 流程）
- [ ] 定義 `script.md` 模板（放 `docs/templates/script.md`）
- [ ] Claude 依 `_sample` 產 `script.md` 草稿，停下等確認（驗證 hard rule 4）
- [ ] `edl.py`：schema 驗證、source 存在檢查、in/out 越界、總長度警告、直式 crop 必填
- [ ] `tripcut props`：EDL → props.json（秒→frame、絕對路徑）
- [ ] 備援出片：接 `kburns-slideshow` 或自寫 ffmpeg concat，用 EDL 出一支粗剪 mp4
- **驗收**：從 `_sample` 走到粗剪 mp4，全程 Claude 只在「腳本確認」處停一次

## Phase 3 — Remotion Montage
- [ ] `Montage.tsx`：讀 props.json，支援 photo(kenburns) / video(in-out, crop) / title / transition / bgm
- [ ] 9:16 與 16:9 兩個 Composition 共用同一 props
- [ ] 字卡字體：Noto Sans TC，安全區（IG：上下各留 250px）
- [ ] BGM ducking（有 keep_audio 的片段時降 BGM）
- [ ] 影片段落先由 Kinocut 預裁到 `work/clips/`（1080p），Remotion 只吃預裁檔
- [ ] Kinocut 品檢：時長、黑幀、音量
- **驗收**：`_sample` 用 Remotion 出 9:16 與 16:9 各一支，畫面與 EDL 一致

## Phase 4 — 真實素材與打磨
- [ ] 用一趟真實出遊素材跑情境 B 全流程，記錄卡點
- [ ] 跑情境 A（自備腳本）
- [ ] 抽幀上限、scene 門檻、contact sheet 版面依實測調整
- [ ] Claude 選片品質觀察：是否偏好某類畫面、是否漏掉短片段
- [ ] 文件回填：把實測學到的寫回 PIPELINE.md / CLAUDE.md

## Backlog（未排程）
- [ ] edge-tts 旁白（讀 script.md 的旁白欄位 → mp3+srt → Remotion 字幕層）
- [ ] 多趟旅行共用的 Remotion 風格 preset（props 內 `theme` 欄位）
- [ ] Immich 整合：直接從自架相簿拉素材（參考 immich-video-memory-generator）
- [ ] 以 `ali-abassi/remotion-templates` 的 transition 家族擴充轉場
- [ ] n8n/GitHub Actions 觸發（目前判定：情境 A/B 是偶發工作，不排程）

## Log
- 2026-09-18：專案文件初版建立（尚未開始 Phase 0）
