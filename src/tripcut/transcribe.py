"""Stage 3 — transcribe：faster-whisper 產逐字稿，CUDA 失敗自動退 CPU。

規格見 docs/PIPELINE.md「Stage 3 — transcribe」：
- 只處理 has_audio 的影片；先用 `volumedetect` 粗判，mean_volume < -40 dB 視為純環境音跳過。
- 先把音軌抽成 16kHz 單聲道 wav（work/audio/<id>.wav），Whisper 不用去解 2.7K 影像。
- 輸出 work/transcript.json：{"v001": [{"start", "end", "text"}, …]}
- 另存 work/transcript_meta.json：每支的音量、裝置、跳過原因。
- 用 initial_prompt 引導 Whisper 輸出繁體中文（否則預設常出簡體）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tripcut.common import find_tool, load_json, load_manifest, run, save_json

_MEAN_RE = re.compile(r"mean_volume:\s*(-?[0-9.]+) dB")
_MAX_RE = re.compile(r"max_volume:\s*(-?[0-9.]+) dB")
SILENCE_DB = -40.0
INITIAL_PROMPT = "以下是一家人出遊時的對話，使用繁體中文，台灣口音。"


def _volume(src: Path) -> tuple[float, float]:
    ffmpeg = find_tool("ffmpeg")
    res = run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(src),
            "-vn",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        check=False,
    )
    mean = _MEAN_RE.search(res.stderr)
    mx = _MAX_RE.search(res.stderr)
    return (float(mean.group(1)) if mean else -99.0, float(mx.group(1)) if mx else -99.0)


def _extract_wav(src: Path, dst: Path) -> None:
    ffmpeg = find_tool("ffmpeg")
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ]
    )


def _load_model(model_size: str) -> tuple[Any, str]:
    from faster_whisper import WhisperModel

    try:
        model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
        return model, "cuda/int8_float16"
    except Exception as e:  # noqa: BLE001 — 任何 CUDA 問題都退 CPU
        print(f"CUDA 不可用（{type(e).__name__}: {str(e)[:80]}），改用 CPU int8")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        return model, "cpu/int8"


def run_transcribe(
    project_dir: Path,
    model_size: str = "small",
    only_ids: set[str] | None = None,
    force: bool = False,
    silence_db: float = SILENCE_DB,
) -> Path:
    """對有人聲的影片跑 faster-whisper，輸出 work/transcript.json。"""
    project_dir = project_dir.resolve()
    manifest = load_manifest(project_dir)
    work = project_dir / "work"
    out_path = work / "transcript.json"
    meta_path = work / "transcript_meta.json"
    transcript: dict[str, Any] = load_json(out_path) if out_path.exists() else {}
    meta: dict[str, Any] = load_json(meta_path) if meta_path.exists() else {}

    todo = [
        it
        for it in manifest["items"]
        if it["type"] == "video"
        and it.get("has_audio")
        and (not only_ids or it["id"] in only_ids)
        and (force or it["id"] not in meta)
    ]
    if not todo:
        print("沒有需要處理的影片（都做過了？用 --force 重跑）")
        return out_path

    model: Any = None
    device = ""
    for item in todo:
        vid = item["id"]
        src = project_dir / item["path"]
        mean_db, max_db = _volume(src)
        m: dict[str, Any] = {"mean_db": mean_db, "max_db": max_db, "duration": item["duration"]}
        if mean_db < silence_db:
            m["skipped"] = f"mean_volume {mean_db} dB < {silence_db}，視為純環境音"
            print(f"[{vid}] 跳過：{m['skipped']}")
            meta[vid] = m
            transcript.pop(vid, None)
            save_json(meta_path, meta)
            continue

        if model is None:
            model, device = _load_model(model_size)
        wav = work / "audio" / f"{vid}.wav"
        if force or not wav.exists():
            _extract_wav(src, wav)
        print(f"[{vid}] 轉逐字稿 {item['duration']:.0f}s（{device}）…", end="", flush=True)
        segments, info = model.transcribe(
            str(wav),
            language="zh",
            vad_filter=True,
            beam_size=5,
            initial_prompt=INITIAL_PROMPT,
            condition_on_previous_text=False,
        )
        segs = [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments
            if s.text.strip()
        ]
        transcript[vid] = segs
        m.update(
            {
                "device": device,
                "model": model_size,
                "segments": len(segs),
                "language_prob": round(float(info.language_probability), 3),
            }
        )
        meta[vid] = m
        print(f" {len(segs)} 段")
        save_json(out_path, transcript)
        save_json(meta_path, meta)

    # transcript.json 只放 id → segments，依 id 排序方便讀
    save_json(out_path, dict(sorted(transcript.items())))
    return out_path
