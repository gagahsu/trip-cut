# DECISIONS (ADR)

格式：編號 / 日期 / 決策 / 理由 / 後果。要推翻請新增一條，不要改舊的。

## ADR-001 2026-09-18 素材分析純本機，不用第三方 vision API
- 決策：分析只走 ffmpeg 抽幀 + exiftool + faster-whisper → Claude Code 讀圖。
- 理由：出遊素材含家人；Gemini/Mistral 免費層資料政策可能用於訓練。Claude Code 已付費訂閱，讀圖不額外花錢。
- 後果：Claude 不能直接看影片，需要 contact sheet；context 有限，靠抽幀上限控制。

## ADR-002 2026-09-18 剪輯執行用 Kinocut，不用裸 ffmpeg MCP
- 決策：所有剪輯操作走 Kinocut MCP。
- 理由：typed tools + preflight + 品檢，比 `shell_run` 式的 ffmpeg MCP 穩；避免 Agent 猜錯 flag。
- 後果：分析用 ffmpeg（抽幀、probe）例外允許裸指令（PIPELINE 白名單）。

## ADR-003 2026-09-18 渲染用 Remotion，JSON-props 驅動
- 決策：單一 `Montage` composition 吃 `props.json`；架構參考 `chrix911/maintain-video`。
- 理由：換旅行只換 JSON；Claude 只需產 EDL，不碰 React；Ken Burns/轉場/字卡都能做。
- 風險：Remotion 授權個人免費、公司規模需付費；WSL headless Chrome 需要額外 libs。
- 備援：`kburns-slideshow` 純 ffmpeg，Phase 1–2 先用它驗證流程。

## ADR-004 2026-09-18 Whisper 用 small + int8_float16
- 理由：GPU 等級不高；中文逐字稿只供理解，不當字幕，精度要求低。
- 後果：CUDA 失敗自動退 CPU int8。

## ADR-005 2026-09-18 情境 A/B 不排程自動化
- 理由：偶發工作、需人工確認腳本；Kinocut 品檢與互動流程在 Claude Code 內足夠。
- 後果：n8n/GitHub Actions 放 Backlog。

## ADR-006 2026-09-18 兩個情境分兩個 repo
- 決策：trip-cut（情境 A/B）與 info-shorts（情境 3）分開。
- 理由：輸入型態、觸發方式、風格系統都不同；共用的只有 Kinocut/Remotion/edge-tts 這類外部工具，不需要共用程式碼。
- 後果：若之後出現重複程式（例如 Remotion 字幕層），再抽成共用 npm/pip 套件。

## ADR-007 2026-09-18 執行環境改為 Windows 原生，不用 WSL2
- 決策：推翻 ADR 前的預設假設（`docs/SETUP.md` 原版全走 WSL2），改成整條 pipeline（`tripcut` CLI、Kinocut MCP、Remotion、faster-whisper、edge-tts）直接在 Windows 原生環境跑，不透過 WSL2。
- 理由：
  1. 使用者 Windows 端已經有 `ffmpeg`，且逐一確認 exiftool、Kinocut（1.15.1，官方支援 macOS/Linux/**Windows**，只要 FFmpeg 在 PATH 上）、Remotion（headless Chrome 在 Windows 上會抓 Windows 版，不需要 WSL2 SETUP.md 列的那堆 Linux-only apt lib）、faster-whisper（ctranslate2 有官方 Windows wheel，CUDA 透過 `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` 這兩個 pip 套件即可）、edge-tts 全部都原生支援 Windows。
  2. GPU 不是決定性因素：驅動裝在 Windows 上，WSL2 是透傳、Windows 原生是直接存取，兩邊 faster-whisper 都能吃到 CUDA，效能差異不大。
  3. 兩套環境（WSL2 + Windows）等於要重複安裝 Python/Node/ffmpeg/edge-tts 兩份，浪費磁碟空間也容易版本不同步；使用者明確不想要這種重複。
- 後果：
  - `docs/SETUP.md` 全面改寫成 PowerShell 指令；不再需要 `sudo apt install`、WSL2 distro、`/mnt/c` 路徑問題。
  - `CLAUDE.md` §3 技術棧「執行環境」改為 Windows 原生。
  - 素材與程式碼都在同一個 Windows 檔案系統路徑下，不再有「/mnt/c 下跑很慢」的顧慮。
  - 若之後真的需要 Linux-only 工具（目前沒有），再開新 ADR 評估要不要局部借 WSL2。

## ADR-008 2026-09-19 長片預裁走專案 ffmpeg，Kinocut 留給短來源與後製

`tripcut clips` 對 2025-03-xitou 的 `edl-style.json`（33 段，來源含 969s 的 v010）實測：

| 路徑 | 每段耗時 | 33 段合計 |
|---|---|---|
| Kinocut（`uvx --from kinocut kino` → `trim` + `resize` 兩趟） | ~110s | 估 ~60 分 |
| 專案 ffmpeg（`--no-kino`，`-ss` 放 `-i` 前做 input seek，單次 encode） | ~2.3s | **77s** |

差距來自兩件事：Kinocut 走 trim→resize **兩次 encode**，而且每段都用 `uvx` 重開一次環境；
專案路徑是 input seek + 單次 encode，不用把 969s 的來源從頭解到取用點。

**決定**：`tripcut clips` 在**長來源（>3 分鐘）**時預設走 `--no-kino`。
這不推翻 ADR-002——hard rule 6 本來就允許「專案內腳本」，`_precut_ffmpeg` 是固定參數的專案腳本，
不是臨時拼的 raw ffmpeg。Kinocut 仍然是**後製／轉檔／品檢**（`kino export`、`kino probe`）的唯一路徑。

