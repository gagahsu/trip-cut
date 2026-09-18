# ARCHITECTURE

## 資料流

```
raw/ (照片/影片)
   │  ingest：exiftool + ffprobe
   ▼
manifest.json ──────────────────────────────┐
   │  frames：場景切換抽幀 / 等距抽幀        │
   ▼                                        │
work/frames/*.jpg ──► contact_sheet.jpg      │
   │  transcribe：faster-whisper（僅有人聲片段）
   ▼                                        │
work/transcript.json                        │
   │                                        │
   ▼  Claude Code 讀：contact sheet + transcript + manifest + (script.md)
script.md（情境 B 產草稿 → 使用者定案）
   │
   ▼  Claude Code 依腳本產生
edl.json ──► tripcut edl-validate ──► props.json
   │                                    │
   │ Kinocut MCP（裁切/合併/轉檔/品檢）    │ Remotion render（Ken Burns、轉場、字卡、BGM）
   ▼                                    ▼
out/<trip>-9x16.mp4  /  out/<trip>-16x9.mp4
```

## 分層

| 層 | 負責 | 技術 |
|---|---|---|
| 分析 | 把媒體變成 Claude 能讀的文字＋圖片 | ffmpeg/ffprobe、exiftool、faster-whisper、Pillow |
| 決策 | 腳本、選片、順序、時長、字卡文案 | Claude Code（人在迴圈確認腳本） |
| 執行 | 素材裁切、合併、格式轉換、品質檢查 | Kinocut MCP |
| 渲染 | 動態效果、轉場、字卡、混音 | Remotion（主）／kburns-slideshow（備援） |

## 為什麼分析層要「壓成文字＋contact sheet」

Claude 不能直接讀影片檔，只能讀圖片。所以：
- 每支影片依場景切換抽幀（`scene > 0.3`），再限制每支最多 N 張，避免 context 爆掉。
- 抽幀拼成 contact sheet（每張圖上標 `影片id@秒數`），一張圖就能讓 Claude 掃過一整支影片。
- 照片直接縮圖成 512px 長邊，同樣拼 contact sheet。
- 有人聲的影片用 Whisper 轉逐字稿，Claude 才知道「這段在講什麼」。

## 兩種渲染路線

- **Remotion（主線）**：`Montage.tsx` 只吃 `props.json`。換旅行＝換 props，不動 composition。
- **kburns-slideshow（備援）**：Phase 1 就能出片，用來驗證 EDL 與腳本流程；Remotion 就緒後退居備援。

## 不做的事

- 不做 AI 生成畫面（Veo/Sora 等）。
- 不做雲端渲染、不做自動上傳社群。
- 不做人臉辨識／人物標籤（隱私考量，未來若要做也只在本機）。
