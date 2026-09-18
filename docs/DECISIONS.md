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
