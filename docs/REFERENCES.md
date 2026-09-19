# REFERENCES

## 執行／渲染
- Kinocut（FFmpeg MCP server，含品檢）— https://github.com/KyaniteLabs/kinocut ・ PyPI `kinocut`
- Remotion — https://www.remotion.dev/docs ・ 官方 Claude Code skill（見 `wilwaldon/Claude-Code-Video-Toolkit`）
- Remotion Ken Burns 單元件範例 — https://www.reactvideoeditor.com/remotion-templates/ken-burns
- JSON-props 驅動 Remotion 模板參考 — https://github.com/chrix911/maintain-video（讀 PLAYBOOK.md）
- Remotion 模板庫（1000 個，附 SKILL.md）— https://github.com/ali-abassi/remotion-templates
- 9:16 / 4:5 / 1:1 模板家族 — https://github.com/instavar/remotion-templates
- 純 ffmpeg Ken Burns slideshow（備援）— https://github.com/Trekky12/kburns-slideshow

## 分析
- faster-whisper — https://github.com/SYSTRAN/faster-whisper
- exiftool — https://exiftool.org
- ffmpeg scene detection：`select='gt(scene,0.3)'` + `showinfo`

## 現成回憶影片工具（先出片用／設計參考）
- immich-video-memory-generator（Trip 模式、Ken Burns、人臉感知平移）— https://github.com/sam-dumont/immich-video-memory-generator
- ClipForge（本機 montage、beat-sync、混照片影片）— https://github.com/Touka01/ClipForge

## 語音（可選）
- edge-tts — https://github.com/rany2/edge-tts
- Kokoro TTS（本機備援）— https://github.com/hexgrad/kokoro

## BGM（免費可商用音樂）

**Incompetech**（Kevin MacLeod）—— 目前唯一實測可以用指令自動抓的來源。

- 目錄：<https://incompetech.com/music/royalty-free/pieces.json>（1442 首，約 940 KB）
- 下載：`https://incompetech.com/music/royalty-free/mp3-royaltyfree/<filename>`
  —— `filename` 直接取自目錄的欄位（含空格，URL 要 encode，例如 `Sunshine%20A.mp3`）
- 授權：**CC BY 4.0**，發布時**必須附標註**，格式見下

目錄每筆的可用欄位（挑曲時拿來篩）：

| 欄位 | 說明 |
|---|---|
| `title` | 曲名 |
| `filename` | mp3 檔名，組下載網址用 |
| `bpm` | 節拍，字串 |
| `length` | `HH:MM:SS`，決定要不要循環 |
| `feel` | 逗號分隔，例如 `Bouncy, Bright, Calming, Uplifting` |
| `instruments` | 逗號分隔，例如 `Ukulele, Guitar, Marimba` |
| `genre` / `collection` | 數字代碼，不好用，建議用 `feel` + `instruments` 篩 |
| `description` | 一句話描述 |
| `isrc` / `uuid` / `itunes` / `video` | 識別碼與外部連結 |

`feel` 常見值：`Dark, Relaxed, Grooving, Mysterious, Bouncy, Intense, Driving,
Bright, Unnerving, Calming, Mystical, Somber, Uplifting, Eerie`。

**挑曲原則**見 `STYLE-TEMPLATE.md` §4：要**沒有強拍的器樂**（lo-fi / acoustic / 兒歌感）。
樣本兩支的 onset 自相關只有 0.10–0.14 且 60–190 BPM 全平坦——音樂是「床」不是「拍」。
有明顯鼓點的曲子會逼你卡拍剪輯，和這個模板衝突。

挑完要看原檔音量再決定 `bgm.volume`：實測 Carefree 原檔 mean -22.7 dB（用 volume 1.0）、
Sunshine ver 2 是 -13.8 dB（用 0.35–0.45）。差了 9 dB，直接套同一個數字會差很多。

**標註格式**（放影片說明或片尾，每首都要）：

```
"<曲名>" Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0 License
http://creativecommons.org/licenses/by/4.0/
```

每趟旅行把實際用到的曲子寫進 `projects/<trip>/CREDITS.md`（該檔不進 git，見 hard rule 3）。

### 試過但不能自動抓的

| 來源 | 狀況 |
|---|---|
| Pixabay Music | API 回 403，要 key |
| YouTube 音訊庫 | 要登入 Google 帳號，無法用指令抓 |

使用者想自己挑的話這兩個都可以手動下載，放進 `projects/<trip>/work/bgm/` 即可。

## 不採用但知道的
- Gemini 影片理解（免費層資料政策）、Mistral Pixtral（只讀圖）、Qwen video-edit plugin（綁 DashScope 付費）
