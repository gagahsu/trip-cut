"""Stage 6：收尾。把 Remotion 出的母帶轉成可以直接上傳的交付檔。

做兩件 Remotion 不做、但 docs/STYLE-TEMPLATE.md §1 要求的事：

1. **響度正規化到 -14 LUFS / -1 dBTP**。IG 與 TikTok 都會把上傳的影片 normalize 到
   -14 LUFS 附近；母帶通常落在 -19 ～ -20 LUFS，直接上傳會被平台拉高，拉的過程
   不受我們控制。先自己做完，成品聽起來才跟樣本一致。
   走兩趟 loudnorm（第一趟量測、第二趟套用 measured_*），單趟的動態模式會飄。

2. **明確寫入 bt709 三件套**（primaries / transfer / matrix）。沒有 tag 的話播放器
   要自己猜色彩空間，在不同裝置上顏色會不一樣。

順便把位元率降到合理範圍（母帶 CRF 20 約 30 Mbps，交付檔 CRF 22 約 18 Mbps）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tripcut.common import find_tool, run

TARGET_LUFS = -14.0
TARGET_TP = -1.0
TARGET_LRA = 11.0
SHARE_CRF = 22
SHARE_PRESET = "medium"
AUDIO_BITRATE = "160k"


def _measure_loudness(src: Path) -> dict[str, Any]:
    """第一趟 loudnorm：量出 input_i / input_tp / input_lra / input_thresh。"""
    ffmpeg = find_tool("ffmpeg")
    res = run(
        [
            ffmpeg, "-hide_banner", "-nostdin", "-i", str(src),
            "-af",
            f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
            "-f", "null", "-",
        ],
        check=True,
    )  # fmt: skip
    text = (res.stderr or "") + (res.stdout or "")
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", text, re.S)
    if not match:
        raise RuntimeError("loudnorm 第一趟沒有吐出 JSON，無法正規化")
    return json.loads(match.group(0))


def finish(
    src: Path,
    dst: Path | None = None,
    crf: int = SHARE_CRF,
    lufs: float = TARGET_LUFS,
) -> Path:
    """母帶 → 交付檔（正規化響度、寫入 bt709、重新編碼）。

    Returns:
        產出的檔案路徑。預設是母帶同目錄的 `<stem>-share.mp4`。
    """
    src = src.resolve()
    if not src.exists():
        raise FileNotFoundError(f"{src} 不存在")
    out = (dst or src.with_name(f"{src.stem}-share.mp4")).resolve()
    if out == src:
        raise ValueError("輸出不能覆蓋母帶")

    m = _measure_loudness(src)
    norm = (
        f"loudnorm=I={lufs}:TP={TARGET_TP}:LRA={TARGET_LRA}"
        f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
        f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
        f":offset={m.get('target_offset', 0)}:linear=true"
    )
    ffmpeg = find_tool("ffmpeg")
    run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(src),
            "-af", f"{norm},aresample=48000",
            "-c:v", "libx264", "-preset", SHARE_PRESET, "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(out),
        ],
        check=True,
    )  # fmt: skip
    return out


def verify(path: Path) -> dict[str, Any]:
    """量成品的響度與色彩 tag，給品檢用。"""
    ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
    res = run(
        [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path), "-af", "ebur128=peak=true",
         "-f", "null", "-"],
        check=True,
    )  # fmt: skip
    text = (res.stderr or "") + (res.stdout or "")
    # ebur128 一路印逐幀讀數，最後才印 Summary；只認 Summary 之後的數字，
    # 否則 re.search 會抓到開頭那個 -70 LUFS 的暖機值。
    summary = text.rsplit("Summary:", 1)[-1] if "Summary:" in text else ""

    def grab(label: str) -> float | None:
        m = re.search(rf"^\s*{label}:\s*(-?\d+\.?\d*)", summary, re.M)
        return float(m.group(1)) if m else None

    probe = run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=color_primaries,color_transfer,color_space",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True,
    )  # fmt: skip
    info = json.loads(probe.stdout or "{}")
    stream = (info.get("streams") or [{}])[0]
    return {
        "duration": float(info.get("format", {}).get("duration", 0.0)),
        "lufs": grab("I"),
        "lra": grab("LRA"),
        "true_peak": grab("Peak"),
        "color": "/".join(
            str(stream.get(k, "?"))
            for k in ("color_primaries", "color_transfer", "color_space")
        ),
    }
