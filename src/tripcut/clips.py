"""預裁：把 EDL 裡每段影片先裁成獨立的 1080p 檔（work/clips/），Remotion 只吃預裁檔。

理由（docs/TASKS.md Phase 3）：原檔是 2.7K 56Mbps、又帶旋轉 metadata，
Remotion 逐格 seek 會非常慢；預裁成短檔、把旋轉烤進畫面、長邊縮到 1920，render 才跑得動。

剪輯執行走 Kinocut（ADR-002）：`kino trim` 裁時間（會把旋轉烤進畫面）、`kino resize` 縮尺寸。
若 Kinocut 不可用，退回本專案固定參數的 ffmpeg 一次 encode（hard rule 6 允許的專案內腳本）。
audio_override 的聲音也用 `kino trim` 裁成同長度的小檔，Remotion 只取它的聲音。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from tripcut.common import find_tool, load_manifest, run
from tripcut.edl import audio_file, clip_duration, clip_file, effective_size, load_edl

LONG_EDGE = 1920


def _kino_cmd() -> list[str] | None:
    if shutil.which("kino"):
        return ["kino"]
    if shutil.which("uvx"):
        return ["uvx", "--from", "kinocut", "kino"]
    return None


def _target_size(item: dict[str, Any]) -> tuple[int, int]:
    w, h = effective_size(item)
    if w >= h:
        return LONG_EDGE, round(LONG_EDGE * h / w / 2) * 2
    return round(LONG_EDGE * w / h / 2) * 2, LONG_EDGE


def _precut_ffmpeg(src: Path, dst: Path, start: float, end: float, size: tuple[int, int]) -> None:
    """專案內固定參數：精準裁切 + 烤旋轉 + 縮放 + 重新編碼（單次 encode）。"""
    ffmpeg = find_tool("ffmpeg")
    w, h = size
    run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
            "-vf", f"scale={w}:{h}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
            "-movflags", "+faststart", str(dst),
        ]
    )  # fmt: skip


def _trim_kino(kino: list[str], src: Path, dst: Path, start: float, end: float) -> None:
    run([*kino, "trim", "-s", f"{start:.3f}", "-e", f"{end:.3f}", "-o", str(dst), str(src)])


def _precut_kino(
    kino: list[str], src: Path, dst: Path, start: float, end: float, size: tuple[int, int]
) -> None:
    tmp = dst.with_name(dst.stem + ".trim.mp4")
    _trim_kino(kino, src, tmp, start, end)
    w, h = size
    run([*kino, "resize", "-w", str(w), "--height", str(h), "-q", "high", "-o", str(dst), str(tmp)])
    tmp.unlink(missing_ok=True)


def run_clips(
    project_dir: Path,
    edl_name: str = "edl.json",
    force: bool = False,
    use_kino: bool = True,
) -> list[Path]:
    project_dir = project_dir.resolve()
    edl = load_edl(project_dir, edl_name)
    items = {it["id"]: it for it in load_manifest(project_dir)["items"]}
    kino = _kino_cmd() if use_kino else None
    outputs: list[Path] = []
    for clip in sorted(edl["clips"], key=lambda c: int(c["seq"])):
        item = items[clip["source"]]
        if item["type"] == "video":
            dst = clip_file(project_dir, clip)
            outputs.append(dst)
            if dst.exists() and not force:
                print(f"[{clip['seq']:03d}] {dst.name} 已存在，跳過")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                src = project_dir / item["path"]
                start, end = float(clip["in"]), float(clip["out"])
                size = _target_size(item)
                label = f"[{clip['seq']:03d}] {dst.name} → {size[0]}x{size[1]}"
                done = False
                if kino:
                    try:
                        _precut_kino(kino, src, dst, start, end, size)
                        print(f"{label}  (kino)")
                        done = True
                    except RuntimeError as e:
                        print(f"{label}  kino 失敗，改用專案 ffmpeg：{str(e)[:120]}")
                if not done:
                    _precut_ffmpeg(src, dst, start, end, size)
                    print(f"{label}  (ffmpeg)")

        ao = clip.get("audio_override")
        if ao:
            adst = audio_file(project_dir, clip)
            outputs.append(adst)
            if adst.exists() and not force:
                print(f"[{clip['seq']:03d}] {adst.name} 已存在，跳過")
                continue
            adst.parent.mkdir(parents=True, exist_ok=True)
            asrc = project_dir / items[ao["source"]]["path"]
            a0 = float(ao["in"])
            a1 = a0 + clip_duration(clip)
            if kino:
                try:
                    _trim_kino(kino, asrc, adst, a0, a1)
                    print(f"[{clip['seq']:03d}] {adst.name}  (kino, audio)")
                    continue
                except RuntimeError as e:
                    print(f"[{clip['seq']:03d}] audio kino 失敗，改用 ffmpeg：{str(e)[:120]}")
            _precut_ffmpeg(asrc, adst, a0, a1, (426, 240))
            print(f"[{clip['seq']:03d}] {adst.name}  (ffmpeg, audio)")
    return outputs
