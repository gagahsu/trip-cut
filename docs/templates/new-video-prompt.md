# 開一支新影片的 prompt

複製下面那塊，把 `<>` 填掉，貼給 Claude Code（在 repo 根目錄開）。

---

```
我要做一支新的旅遊回憶影片。

專案名：<2026-10-okinawa>
地點：<沖繩（那霸、美麗海水族館、古宇利島）>
日期：<2026-10-05 ~ 10-07>
素材：已經放在 projects/<2026-10-okinawa>/raw/
要幾版：<60s（IG Reels）＋ 120s（家人完整版）>
語氣：<family>          # family=家庭 vlog／碎念體，guide=攻略／推薦體
調色：<warm>            # warm=城市/室內/美食/陰雨森林，cool=雪地/海/清晨，
                        #   fresh=晴天草地/公園/溪邊；可分段覆寫
片中人物怎麼稱呼：<小孩叫奈奈（妹妹）、達達（哥哥）>   # 不想出現名字就寫「不要出現名字」

先讀 CLAUDE.md，再讀 docs/STYLE-TEMPLATE.md（剪輯規則、字幕、音樂、色調）
和 docs/templates/edl-style.example.json（EDL 欄位怎麼寫）。

照 CLAUDE.md §5 的流程走。寫完 script.md 草稿停下來等我確認，
確認後再往下做到成品。
```

---

## 這支 prompt 會讓它做什麼

| 階段 | 指令 | 產物 |
|---|---|---|
| 1 | `tripcut ingest` | `manifest.json` |
| 2 | `tripcut frames` | `work/frames/`、`work/contact/` |
| 3 | `tripcut transcribe` | `work/transcript.json` |
| — | Claude 看 contact sheet + 逐字稿 | **`script.md` 草稿 → 停下來等你確認** |
| 4 | Claude 依 script.md 寫 EDL | `edl-style.json` |
| 4b | `tripcut edl-validate` | 檢查時間碼不越界 |
| 5 | `tripcut clips` | `work/clips/` 預裁檔 |
| 4b | `tripcut props` | `props-style.json` |
| 6 | `npx remotion render` | `out/<trip>-9x16.mp4` 母帶 |
| 6 | `tripcut finish` | `out/<trip>-9x16-share.mp4` 交付檔 |

停一次是 hard rule 4，不會自己衝到底。

## 需要提醒它的話（通常不用，規則都在文件裡）

如果它開始偏離模板，這幾句可以直接貼：

- 「全片硬切，不要用 crossfade 或 fade-black」
- 「剪點用 RMS 包絡量過再寫，不要直接信 Whisper 的段落時間碼」
- 「字幕文案自己當中文讀過一遍，Whisper 常誤聽」
- 「章節標和主字幕不要講同一件事，重複就只留一個」
- 「照片要靜止＋拍立得外框，不要 Ken Burns」
- 「BGM 挑沒有強拍的器樂，來源看 docs/REFERENCES.md」

## 常見的追加需求

```
改長度      「改成 90 秒」→ 改 edl 重跑 props + render，不用重新預裁
改某一句    「seq12 的字幕改成 xxx」→ 同上
換 BGM      「換一首更輕快的」→ 從 Incompetech 重挑，注意原檔音量差很多
加彩蛋      「片尾加一段 <某支影片> 的 xx 秒」
16:9 版     用同一份 props 換 composition（Montage16x9）
```

## 素材先準備好

```powershell
mkdir projects\<2026-10-okinawa>\raw
# 把照片影片丟進去（不用改檔名，manifest 會給 id）
```

素材很大又不想複製的話，`raw/` 可以做成指向原資料夾的 junction：

```powershell
cmd /c mklink /J projects\<2026-10-okinawa>\raw "D:\照片\沖繩"
```

## 會需要你決定的事

Claude 在 `script.md` 草稿階段會問，先想一下：

1. 小孩／家人在字幕裡怎麼稱呼，或是完全不出現名字
2. 有沒有一定要留的橋段（某句對話、某個畫面）
3. 有沒有一定要剪掉的（拍到別人的臉、講到不想公開的事）
4. 要不要保留現場原音（預設要，家庭 vlog 靠這個）
5. 要幾版、各幾秒
