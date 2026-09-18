"""Stage 2 — frames：場景切換抽幀 / 等距抽幀，再拼成 contact sheet 供 Claude 讀圖。

規格見 docs/PIPELINE.md「Stage 2 — frames」。做法：

1. 只解 keyframe（`-skip_frame nokey`）跑 `select='gt(scene,T)'` 找場景切換點，
   比全解碼快很多（2.7K 檔案 keyframe 約每 0.5s 一張）。
2. 場景切換點少於 4 個 → 改等距：interval = max(3s, duration / max_frames)。
3. 候選點多於 max_frames → 均勻挑子集。
4. 每個時間點用 `-ss` 輸入端 seek 抽一張，長邊縮到 512px（ffmpeg 會自動套用旋轉）。
5. 檔名 `NNNN_SSSSS.SS.jpg`，另存 `index.json` 紀錄每張的秒數。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tripcut.common import find_tool, item_source_path, load_manifest, run, save_json
from tripcut.contact_sheet import build_photo_sheet, build_video_sheet

_PTS_RE = re.compile(r"pts_time:\s*([0-9.]+)")
_SCALE_LONG_EDGE = "scale='if(gt(iw,ih),{n},-2)':'if(gt(iw,ih),-2,{n})'"


def _scene_change_times(src: Path, threshold: float) -> list[float]:
    ffmpeg = find_tool("ffmpeg")
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-skip_frame",
        "nokey",
        "-i",
        str(src),
        "-an",
        "-vf",
        f"select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    ]
    res = run(cmd, check=False)
    times = [float(m.group(1)) for m in _PTS_RE.finditer(res.stderr)]
    return sorted(set(round(t, 2) for t in times))


def _evenly(values: list[float], n: int) -> list[float]:
    if len(values) <= n:
        return values
    step = (len(values) - 1) / (n - 1)
    return [values[round(i * step)] for i in range(n)]


def _equidistant(duration: float, n: int, min_interval: float = 3.0) -> list[float]:
    if duration <= 0:
        return [0.0]
    interval = max(min_interval, duration / n)
    times: list[float] = []
    t = interval / 2
    while t < duration and len(times) < n:
        times.append(round(t, 2))
        t += interval
    return times or [0.0]


def choose_times(
    src: Path, duration: float, max_frames: int, threshold: float, min_scene_hits: int = 4
) -> tuple[list[float], str]:
    """回傳 (時間點清單, 用了哪種策略)。"""
    scene = [t for t in _scene_change_times(src, threshold) if 0.3 < t < duration - 0.3]
    if len(scene) >= min_scene_hits:
        # 開頭一定要有一張，讓人知道影片怎麼開始
        if not scene or scene[0] > 2.0:
            scene = [0.5] + scene
        return _evenly(scene, max_frames), f"scene>{threshold} ({len(scene)} hits)"
    return _equidistant(duration, max_frames), "equidistant"


def _extract_frame(src: Path, t: float, dst: Path, long_edge: int = 512) -> None:
    ffmpeg = find_tool("ffmpeg")
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(src),
            "-frames:v",
            "1",
            "-vf",
            _SCALE_LONG_EDGE.format(n=long_edge),
            "-q:v",
            "3",
            str(dst),
        ]
    )


def _thumb_photo(src: Path, dst: Path, long_edge: int = 512) -> None:
    from PIL import Image, ImageOps

    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im) or im
        im = im.convert("RGB")
        im.thumbnail((long_edge, long_edge))
        im.save(dst, "JPEG", quality=88)


def run_frames(
    project_dir: Path,
    max_frames: int = 12,
    scene_threshold: float = 0.4,
    only_ids: set[str] | None = None,
    force: bool = False,
) -> Path:
    """依 manifest.json 對每支影片抽幀、每張照片縮圖，輸出 work/frames/ 與 work/contact/。

    Returns:
        contact sheet 所在目錄。
    """
    project_dir = project_dir.resolve()
    manifest = load_manifest(project_dir)
    frames_dir = project_dir / "work" / "frames"
    contact_dir = project_dir / "work" / "contact"
    contact_dir.mkdir(parents=True, exist_ok=True)

    photos: list[tuple[dict[str, Any], Path]] = []
    for item in manifest["items"]:
        if only_ids and item["id"] not in only_ids:
            continue
        src = item_source_path(project_dir, item)
        if item["type"] == "photo":
            dst = frames_dir / "photos" / f"{item['id']}.jpg"
            if force or not dst.exists():
                _thumb_photo(src, dst)
            photos.append((item, dst))
            continue

        vid_dir = frames_dir / item["id"]
        index_path = vid_dir / "index.json"
        if index_path.exists() and not force:
            print(f"[{item['id']}] 已有抽幀，跳過（--force 可重抽）")
        else:
            times, strategy = choose_times(
                src, float(item["duration"]), max_frames, scene_threshold
            )
            print(f"[{item['id']}] {item['filename']}  {strategy} → {len(times)} 張")
            if vid_dir.exists():
                for old in vid_dir.glob("*.jpg"):
                    old.unlink()
            entries: list[dict[str, Any]] = []
            for n, t in enumerate(times, start=1):
                name = f"{n:04d}_{t:08.2f}.jpg"
                _extract_frame(src, t, vid_dir / name)
                entries.append({"n": n, "t": t, "file": name})
            save_json(index_path, {"id": item["id"], "strategy": strategy, "frames": entries})
        build_video_sheet(project_dir, item, vid_dir, contact_dir)

    if photos and not only_ids:
        build_photo_sheet(project_dir, photos, contact_dir)
    elif photos:
        build_photo_sheet(project_dir, photos, contact_dir)
    return contact_dir
