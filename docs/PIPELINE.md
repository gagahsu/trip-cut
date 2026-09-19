# PIPELINE — 四階段規格

所有階段以 `projects/<trip>/` 為工作目錄。時間一律用秒（float）。

---

## Stage 1 — ingest：`tripcut ingest <project>`

**輸入**：`raw/` 下所有照片（jpg/jpeg/png/heic）與影片（mp4/mov）。
**輸出**：`manifest.json`（符合 `schemas/manifest.schema.json`）。

做的事：
1. `exiftool -json -r -DateTimeOriginal -CreateDate -GPSLatitude -GPSLongitude -ImageWidth -ImageHeight -Duration raw/`
2. 影片再補 `ffprobe -v quiet -print_format json -show_format -show_streams`（取 duration、fps、是否有 audio stream、旋轉）。
3. 每個檔案給穩定 id：`p001`（photo）、`v001`（video），依拍攝時間排序。
4. HEIC → 轉 jpg 到 `work/converted/`（`heif-convert` 或 Pillow + pillow-heif），manifest 記錄 `converted_path`。

manifest 範例：
```json
{
  "project": "2026-10-okinawa",
  "generated_at": "2026-10-20T10:00:00+08:00",
  "items": [
    {"id": "p001", "type": "photo", "path": "raw/IMG_0001.HEIC", "converted_path": "work/converted/p001.jpg",
     "taken_at": "2026-10-12T09:14:03+09:00", "gps": [26.21, 127.68], "width": 4032, "height": 3024},
    {"id": "v001", "type": "video", "path": "raw/IMG_0002.MOV",
     "taken_at": "2026-10-12T09:20:11+09:00", "duration": 34.5, "fps": 29.97, "has_audio": true, "width": 1920, "height": 1080, "rotation": 90}
  ]
}
```

---

## Stage 2 — frames：`tripcut frames <project>`

**輸入**：manifest.json
**輸出**：`work/frames/<id>/NNNN_<sec>.jpg`、`work/contact/<id>.jpg`、`work/contact/ALL_photos.jpg`

影片抽幀（場景切換優先，等距補位）：
```bash
ffmpeg -i raw/IMG_0002.MOV -vf "select='gt(scene,0.3)',scale=512:-2,showinfo" -vsync vfr work/frames/v001/%04d.jpg 2> work/frames/v001/showinfo.log
```
- 從 `showinfo.log` 解析每張的 `pts_time`，重新命名成 `0001_00012.40.jpg`（秒數保留兩位）。
- 若場景切換少於 4 張 → 改每 3 秒等距抽一張。
- 每支影片上限 12 張（可用 `--max-frames` 覆寫）。

Contact sheet（Pillow）：
- 每列 4 張，每張下方寫 `v001 @ 12.40s`；整張 sheet 頂部寫檔名、拍攝時間、總長度。
- 照片：全部縮成 512px 長邊，每列 5 張，標 `p001 · 10/12 09:14`。
- 單張 sheet 不超過 2000px 寬、8 列；超過就分頁 `v001_1.jpg`、`v001_2.jpg`。

---

## Stage 3 — transcribe：`tripcut transcribe <project>`

只處理 `has_audio: true` 且音量不是純環境音的影片（先用 `ffmpeg -af volumedetect` 粗判，mean_volume < -40dB 跳過）。

```python
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cuda", compute_type="int8_float16")  # GPU 等級不高的設定
segments, info = model.transcribe(path, language="zh", vad_filter=True, word_timestamps=True)
```
- CUDA 失敗自動退 `device="cpu", compute_type="int8"`。
- 輸出 `work/transcript.json`：`{"v001": [{"start": 1.2, "end": 3.8, "text": "..."}]}`。
- 中文逐字時間碼精度有限，只用來讓 Claude 理解內容，不直接當字幕。

---

## Stage 4a — 腳本（情境 B 才有）

Claude 讀 `manifest.json`、`work/contact/*.jpg`、`work/transcript.json`，寫 `script.md` 草稿，格式：

```markdown
# 2026-10 沖繩 — 回憶影片腳本

- 目標長度：60s（9:16）
- 語氣：溫暖、家庭、慢節奏
- BGM：使用者提供（放 `work/bgm/`），或由 Claude 依腳本語氣從 Incompetech 挑並下載
  （來源、目錄欄位、下載網址、標註格式見 `REFERENCES.md`；挑曲原則見 `STYLE-TEMPLATE.md` §4）

## 段落
### 1. 抵達（0–8s）
- 素材候選：p001, p003, v001@0–4s
- 字卡：「Day 1 · 那霸」
- 備註：v001 開頭有人聲「到了到了」，可保留原音

### 2. 海邊（8–25s）
...
```

**寫完停下來**，回報：「script.md 草稿完成，請確認或修改後告訴我」。不進 Stage 4b。

## Stage 4b — EDL

Claude 依定案的 `script.md` 產 `edl.json`（符合 `schemas/edl.schema.json`）：

```json
{
  "project": "2026-10-okinawa",
  "output": {"aspect": "9:16", "fps": 30, "target_duration": 60},
  "bgm": {"path": "raw/bgm.mp3", "volume": 0.6, "duck_under_speech": true},
  "clips": [
    {"seq": 1, "source": "p001", "start": 0, "duration": 2.5, "effect": "kenburns", "kenburns": {"from": [0.5,0.5,1.0], "to": [0.55,0.45,1.15]}, "transition_out": "crossfade"},
    {"seq": 2, "source": "v001", "in": 0.0, "out": 4.0, "keep_audio": true, "crop": "center", "transition_out": "cut"},
    {"seq": 3, "source": "p003", "start": 0, "duration": 2.0, "effect": "kenburns", "title": {"text": "Day 1 · 那霸", "style": "lower-third"}}
  ]
}
```

`tripcut edl-validate`：
- schema 驗證；`source` 必須存在於 manifest；影片 `in/out` 不越界；總長度與 `target_duration` 差距 > 15% 要警告。
- 直式輸出時，橫向影片必須指定 `crop`（center / left / right / 0..1 的 x 座標）。

`tripcut props`：把 EDL 轉成 Remotion 的 `props.json`（秒 → frame）。時間軸在這裡就算好：每段有 `startFrame`，crossfade 讓下一段提早 0.5s 開始並淡入。用到的檔案會 hard link 到 `work/public/{clips,photos,raw,bgm}/`，props 的 src 相對於它；render 時 `--public-dir=<專案>/work/public`（Remotion 的 bundler 會整個複製 public dir、也不能跨 junction，所以不能直接指專案目錄）。

同一專案可以有多個版本：`--edl edl-120.json` → `props-120.json`。

EDL 額外欄位 `audio_override: {source, in}`：畫面用這段、聲音用另一段（例如小孩視角的畫面配上大人的對話）。

`tripcut clips`：把 EDL 裡的影片段落用 Kinocut 預裁成 `work/clips/<id>_<in>-<out>.mp4`（旋轉烤進畫面、長邊 1920），Remotion 只吃預裁檔；`audio_override` 也裁成同長度的小檔。要在 `tripcut props` 之前跑，props 才會指向預裁檔。

---

## Stage 5 — 渲染與後製

**Remotion（主）**
```powershell
cd remotion
npx remotion render Montage ..\projects\<trip>\out\<trip>-9x16.mp4 --props=..\projects\<trip>\props.json --public-dir=..\projects\<trip>\work\public
# 16:9 用同一份 props：composition 改成 Montage16x9
```
Composition 的尺寸／長度／fps 都由 props 的 `calculateMetadata` 決定；`Montage16x9` 只是把同一份 props 硬轉 1920x1080（影片 cover crop、照片 Ken Burns 自動重算）。

**kburns-slideshow（備援，Phase 1）**：只吃照片＋簡單順序，用來早期驗證流程。

**Kinocut MCP（後製）**：
- 影片段落預先裁切成 `work/clips/`（避免 Remotion 直接吃 4K 原檔）。
- 成品品檢：時長、解析度、有無黑幀、音量。
- 另出 16:9 版本時用 Kinocut 轉檔而非重跑 Remotion（若 props 允許）。

---

## 分析用 ffmpeg 白名單

Claude 可直接下的 raw ffmpeg 僅限：抽幀（`select`/`fps`）、`volumedetect`、`ffprobe`、縮圖。其餘剪輯操作走 Kinocut。

## Stage 6 — 收尾（`tripcut finish`）

```
tripcut finish projects/<trip>/out/<trip>-9x16.mp4
```

Remotion 出的是母帶，不能直接上傳。這一步做 `docs/STYLE-TEMPLATE.md` §1 要求的兩件事：

1. **響度正規化到 -14 LUFS / -1 dBTP**（兩趟 loudnorm，第一趟量測、第二趟套 `measured_*`）。
   母帶通常是 -19 ～ -20 LUFS；IG／TikTok 會自己拉到 -14 附近，但拉的過程不受我們控制。
2. **寫入 bt709 三件套**（primaries / transfer / matrix），否則播放器要自己猜色彩空間。

順便把位元率從母帶的 CRF 20（約 30 Mbps）降到 CRF 22（約 18 Mbps）。
產出 `<母帶>-share.mp4`，並印出品檢數字（長度／LUFS／LRA／true peak／色彩 tag）。

`--crf`、`--lufs`、`--out` 可調。品檢數字也可以自己呼叫 `tripcut.finish.verify()` 取得。
