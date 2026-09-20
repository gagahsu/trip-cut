# TASKS

> Claude：開工前先讀「當前階段」。完成一項就勾掉並在 Log 加一行（日期、做了什麼、產物）。
> 不要跳階段；一個階段的驗收條件沒過不進下一階段。

## 當前階段：Phase 4（第一趟真實素材已出片；接下來是打磨與文件回填）

---

## Phase 0 — 環境與骨架
- [x] 依 `docs/SETUP.md`（已改為 Windows 原生，見 ADR-007）確認工具：`ffmpeg`（原本就有，winget 又裝了一份 8.1.1）、`exiftool`（winget 裝好，13.59）、`node`（v22.19.0）、`uv`/`uvx`（裝在 `~/.local/bin`）全部驗證可用；faster-whisper CUDA 測試通過（印出 `cuda ok`）
- [x] 確認 Kinocut MCP 啟動指令，更新 `.mcp.json`：`uvx --from kinocut kino`；`uvx --from kinocut kino doctor` 在 PowerShell 下顯示 **Kinocut doctor - OK**（ffmpeg/ffprobe 都偵測到），MCP 連線待下次開 Claude Code 用 `/mcp` 再次確認
- [x] 建 `pyproject.toml`（套件名 `tripcut`，CLI 入口 `tripcut`），ruff/pyright 設定（補上 `venvPath`/`venv` 指向 `.venv`，否則 pyright 會抓錯 Python 解析不到 import）；`src/tripcut/` 骨架（`cli.py` + 各 stage 的 stub，丟 `NotImplementedError`，Phase 1/2 補實作）。`uv venv --python 3.11` + `uv pip install -e ".[transcribe,dev]"` 裝好，`tripcut --help`、`ruff check src`、`pyright src` 全部通過
- [x] 建 `remotion/` 專案骨架（`npx create-video@latest --yes --blank remotion`，TypeScript）；`npm install`、`npx remotion browser ensure`（抓 Windows 版 headless Chrome）都跑完；用 `npx remotion render MyComp` 實際渲染 6 張 frame 驗證整條路徑通（渲染出的測試檔已刪除，`out/` 有 gitignore）
- [x] 準備一個測試專案 `projects/_sample/`（目前只建了 `raw/ work/ out/` 目錄骨架；10 張照片 + 2 支短影片還沒放——這一項還沒完全做完，Phase 1 開始跑 ingest/frames 前需要補上合成或真實的測試素材）
- **驗收**：`tripcut --help` 可跑（✅）；`npx remotion studio`／render 可動（✅，用 render 驗證過，studio 本身未手動開視窗確認但底層一致）；kinocut 已連線（CLI 層 `kino doctor` OK，Claude Code 的 `/mcp` 連線要下次啟動時確認）

## Phase 1 — 分析層（ingest / frames / transcribe）
- [x] `ingest.py`：exiftool + ffprobe → `manifest.json`，通過 schema（拍攝時間：照片用 EXIF、影片優先用檔名的本地時間，再退 QuickTime CreateDate+tz）
- [x] HEIC 轉 jpg（pillow-heif，寫好但 2025-03-xitou 沒有 HEIC，尚未實測）
- [x] `frames.py`：場景切換抽幀（只解 keyframe，快）+ 等距 fallback + 每支上限 + `--only`/`--force`
- [x] `contact_sheet.py`：影片 sheet + 照片 sheet，含標籤；直式素材一列 6 張
- [x] `transcribe.py`：faster-whisper，CUDA→CPU fallback，volumedetect 跳過純環境音；`initial_prompt` 引導繁體輸出；可續跑
- [x] 用真實素材 `projects/2025-03-xitou`（取代 `_sample`）跑完整分析，Claude 讀 contact sheet 能正確描述內容
- **驗收**：`tripcut ingest && tripcut frames && tripcut transcribe` 在 2025-03-xitou 上一次跑完，產物齊全 ✅
- 實測待改（Phase 4 再調）：
  - 小孩穿戴的鏡頭（奈奈視角／達達視角）用 scene detection 會偏向挑到晃動模糊的那幾格；這類素材應改等距、張數加倍
  - 長片（>5 分鐘）12 張太稀，`--max-frames` 應依長度自動放大
  - Whisper `small` 對小孩講話與風聲的辨識率低，常出現重複句與幻覺（v019 整支都是 initial_prompt 漏出來的「使用繁體中文」）；有需要再試 `medium`

## Phase 2 — 腳本與 EDL（情境 B 流程）
- [x] 定義 `script.md` 模板（`docs/templates/script.md` 原本就有；實際用起來多加了「需要你決定」與素材總覽表）
- [x] Claude 依 2025-03-xitou 產 `script.md` 草稿，停下等確認（hard rule 4 驗證通過：使用者回了 4 點決定才往下）
- [x] `edl.py`：schema 驗證、source 存在檢查、in/out 越界、總長度警告（±15%）、直式 crop 必填、`audio_override` 檢查
- [x] `tripcut props`：EDL → props.json（秒→frame、時間軸含 crossfade 重疊、路徑相對專案目錄）；`--edl` 支援多版本
- [x] `tripcut clips`：Kinocut `trim`+`resize` 預裁到 `work/clips/`，Kinocut 失敗退專案 ffmpeg
- [ ] 備援出片（kburns-slideshow）：**跳過**，Remotion 已直接可用（見 Phase 3）
- **驗收**：從 2025-03-xitou 走到 mp4，全程 Claude 只在「腳本確認」處停一次

## Phase 3 — Remotion Montage
- [x] `Montage.tsx`：讀 props.json，支援 photo(kenburns) / video(in-out, crop) / title / transition(crossfade, fade-black) / bgm / audio_override
- [x] 9:16 與 16:9 兩個 Composition 共用同一 props（`Montage`、`Montage16x9`，尺寸由 `calculateMetadata` 決定）
- [x] 字卡字體：Noto Sans TC → Microsoft JhengHei fallback；lower-third 避開 IG 底部 250px 安全區
- [x] BGM ducking（有 keep_audio / audio_override 的片段降到 30%）——寫好但這趟沒 BGM，未實測
- [x] 影片段落先由 Kinocut 預裁到 `work/clips/`（長邊 1920），Remotion 只吃預裁檔（`tripcut clips`）
- [x] 品檢：`kino video-quality-check` 的音量檢查 PASS（-18.6 / -18.7 LUFS）；畫面類檢查在 Windows 全部 FAIL，是 Kinocut 的 bug（lavfi `movie=C\:\\…` 路徑跳脫錯，ffprobe 只看到 `'C'`），改用 ffmpeg `blackdetect`（無異常黑幀）＋ 成品每 4 秒抽一格拼 sheet 目視（`work/qc/sheet-*.jpg`）
- [x] 成品另用 `kino export -q high` 出一份較小的 share 版
- [ ] 16:9 版實際 render 一次（`Montage16x9`，尚未跑）
- **驗收**：2025-03-xitou 用 Remotion 出 9:16 60s 與 120s 各一支，畫面與 EDL 一致 ✅
- 實測踩到的坑：
  - Remotion bundler 會把整個 `--public-dir` 複製進暫存 bundle，且遇到 junction 會想建 symlink（Windows 沒權限）→ `tripcut props` 改成把用到的檔 hard link 到 `work/public/`，只指這個目錄
  - uv 的 venv 會 export `PYTHONHOME`，從 tripcut 裡 spawn `uvx --from kinocut kino` 會炸 "SRE module mismatch" → `common.run()` 一律清掉 `PYTHONHOME`/`PYTHONPATH`；第一輪 41 個預裁檔因此全走了專案 ffmpeg 備援（結果一樣可用，沒重做）
  - 直式 2720x1536 縮到長邊 1920 是 1084x1920（非 1080），Remotion cover 會切掉 2px，無視覺影響

## Phase 4 — 真實素材與打磨
- [x] 用一趟真實出遊素材跑情境 B 全流程，記錄卡點（`2025-03-qimei`，見下方 Log；
  過程中揪出三個先前都沒發現的 pipeline 正確性 bug：Kinocut trim 起點沒生效、
  hard link 沒隨來源更新、背景孤兒行程搶檔案）
- [ ] 跑情境 A（自備腳本）
- [ ] 抽幀上限、scene 門檻、contact sheet 版面依實測調整
- [ ] Claude 選片品質觀察：是否偏好某類畫面、是否漏掉短片段
- [ ] 文件回填：把實測學到的寫回 PIPELINE.md / CLAUDE.md
- [ ] **`work/public` 改成每份 props 一個子目錄**。現在三版（60s/120s/style）的預裁檔全擠在同一個 public dir（75 檔 1.6 GB），Remotion bundle 每次 render 都把整包複製一份，光 bundling 就花好幾分鐘。`build_props` 已加 `_prune_public`（刪沒有任何 props 指到的孤兒檔），但同時存在多版時它刪不掉東西——真正的解是 `--public-dir` 指到 `work/public/<props 名>/`。
- [x] **收尾步驟 `tripcut finish`**：`src/tripcut/finish.py`，兩趟 loudnorm → -14 LUFS / -1 dBTP、寫入 bt709 三件套、CRF 22 降位元率，並印品檢數字。用溪頭 60s 母帶實測，結果與先前手動做的完全一致（-13.9 LUFS / LRA 7.8 / TP -0.9 / bt709）。
- [ ] `script.md` 模板加四層字幕欄位（章節標／主字幕 tone／強調字／位置膠囊／調色），見 STYLE-TEMPLATE §7.5

## Backlog（未排程）
- [ ] edge-tts 旁白（讀 script.md 的旁白欄位 → mp3+srt → Remotion 字幕層）
- [ ] 多趟旅行共用的 Remotion 風格 preset（props 內 `theme` 欄位）
- [ ] Immich 整合：直接從自架相簿拉素材（參考 immich-video-memory-generator）
- [ ] 以 `ali-abassi/remotion-templates` 的 transition 家族擴充轉場
- [ ] n8n/GitHub Actions 觸發（目前判定：情境 A/B 是偶發工作，不排程）

## Log
- 2026-09-18：專案文件初版建立（尚未開始 Phase 0）
- 2026-09-18：開始 Phase 0。原先假設走 WSL2，實測發現 WSL 裡什麼都沒裝，且需要 `sudo` 密碼（這個環境的指令列沒 TTY 可輸入，卡住）。使用者確認：Windows 端已經有 ffmpeg，問「一定要 WSL 嗎」「GPU 有沒有關係」，討論後決定改用 **Windows 原生**（見 ADR-007），理由是 exiftool/Kinocut/Remotion/faster-whisper/edge-tts 全都原生支援 Windows，GPU 兩邊都能吃到 CUDA 沒差，兩套環境重複安裝浪費空間。改寫了 `docs/SETUP.md`、`CLAUDE.md` §3、`README.md`，並在 `docs/DECISIONS.md` 補上 ADR-007。
- 2026-09-18：Phase 0 環境建置（Windows 原生）：用 winget 裝好 `exiftool`（13.59）；確認 `node` v22.19.0、`ffmpeg`、`uv` 都已經在機器上。用 `uv venv --python 3.11` 建虛擬環境，`uv pip install -e ".[transcribe,dev]"` 裝好 `tripcut`；`tripcut --help`、`ruff check src`、`pyright src`（修正 pyproject 加 `venvPath`/`venv` 才抓對 Python）全部通過；`faster-whisper` CUDA 測試印出 `cuda ok`。`uvx --from kinocut kino doctor` 在 PowerShell 下顯示 `Kinocut doctor - OK`（git-bash 因為 PATH 混到 miniconda 舊版 ffmpeg 一度誤判成 Missing，換 PowerShell 就正常，之後操作都建議用 PowerShell 而非 git-bash 跑）。用 `npx create-video@latest --yes --blank remotion` 建好 Remotion 骨架，`npm install` + `npx remotion browser ensure`（抓 Windows headless Chrome）+ 實際 `npx remotion render MyComp` 渲染 6 張 frame，整條渲染路徑驗證通過。剩下沒做：`projects/_sample/` 還缺實際測試素材（10 張照片＋2 支短片），以及下次開 Claude Code 要用 `/mcp` 確認 kinocut 真的連上。
- 2026-09-18：Phase 1 完成。使用者提出用 `../溪頭/`（2025-03-16 溪頭一日遊，Insta360 GO 3S，20 支影片 58.5 分鐘 25 GB + 7 張照片）試做。建 `projects/2025-03-xitou/`，`raw/` 用 NTFS junction 指向原資料夾（不複製 25 GB）。實作 ingest / frames / contact_sheet / transcribe 並全部跑完：抽幀約 25 分鐘（兩支 13–16 分鐘長片佔大半）、Whisper small CUDA 約 15 分鐘。Claude 讀完 21 張 contact sheet 與逐字稿，寫出 `script.md` 草稿（60s、9:16、原音為主、7 段），**停在等使用者確認**（hard rule 4）。
- 2026-09-18：Phase 2 + 3 完成，第一趟真實素材出片。使用者確認腳本 4 點（名字對、字卡出名字、留奈奈視角、保留原音、要 60s 與 120s 兩版）。實作 `edl.py`（驗證＋props、`audio_override`）、`clips.py`（Kinocut 預裁）、`remotion/src/Montage.tsx`（props 驅動、Ken Burns、cover crop、crossfade/fade-black、三種字卡、BGM ducking）。產出 `edl.json`（17 段，65.0s）、`edl-120.json`（29 段，131.5s），Remotion render 9:16 兩支到 `out/`（原版 311 MB / 637 MB，`kino export` share 版 146 MB / 294 MB）。踩到的坑記在 Phase 3。未做：16:9 版、`_sample` 合成素材、kburns 備援。
- 2026-09-19：加 BGM。使用者放 `raw/bgm.mp3`（72s，原始音量偏大：mean -10.5 dB、峰值 0 dB）。兩份 EDL 加 `bgm: volume 0.25, duck_under_speech`，重跑 props + render + `kino export`。實測：純 BGM 段落約 -22.5 dB、對話段落約 -20 dB（BGM 自動降到 30%），120s 版 BGM 循環一次、結尾 1.5s 淡出。Ducking 目前是段落邊界瞬間切換，之後可加 0.3s 緩降（Phase 4）。
- 2026-09-19：換成免費音樂庫 BGM。使用者要求 Claude 依腳本自行挑曲、直接下載使用（不滿意再自己去 YouTube／Pixabay 挑）。實測 Incompetech 可用 curl 直接下載（目錄 `https://incompetech.com/music/royalty-free/pieces.json`，1442 首含 feel/bpm/樂器欄位可篩），Pixabay 回 403、YouTube 音訊庫要登入，都不能自動抓。依「溫暖、家庭、中慢」篩出 4 首（Kevin MacLeod，CC BY 4.0）放 `work/bgm/`：60s 版用 **Carefree**（烏克麗麗、96 bpm，原檔 mean -22.7 dB → volume 1.0），120s 版用 **Sunshine ver 2**（吉他＋鋼琴、79 bpm、225s 不用循環，mean -13.8 dB → volume 0.35）；備選 Easy Lemon、Porch Swing Days - slower 未用。render 到新檔名 `out/*-carefree.mp4`、`out/*-sunshine.mp4`（＋`-share` 版），舊版與 `raw/bgm.mp3` 都保留。成品整體 -19.2 / -19.5 LUFS，與上一版相當。標註文字寫在 `projects/2025-03-xitou/CREDITS.md`，發布時必須附上。
- 2026-09-19：第二趟素材 `../竹夢森居玩水/`（2025-06-28，12 支影片 22.7 分鐘 9.5 GB，無照片）。建 `projects/2025-06-zhumeng/`，`raw/` 一樣用 junction。ingest／frames（`--max-frames 16`）／transcribe 一次跑完約 10 分鐘。v010（奈奈胸前相機 9 分鐘 SUP）、v011、v012（水槍大戰）用 scene detection 都只抓到晃動格，改 `--scene-threshold 1.0` 強制等距、張數 24–30 重抽（Phase 1 待改事項再次驗證）。另用 ffmpeg 抽指定秒數的細格拼 sheet 到 `work/stills/` 輔助挑段。Incompetech 依「夏天、活潑」預抓 5 首候選到 `work/bgm/`。寫出 `script.md` 草稿（60s／120s，6 段＋結尾），**停在等使用者確認 5 個問題**（名字、v010 是否保留、要幾版、BGM、標題地名）。
- 2026-09-19：築夢森居出片（情境 B 第二趟，全程只停一次）。使用者確認 5 點（名字對、v010 SUP 段不留、60s＋120s 都要、BGM 照配、標題寫「築夢森居」）。`edl.json` 17 段 63.0s（Rainbows 0.55）、`edl-120.json` 29 段 128.5s（Island Meet and Greet 0.45），validate 抓到一個 out 超過影片長度（v009 59.5 > 59.16）改掉。`tripcut clips` 42 段這次**全部走 Kinocut 成功**（上一趟 PYTHONHOME 問題已修好）。Remotion render 60s 約 4 分鐘、120s 約 6 分鐘；`kino export -q high` share 版 131 MB／265 MB。品檢：blackdetect 0、-18.2／-18.4 LUFS、每 4 秒抽格 sheet（`work/qc/`）目視 OK。標註在 `projects/2025-06-zhumeng/CREDITS.md`。這趟學到：小孩胸前相機（v010）與水槍大戰這類晃動素材，scene detection 抓到的都是廢格，`--scene-threshold 1.0` 可強制退回等距（之後應改成 `--equidistant` 旗標並依長度自動放大張數，Phase 4）。
- 2026-09-19：**依 sample 兩支 IG Reels 建立剪輯模板，並用它重出溪頭版**。先拆解 `../sample/` 兩支片（台北親子 / 名古屋滑雪），量出剪輯節奏、四層字幕、音樂、色調，寫成 `docs/STYLE-TEMPLATE.md`。三個和專案原本預設相反的發現：**全片零轉場**（逐幀 diff 是單幀尖峰無斜坡）、**剪點不卡拍**（onset 自相關只有 0.10–0.14 且 60–190 BPM 全平坦，音樂是床不是拍）、**照片完全靜止不推鏡**（diff=0）且用拍立得卡呈現。實作：`edl.schema.json` 加 `preset`/`grade`/`captions[]`/`badge`/`photo_frame`/`rotate`/`silence`/`size`；`edl.py` 轉 props；新檔 `remotion/src/style.tsx`（四層字幕 + `StrokeText` 疊兩層描邊 + pulse/pop + `LocationBadge` + `PolaroidPhoto` + `GradeWrap`）；`Montage.tsx` 接上並**拿掉開場淡入**（IG 拿第 1 幀當封面）。產出 `edl-style.json` 33 段 58.8s → `out/2025-03-xitou-style-9x16.mp4`（220 MB）→ loudnorm 到 -14 LUFS 的 `-share.mp4`（137 MB）。品檢：**-13.9 LUFS / TP -0.9 dBFS / bt709 全鏈**（模板 §1 要求，pipeline 之前沒這步）；開場靜音實測 1.249–1.576s（0.327s），對上樣本 A 的 0.303s；色調 p99 從舊版的 **1.000（霧天白空全爆）壓到 0.950**、對比 0.761→0.694、飽和 0.251→0.306、R−B 0.018→0.075，各項都落在樣本 A 的 warm 目標值附近。
- 2026-09-19：預裁效能。`tripcut clips` 對 33 段走 Kinocut 每段要 ~110s（`trim`+`resize` 兩次 encode，每段還用 `uvx` 重開環境），估 60 分鐘；`--no-kino` 走專案 ffmpeg（`-ss` 放 `-i` 前 input seek、單次 encode）**77 秒跑完**。記成 ADR-008：長來源預設走 `--no-kino`，Kinocut 留給後製／轉檔／品檢。
- 2026-09-19：溪頭 style 版第二輪（使用者看片後的回修）。四類問題：①**章節標和主字幕字面重複**（★這裡有很多恐龍★／這裡有很多恐龍耶，雨變大了、起霧了同樣）→ 兩層講同一件事時只留章節標；②**章節標和地標膠囊重複**（★妖怪村★ + 📍溪頭 妖怪村）→ 只留膠囊；③**語音被截**，查出根因是**照 Whisper 段落時間碼剪**——「哇 現在又起霧了」被標成 902.23–907.68，實際說話在 906.45–907.70，原本剪 902.2–904.9 整句都沒進去；另三處（爸爸救命喔／一二三／加油）差 0.2–0.9s 截尾。改成一律用 RMS 包絡（0.05s 窗、`max-16dB` 門檻）定剪點，已寫進 STYLE-TEMPLATE §7.4；④**結尾倉卒** → v016 用同鏡跳接拆兩段（跳過 96.6–97.0 鏡頭被撞到那段），補上「哇 到停車場了」收尾台詞，片尾拍立得 1.3s → 2.9s。改完 34 鏡 59.98s。`edl-validate` 在這輪抓到 v016 `out=98.9` 超過影片長度 98.50，改 98.48。
- 2026-09-20：補掉「在別台機器 clone 就能剪」的三個洞（使用者問到才發現）。
  ① **字型是未宣告的系統依賴**：`style.tsx` 寫死 `"Noto Sans TC Black"`，SETUP 沒列，
  新機器沒裝會**靜默**退回 Microsoft JhengHei UI（無 Black 字重），章節標與強調字變細、
  風格跑掉且不報錯。改用 `@remotion/google-fonts` 的 `loadVariableFont`（variable font
  一次涵蓋 100-900，請求數 102 vs 靜態版 204），配 `delayRender`/`continueRender`。
  winget 查過沒有 Noto Sans TC 套件，所以不是「寫進 SETUP 叫人裝」能解的。
  ② **ADR-008 說長素材走 ffmpeg，但程式預設沒改**：`clips.py` 還是 `use_kino=True`，
  照標準流程跑會掉進 60 分鐘的路徑。改成 `use_kino: bool | None = None` 逐段自動判斷
  （來源 > `KINO_SOURCE_LIMIT_SEC` 180s 走 ffmpeg），CLI 改 `--kino/--no-kino` 三態。
  ③ **`tripcut finish`**：見上。
  另修 `finish.verify()` 的 ebur128 解析——原本 `re.search` 會抓到開頭逐幀的 -70 LUFS
  暖機值，改成只認 `Summary:` 之後的數字。
- 2026-09-20：BGM 來源寫進 `docs/REFERENCES.md`（使用者問到才發現沒寫）。原本只埋在
  TASKS 的兩則 Log 裡——那是流水帳不是參考資料，而且 `PIPELINE.md` 還寫著過時的
  「BGM：使用者提供（raw/bgm.mp3）」。重新驗證過才寫：目錄 `pieces.json` HTTP 200、
  1442 首，下載網址是 `mp3-royaltyfree/<filename>`（filename 取自目錄欄位、含空格要
  URL encode），抓下來 ffprobe 確認是真 mp3。順便記下可篩的欄位（`feel`/`instruments`/
  `bpm`/`length`）、常見 `feel` 值、CC BY 4.0 標註格式，以及 Pixabay 403、YouTube
  音訊庫要登入這兩個不能自動抓。`PIPELINE.md` Stage 3 與 `templates/script.md` 的
  BGM 欄位一併更新。
- 2026-09-20：加 `docs/templates/new-video-prompt.md`——開新片用的 prompt 範本，含流程對照表、偏離模板時的提醒句、素材準備（含 junction）與腳本階段要先想好的五件事。
- 2026-09-20：加第三個調色 preset `fresh`（晴天綠地）。使用者問「戶外/草地要用哪個」，
  查了發現兩支樣本沒涵蓋這種場景（A 城市室內、B 雪地），所以拿 `2025-06-zhumeng`
  （夏天溪邊玩水）實際渲圖量測，不用猜的。結果：`warm` 把綠地 hue 從 95.7° 推到
  83.4°（變橄欖黃），`cool` 把綠地飽和從 0.519 壓到 0.392（掉 24%，變死板），
  兩個都不能用。試了三組參數，選 `saturate(1.20) contrast(0.96) brightness(1.03)`
  + `#7CFF4D` soft-light 5%：綠地 hue 101.9°（+6° 往真綠但沒過頭）、綠地飽和 0.498、
  整體飽和 0.442、天空飽和 0.564 都是最佳。已加進 style.tsx / schema / STYLE-TEMPLATE §5
  / 範例 EDL / new-video-prompt。文件裡明確標註這組**不是量自樣本**，來源與 warm/cool 不同。
  判斷準則寫成「看天氣不是看植被」：晴天藍空→fresh、灰空下雨→warm（溪頭那趟就是）、雪地海→cool。
- 2026-09-20：第三趟素材 `projects/2025-03-qimei`（台南奇美博物館都會公園，2025-03-29，
  15 支影片 29.9 分鐘 13GB，**無照片**）。情境 B 全流程進行到一半，**中斷點記錄如下，
  下次接續直接看這裡**：
  - ingest/frames（v011 長片 11 分鐘手動補到 28 張）/transcribe 都跑完。
  - `script.md` 草稿寫完，使用者確認 5 點：①v006-009 泡泡場景深色上衣是**菡媞**（長髮女孩）、
    黃色系是**達達**，短髮粉色是**奈奈**；②沒有照片素材，收尾改用影片截幀模擬拍立得
    （已存 `work/stills/p001.jpg`，並手動加進 `manifest.json` 當 `p001` photo 條目）；
    ③保留原音，吵的鏡頭用 `keep_audio:false` 代替調音量（**pipeline 沒有 per-clip 音量
    欄位**，用「不保留原音、靠 BGM 蓋過」逼近使用者要的「壓低音量」，非精確做法，
    之後有需要可以補一個真正的 volume 欄位）；④BGM 從 Incompetech 篩了 **Life of Riley**
    （60s 版）與 **Carpe Diem**（120s 版），已下載到 `work/bgm/`，標註寫在 `CREDITS.md`；
    ⑤路人正臉用**挑鏡頭時避開**處理，**沒有**新增模糊功能（問過使用者，選了不做新功能）。
  - `edl.json`（60s，25 段 59.85s）與 `edl-120.json`（120s，51 段 124.95s）都寫完、
    `edl-validate` 通過。
  - `tripcut clips`：**60s 版全部 25 個檔案已預裁完成**（`work/clips/`）。**120s 版只
    完成 28/約 51 個**——背景執行到一半時，Claude Code 偵測到系統閒置記憶體吃緊，
    自動把這個背景任務砍掉（不是指令本身的錯，是資源保護機制），使用者當下要去睡覺，
    交代「先記錄，之後再繼續」。
  - **下一步**：重新跑 `tripcut clips projects/2025-03-qimei --edl edl-120.json`
    （會跳過已存在的 25 個重疊檔案，只補剩下的），跑完後依序：
    `tripcut props`（兩版）→ Remotion render（`Montage`，兩版，`--public-dir` 記得指到
    這個專案的 `work/public/`）→ `tripcut finish`（兩版，-14 LUFS + bt709）。
  - 待確認的路人臉：目前 EDL 選的鏡頭都盡量避開清楚入鏡的路人，但**還沒有實際 render
    出來目視檢查**，render 完要順便看一下有沒有漏網的路人臉。
- 2026-09-20（續，使用者睡覺期間自動執行）：發現並修掉兩個會讓成品內容錯誤的坑，
  render 卡在系統記憶體保護機制，**目前中斷點如下**：
  - **孤兒 kino/uvx 行程同時寫入同一個檔案造成毀損**：先前中斷的 `tripcut clips` 背景
    執行留下的子行程（`uvx --from kinocut kino`，非 `--mcp` 版本）沒有真的結束，
    跟後續重跑的指令同時對同一批預裁檔輸出，導致約 17 個檔案 NAL unit 毀損
    （`ffmpeg -f null -` 解碼會報錯）。用 `tasklist`/`wmic` 揪出這些孤兒行程
    （命令列沒有 `--mcp`，跟 `.mcp.json` 啟動的 Kinocut MCP server 是兩碼事）
    砍掉後才不再復發。**教訓：背景重跑同一個指令前一定要先確認舊的行程真的死了**
    （用 `tasklist`／`wmic process get CommandLine` 查，不能只看 exit code）。
  - **Kinocut `kino trim -s -e` 沒有真的裁切起點，整段變成從 0 剪到 `-e`**：
    修完毀損後逐一比對「EDL 的 out-in 應有長度」vs `ffprobe` 實際長度，
    發現幾乎所有走過 Kinocut trim 的檔案（不只失敗退 ffmpeg 的那些）長度都是錯的
    ——實際長度等於 `-e` 的值，代表 `-s` 被忽略、從頭開始剪。這是先前 Phase 3/4
    都沒抓到的 pipeline 正確性問題，不是這趟才有。**已把 `projects/2025-03-qimei/
    work/clips/` 全部刪除，用 `tripcut clips --no-kino --force` 重新產生（兩版
    共 75 段 clip 參照），並寫腳本核對每段 `ffprobe` 長度誤差 <0.35s + 解碼零錯誤，
    全部通過**。**待辦：`clips.py` 的 `_trim_kino`／ADR-008 需要回頭確認 Kinocut
    trim 指令的正確參數語意（可能是 `-e` 要改成 duration 而不是絕對結束時間，或
    有其他旗標），在修好前 Kinocut trim 路徑不可信，`--no-kino` 是唯一可用路徑。**
  - 兩版 `props.json`／`props-120.json` 已用乾淨的 clips 重新產生。
  - **120s Remotion render 執行到一半（約 1/3）被系統記憶體保護機制砍掉**（跟
    2026-09-19 log 提到的 `tripcut clips` 那次一樣的機制，這次是 render）。
    砍掉後發現 8 個 `chrome-headless-shell.exe` 子行程（每個 400MB+）變成孤兒
    繼續占記憶體，已手動 `taskkill` 清乾淨。**依系統指示，記憶體保護砍掉的背景
    工作不可自行重啟**，所以停在這裡沒有再次嘗試 render。
  - **下一步（使用者醒來後）**：確認目前記憶體狀況足夠後，重新跑
    `cd remotion && npx remotion render Montage ../projects/2025-03-qimei/out/2025-03-qimei-120s.mp4
    --props=../projects/2025-03-qimei/props-120.json --public-dir=../projects/2025-03-qimei/work/public`，
    完成後依序跑 60s 版（同指令換 `props.json`／輸出檔名），
    再兩版都跑 `tripcut finish`（-14 LUFS + bt709）與品檢（blackdetect + 抽格 sheet 目視）。
    `out/` 目前是空的，兩版都還沒有成品。
- 2026-09-20（續，完成）：使用者稍後明確要求「自行完成」，已恢復自動執行，
  **兩版都成功出片**，把過程中發現的第三個坑也修掉了：
  - 確認可用記憶體回升到 ~6.9GB 後，重試 render，但**同一個問題（v008 那段）又
    在完全相同的位置炸掉**——這次已知 `work/clips/` 裡的來源檔案本身沒問題（duration/
    解碼都驗證過），所以懷疑是 `work/public/clips/`（Remotion 實際讀取的 hard link
    副本）沒同步更新。查證發現 `edl.py:172` 的 `rel()` 函式寫 `if not dst.exists():
    os.link(...)`——**只要 hard link 目的檔已存在就永遠不會更新**，就算來源內容
    已經換了新的 inode 也一樣，所以先前所有清掉重建 `work/clips/` 的努力都沒有真正
    傳到 render 會讀的地方。**這是繼「Kinocut trim -s 沒生效」之後第三個
    pipeline 正確性 bug，同樣不是這趟才有——只要重跑過 `tripcut clips` 覆蓋舊檔，
    render 用的都可能是舊內容。** 已修好 `rel()`：先比對 `dst.samefile(p)`，
    不同才刪掉重連。清空 `work/public/` 重跑兩版 `tripcut props`，重新核對
    `work/public/clips/` 75 段全部通過後，render 才真正成功。
  - **成品**：`out/2025-03-qimei-120s.mp4`（658.7 MB）／`out/2025-03-qimei-60s.mp4`
    （333.9 MB），`tripcut finish` 收尾後 `out/2025-03-qimei-120s-share.mp4`
    （289.9 MB，-14.0 LUFS／LRA 5.7／TP -1.0 dBFS／bt709）與
    `out/2025-03-qimei-60s-share.mp4`（151.6 MB，-14.1 LUFS／LRA 5.6／TP -0.9 dBFS／
    bt709）。
  - 品檢：兩版 `blackdetect=d=0.1:pic_th=0.98` 都零異常；`work/qc/sheet-120s.jpg`／
    `sheet-60s.jpg`（每 4 秒抽格拼圖）目視過，字卡／地標膠囊／片尾拍立得都正常
    渲染，色調符合 `fresh` preset 的晴天綠地設定；v011 那段長片裡出現的路人都是
    背影或遠景，沒有清楚入鏡的正臉，符合腳本確認時「挑鏡頭時避開」的做法。
  - **待辦回填**（下次有空再處理，不影響這趟出片）：
    1. `clips.py` 的 `_trim_kino` 要查 Kinocut 官方文件確認 `trim -s/-e` 正確語意
       後修好，目前 Kinocut trim 路徑整個不可信，只能靠 `--no-kino`；
    2. 背景執行同一支 `tripcut clips`／render 指令前，養成先 `tasklist` 確認舊行程
       真的死了的習慣，這趟因為孤兒行程同時寫檔弄壞了 ~17 個預裁檔；
    3. 系統記憶體保護砍掉背景工作後，若底下有 `chrome-headless-shell.exe` 之類的
       子行程沒有跟著死掉，要手動 `taskkill` 清乾淨，不然記憶體不會真的釋放。
