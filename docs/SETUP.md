# SETUP — WSL2 環境

目標：所有分析與渲染在 WSL2 (Ubuntu 22.04/24.04) 執行；素材放在 WSL 檔案系統內（`~/trip-cut/projects/...`），**不要放在 `/mnt/c/` 下跑**（I/O 慢 3–10 倍，Remotion render 會很痛）。

## 0. 前置

- Windows 11，WSL2 已啟用，Ubuntu 已安裝。
- NVIDIA 驅動裝在 Windows 端即可（WSL2 會自動帶 CUDA 支援）。確認：`nvidia-smi` 在 WSL 內可執行。
- GPU 等級不高的假設：VRAM ≤ 6GB。Whisper 用 `small` + `int8_float16`；Remotion render 走 CPU 沒關係。

## 1. 系統套件

```bash
sudo apt update && sudo apt install -y ffmpeg exiftool libheif-examples \
  python3.11 python3.11-venv python3-pip build-essential \
  # Remotion 在 headless Chrome 需要的 libs
  libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2 libxshmfence1 fonts-noto-cjk
ffmpeg -version && exiftool -ver
```

## 2. Python

```bash
cd ~/trip-cut
python3.11 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install faster-whisper pillow pillow-heif jsonschema typer ruff pyright kinocut
pip install -e .            # 本專案（Phase 1 建好 pyproject 後）
```

faster-whisper GPU 測試：
```bash
python -c "from faster_whisper import WhisperModel; m=WhisperModel('small',device='cuda',compute_type='int8_float16'); print('cuda ok')"
```
失敗（多半是 cuBLAS/cuDNN 版本）→ `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` 並依 faster-whisper README 設定 `LD_LIBRARY_PATH`；再不行就用 CPU，`small` 模型在 CPU int8 上 1 分鐘影片約 30–60 秒，可接受。

## 3. Node / Remotion

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
node -v   # ≥ 22
cd ~/trip-cut/remotion && npm install
npx remotion browser ensure     # 下載 headless Chrome
npx remotion studio              # 開發預覽（瀏覽器開 http://localhost:3000）
```
Remotion 授權：個人／3 人以下公司免費；公司規模以上需 company license（見 DECISIONS）。

## 4. Kinocut MCP

```bash
pip install kinocut        # 已在上面裝過
kinocut --help             # 確認 CLI 可用
```
Claude Code 讀 repo 根目錄 `.mcp.json`。**Phase 0 任務**：依 Kinocut README 確認 MCP 啟動指令（`.mcp.json` 目前是 placeholder）。啟動 Claude Code 後用 `/mcp` 確認 kinocut 已連線。

## 5. edge-tts（可選，旁白用）

```bash
pip install edge-tts
edge-tts --list-voices | grep zh-TW
edge-tts --voice zh-TW-HsiaoChenNeural --text "測試" --write-media /tmp/t.mp3 --write-subtitles /tmp/t.srt
```
非官方服務，可能失效；失效時改 Kokoro TTS（本機）。

## 6. 從 Windows 拿素材

```bash
# 從手機匯出到 Windows 後
cp -r /mnt/c/Users/<you>/Pictures/okinawa/* ~/trip-cut/projects/2026-10-okinawa/raw/
```
成品回 Windows：`cp out/*.mp4 /mnt/c/Users/<you>/Videos/`，或在 Explorer 開 `\\wsl$\Ubuntu\home\<you>\trip-cut\projects\...`。

## 7. 驗證清單

- [ ] `ffmpeg`、`exiftool`、`nvidia-smi` 可用
- [ ] faster-whisper cuda 或 cpu 任一可跑
- [ ] `npx remotion studio` 可開
- [ ] Claude Code `/mcp` 看到 kinocut
- [ ] `projects/` 在 WSL 檔案系統內、已被 .gitignore
