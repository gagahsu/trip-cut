# SETUP — Windows 原生環境

> 見 `docs/DECISIONS.md` 的 ADR-007：整條 pipeline 直接在 Windows 上跑，不用 WSL2。
> 素材與程式碼都放在同一個 Windows 路徑（例如 `projects/<trip>/raw/`），不用擔心 `/mnt/c` 的效能問題。

目標：`ffmpeg`、`exiftool`、Python 3.11+、Node.js 22+、Kinocut、Remotion 全部裝在 Windows 端，指令用 PowerShell。

## 0. 前置

- Windows 10/11。
- NVIDIA 驅動裝好即可（`nvidia-smi` 在 PowerShell 內可執行）。
- GPU 等級不高的假設：VRAM ≤ 6GB。Whisper 用 `small` + `int8_float16`；Remotion render 走 CPU 沒關係。

## 1. 系統工具

- **ffmpeg**：`winget install Gyan.FFmpeg`（或已經有的話跳過，確認 `ffmpeg -version` 有反應）。
- **exiftool**：`winget install OliverBetz.ExifTool`。裝完要開新的終端機視窗才會吃到更新的 PATH。
- **Node.js 22+**：`winget install OpenJS.NodeJS.LTS`（或用 `nvm-windows` 管理版本）。確認 `node -v` ≥ 22。
- **uv**（Python 版本管理 + 套件執行器，取代 venv 手動操作）：
  ```powershell
  irm https://astral.sh/uv/install.ps1 | iex
  uv python install 3.11
  ```

驗證：
```powershell
ffmpeg -version
exiftool -ver
node -v
npm -v
uv --version
```

## 2. Python（tripcut 套件）

```powershell
cd C:\Users\<you>\Videos\Camera01\trip-cut
uv venv --python 3.11
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[transcribe,dev]"
tripcut --help
```

faster-whisper GPU 測試：
```powershell
python -c "from faster_whisper import WhisperModel; m=WhisperModel('small',device='cuda',compute_type='int8_float16'); print('cuda ok')"
```
失敗（多半是缺 cuBLAS/cuDNN DLL）→
```powershell
uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```
再不行就用 CPU（`device="cpu", compute_type="int8"`），`small` 模型在 CPU int8 上 1 分鐘影片約 30–60 秒，可接受。

## 3. Remotion

```powershell
cd remotion
npx create-video@latest .    # TypeScript, blank template（Phase 0 尚未建立時執行）
npm install
npx remotion browser ensure  # 下載 Windows 版 headless Chrome
npx remotion studio          # 開發預覽（瀏覽器開 http://localhost:3000）
```
Remotion 授權：個人／3 人以下公司免費；公司規模以上需 company license（見 DECISIONS）。

## 3.5 字型（不用手動裝）

字幕用的 **Noto Sans TC** 由 `@remotion/google-fonts` 在 render 時載入（見
`remotion/src/style.tsx`），**不依賴機器上裝了什麼字型**。代價是 render 時要能連外網
抓字型檔；完全離線的機器要改成把 woff2 放進 `remotion/public/` 再用 `@remotion/fonts`
的 `loadFont({family, url})` 指過去。

> 早期版本寫死系統字型 `"Noto Sans TC Black"`，沒裝的機器會**靜默**退回
> Microsoft JhengHei UI（沒有 Black 字重），章節標和強調字會變細、風格跑掉且不會報錯。
> 現在不會了。

## 4. Kinocut MCP

```powershell
uvx --from kinocut kino doctor   # 確認 ffmpeg/ffprobe 偵測 OK
```
不需要另外 `pip install`：`.mcp.json` 用 `uvx --from kinocut kino` 啟動，`uv` 會自動抓套件跑在隔離環境裡。Claude Code 讀 repo 根目錄的 `.mcp.json`；啟動 Claude Code 後用 `/mcp` 確認 `kinocut` 已連線。

若要在自己的 venv 裡直接用 CLI（非透過 MCP）：
```powershell
uv pip install kinocut
kino --help
```

## 5. edge-tts（可選，旁白用）

```powershell
uv pip install edge-tts
edge-tts --list-voices | Select-String "zh-TW"
edge-tts --voice zh-TW-HsiaoChenNeural --text "測試" --write-media test.mp3 --write-subtitles test.srt
```
非官方服務，可能失效；失效時改 Kokoro TTS（本機）。

## 6. 專案資料夾

不用再從 Windows 複製到 WSL，素材直接放進專案資料夾即可：
```powershell
mkdir projects\2026-10-okinawa\raw
# 把手機/相機的照片影片丟進 projects\2026-10-okinawa\raw\
```
成品在 `projects\2026-10-okinawa\out\`，直接在 Explorer 開。

## 7. 驗證清單

- [ ] `ffmpeg`、`exiftool`、`nvidia-smi`（若有 GPU）可用
- [ ] `node -v` ≥ 22、`npm -v` 可用
- [ ] `uv --version` 可用；`uv venv --python 3.11` 建得起來
- [ ] `tripcut --help` 可跑
- [ ] faster-whisper cuda 或 cpu 任一可跑
- [ ] `npx remotion studio` 可開
- [ ] Claude Code `/mcp` 看到 `kinocut`
- [ ] `projects/*/raw`、`work`、`out` 已被 `.gitignore` 排除
