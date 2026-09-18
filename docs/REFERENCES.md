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

## 不採用但知道的
- Gemini 影片理解（免費層資料政策）、Mistral Pixtral（只讀圖）、Qwen video-edit plugin（綁 DashScope 付費）
