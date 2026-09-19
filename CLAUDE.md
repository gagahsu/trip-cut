# trip-cut — 旅遊素材 AI 剪輯 pipeline

> 給 Claude Code 的入口文件。開始任何工作前先讀完本檔，再依需要讀 `docs/`。
> 進度與待辦以 `docs/TASKS.md` 為準；架構決策以 `docs/DECISIONS.md` 為準，不要私自推翻。

## 1. 這個專案在做什麼

把出遊的照片＋影片，經過「本機分析 → 腳本 → 剪輯決策 → 渲染」四個階段，產出一支回憶影片（預設 9:16 直式，另可輸出 16:9）。

兩種使用情境，共用同一條 pipeline：

| 情境 | 輸入 | 差別 |
|---|---|---|
| A. 有腳本 | 素材 + 使用者寫好的 `script.md` | 跳過腳本生成，直接進 EDL |
| B. 沒腳本 | 只有素材 | Claude 先看素材出 `script.md` 草稿 → 使用者定案 → 再進 EDL |

## 2. 不可違反的原則（Hard rules）

1. **素材絕不離開本機。** 分析只走「FFmpeg 抽幀 + exiftool + faster-whisper → Claude Code 讀圖／讀文字」。不呼叫 Gemini、Mistral 或任何第三方 vision API，即使免費。
2. **AI Agent 以外一律免費開源。** 新增任何依賴前先確認授權（Remotion 僅限個人／3 人以下免費，見 DECISIONS）。
3. **Git 不追蹤原始媒體。** `raw/`、`work/`、`out/` 全在 `.gitignore`，只追蹤程式碼、schema、文件與 `script.md`/`edl.json` 等文字產物。
4. **腳本定案前不渲染。** 情境 B 一定停在 `script.md` 等使用者確認，不可自行進入 EDL 與 render。
5. **刪除或覆寫使用者檔案前必須詢問。** 包含 `raw/`、`script.md`、`edl.json`。
6. **剪輯執行只走 Kinocut MCP 或專案內腳本**，不要臨時拼 raw ffmpeg 指令（抽幀、探測等分析用途除外，見 `docs/PIPELINE.md`）。

## 3. 技術棧（已定案）

- 執行環境：**Windows 原生**（見 ADR-007，已推翻先前 WSL2 的預設假設）；不用 WSL2。
- 語言：Python 3.11+（編排、分析）、Node.js 22+ / TypeScript（Remotion 渲染層）。
- 分析：`ffmpeg`/`ffprobe`、`exiftool`、`faster-whisper`（GPU 等級不高 → 預設 `small` 模型、`int8_float16`；CUDA 走 Windows 原生 `nvidia-cublas-cu12`/`nvidia-cudnn-cu12`，失敗自動退 CPU）。
- 剪輯執行：**Kinocut**（MCP server，包 FFmpeg；官方原生支援 Windows）。
- 渲染／轉場／字卡：**Remotion**，JSON-props 驅動的 `Montage` composition（架構參考 `chrix911/maintain-video` 的單一 props 檔模式）。
- 快速備援：`Trekky12/kburns-slideshow`（純 FFmpeg Ken Burns），Remotion 未就緒時可先出片。
- 語音旁白（可選）：`edge-tts`（zh-TW 聲音，同時輸出 mp3 + srt）。

## 4. 目錄結構

```
trip-cut/
├── CLAUDE.md                ← 你正在讀的檔
├── README.md
├── docs/
│   ├── ARCHITECTURE.md      系統架構與資料流
│   ├── PIPELINE.md          四階段詳細規格、每階段的輸入輸出與指令
│   ├── SETUP.md             Windows 原生環境安裝（含 GPU）
│   ├── TASKS.md             分階段待辦（開工前必讀）
│   ├── DECISIONS.md         ADR：為什麼選這些工具
│   ├── STYLE-TEMPLATE.md    參考影片拆解：剪輯規則／字幕／音樂／色調（寫 script.md 與 edl.json 前先讀）
│   └── REFERENCES.md        外部工具與參考專案連結
├── schemas/
│   ├── manifest.schema.json 素材清單
│   └── edl.schema.json      剪輯決策表
├── src/tripcut/             Python 套件（CLI 入口：`tripcut`）
│   ├── ingest.py            掃描 raw/、exiftool、ffprobe → manifest.json
│   ├── frames.py            場景切換抽幀 / 等距抽幀
│   ├── transcribe.py        faster-whisper → transcript.json
│   ├── contact_sheet.py     把抽幀拼成 contact sheet 給 Claude 看
│   ├── edl.py               驗證 edl.json、轉成 Remotion props
│   └── cli.py
├── remotion/                Remotion 專案（獨立 package.json）
│   └── src/Montage.tsx      單一 props 檔驅動的主 composition
├── projects/<trip-name>/    每趟旅行一個資料夾（見下）
├── .mcp.json                Claude Code 的 MCP 設定（Kinocut）
└── .gitignore
```

每趟旅行：

```
projects/2026-10-okinawa/
├── raw/            使用者放入的原始照片影片（不進 git）
├── work/           抽幀、contact sheet、transcript（不進 git）
├── manifest.json   ingest 產物
├── script.md       腳本（情境 A 使用者提供；情境 B Claude 產草稿）
├── edl.json        剪輯決策表（Claude 產生、使用者可改）
├── props.json      edl → Remotion props
└── out/            成品（不進 git）
```

## 5. 標準工作流程

```
tripcut ingest  projects/<trip>          # raw → manifest.json
tripcut frames  projects/<trip>          # 抽幀 + contact sheet
tripcut transcribe projects/<trip>       # 有人聲的影片才跑
# ---- 情境 B：Claude 讀 contact sheet + transcript + manifest → 寫 script.md 草稿，停下等確認 ----
# ---- 情境 A/B：Claude 依 script.md 產 edl.json ----
tripcut edl-validate projects/<trip>     # 對 schema 驗證、檢查時間碼不越界（--edl edl-120.json 可指定版本）
tripcut clips projects/<trip>            # Kinocut 預裁每段到 work/clips/（先跑，props 才會指向預裁檔）
tripcut props projects/<trip>            # edl.json → props.json，並把用到的檔 hard link 到 work/public/
# ---- 渲染：cd remotion && npx remotion render Montage <out.mp4> --props=<props.json> --public-dir=<專案>/work/public ----
# ---- 後製／轉檔／品檢：Kinocut MCP（或 kino CLI） ----
```

Claude 在每個階段完成後回報：產物路徑、發現的問題、下一步需要使用者做什麼。

## 6. 開發規範

- Python：`ruff` + `pyright`（basic），型別標註必填，函式短、可單測。
- TypeScript：`strict: true`；Remotion 動畫只用 `useCurrentFrame` / `interpolate` / `spring` / `<Sequence>`，禁止 CSS transition / requestAnimationFrame（render 時會壞）。
- 所有時間單位：EDL 用**秒（float）**，Remotion 內部才轉 frame（30 fps）。
- 檔名：專案資料夾 `YYYY-MM-<slug>`；素材不改名，用 manifest 的 `id` 對應。
- Commit 訊息：`feat|fix|docs|chore(scope): 說明`，中文可。
- 新增外部依賴 → 先在 `docs/DECISIONS.md` 加一條 ADR 再裝。
- 遇到 Kinocut / Remotion 文件與本專案描述不一致 → 以官方文件為準，並回報更新本檔。

## 7. 現在的階段

看 `docs/TASKS.md` 的「當前階段」。Phase 0（環境）與 Phase 1（ingest/frames）尚未開始時，不要動 Remotion。

## 8. 遇到不確定時

- 素材要不要上傳 → 一律不。
- 腳本風格不明 → 問使用者，不要自己定調。
- 工具指令不確定（尤其 Kinocut MCP 啟動方式、Remotion 版本 API）→ 查官方文件或 `docs/REFERENCES.md`，不要憑記憶猜。
