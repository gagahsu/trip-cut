"""Stage 1 — ingest：掃描 raw/，跑 exiftool + ffprobe，產出 manifest.json。

規格見 docs/PIPELINE.md「Stage 1 — ingest」。

拍攝時間的來源優先序：
- 照片：EXIF DateTimeOriginal（本地時間）→ 檔名裡的 YYYYMMDD_HHMMSS → 檔案 mtime
- 影片：檔名裡的 YYYYMMDD_HHMMSS（相機寫的是本地時間）
  → QuickTime CreateDate（UTC，加上 --tz 位移）→ 檔案 mtime
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from tripcut.common import (
    PHOTO_EXTS,
    VIDEO_EXTS,
    find_tool,
    load_json,
    run,
    save_json,
)

_FILENAME_TS = re.compile(r"(20\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})")


def _scan_raw(raw_dir: Path) -> list[Path]:
    files: list[Path] = []
    for p in sorted(raw_dir.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.suffix.lower() in PHOTO_EXTS | VIDEO_EXTS:
            files.append(p)
    return files


def _exiftool_all(raw_dir: Path) -> dict[str, dict[str, Any]]:
    """一次跑 exiftool -r，回傳 {絕對路徑(小寫、正斜線): tags}。"""
    exiftool = find_tool("exiftool")
    cmd = [
        exiftool,
        "-json",
        "-r",
        "-n",
        "-charset",
        "filename=utf8",
        "-DateTimeOriginal",
        "-CreateDate",
        "-GPSLatitude",
        "-GPSLongitude",
        "-ImageWidth",
        "-ImageHeight",
        "-Duration",
        "-Rotation",
        "-Model",
        "-Orientation",
        "-SourceFile",
        str(raw_dir),
    ]
    res = run(cmd, check=False)
    if not res.stdout.strip():
        raise RuntimeError("exiftool 沒有輸出：\n" + res.stderr[-800:])
    rows = json.loads(res.stdout)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = Path(row["SourceFile"]).resolve().as_posix().lower()
        out[key] = row
    return out


def _ffprobe(path: Path) -> dict[str, Any]:
    ffprobe = find_tool("ffprobe")
    res = run(
        [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    return json.loads(res.stdout)


def _parse_exif_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (
        "%Y:%m:%d %H:%M:%S%z",
        "%Y:%m:%d %H:%M:%S.%f%z",
        "%Y:%m:%d %H:%M:%S",
        "%Y:%m:%d %H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _filename_dt(path: Path) -> datetime | None:
    m = _FILENAME_TS.search(path.stem)
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) for x in m.groups())
    try:
        return datetime(y, mo, d, h, mi, s)
    except ValueError:
        return None


def _taken_at(path: Path, tags: dict[str, Any], kind: str, tz: timezone) -> datetime:
    """回傳帶時區的本地拍攝時間。"""
    if kind == "photo":
        dt = _parse_exif_dt(tags.get("DateTimeOriginal")) or _filename_dt(path)
        if dt is None:
            dt = _parse_exif_dt(tags.get("CreateDate"))
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=tz)
    else:
        dt = _filename_dt(path)
        if dt is not None:
            return dt.replace(tzinfo=tz)
        dt = _parse_exif_dt(tags.get("CreateDate"))
        if dt is not None:
            # QuickTime CreateDate 依規格是 UTC
            return dt.replace(tzinfo=UTC).astimezone(tz) if dt.tzinfo is None else dt
    return datetime.fromtimestamp(path.stat().st_mtime, tz=tz)


def _video_info(path: Path) -> dict[str, Any]:
    info = _ffprobe(path)
    vstream = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    if vstream is None:
        raise RuntimeError(f"{path} 沒有影像串流")
    has_audio = any(s.get("codec_type") == "audio" for s in info["streams"])
    fps = float(Fraction(vstream.get("r_frame_rate", "30/1")))
    duration = float(info["format"].get("duration") or vstream.get("duration") or 0.0)
    rotation = 0
    for sd in vstream.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    if rotation == 0 and "rotate" in (vstream.get("tags") or {}):
        rotation = int(vstream["tags"]["rotate"])
    rotation = rotation % 360
    return {
        "duration": round(duration, 3),
        "fps": round(fps, 3),
        "has_audio": has_audio,
        "width": int(vstream["width"]),
        "height": int(vstream["height"]),
        "rotation": rotation,
        "codec": vstream.get("codec_name"),
    }


def _convert_heic(src: Path, dst: Path) -> tuple[int, int]:
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()  # pyright: ignore[reportPrivateImportUsage]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.save(dst, "JPEG", quality=92)
        return im.size


def run_ingest(project_dir: Path, tz_hours: float = 8.0) -> Path:
    """掃描 `project_dir/raw/`，寫出 `project_dir/manifest.json`。

    Returns:
        產出的 manifest.json 路徑。
    """
    project_dir = project_dir.resolve()
    raw_dir = project_dir / "raw"
    if not raw_dir.exists():
        raise FileNotFoundError(f"{raw_dir} 不存在")
    tz = timezone(timedelta(hours=tz_hours))

    files = _scan_raw(raw_dir)
    if not files:
        raise RuntimeError(f"{raw_dir} 底下沒有照片或影片")
    tags_by_path = _exiftool_all(raw_dir)

    records: list[tuple[datetime, Path, dict[str, Any]]] = []
    for f in files:
        kind = "photo" if f.suffix.lower() in PHOTO_EXTS else "video"
        tags = tags_by_path.get(f.resolve().as_posix().lower(), {})
        taken = _taken_at(f, tags, kind, tz)
        rel = f.relative_to(project_dir).as_posix()
        folder = f.parent.relative_to(raw_dir).as_posix()
        rec: dict[str, Any] = {
            "type": kind,
            "path": rel,
            "filename": f.name,
            "folder": "" if folder == "." else folder,
            "taken_at": taken.isoformat(),
            "size_mb": round(f.stat().st_size / 1_048_576, 1),
        }
        lat, lon = tags.get("GPSLatitude"), tags.get("GPSLongitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and (lat or lon):
            rec["gps"] = [round(float(lat), 6), round(float(lon), 6)]
        if tags.get("Model"):
            rec["camera"] = tags["Model"]

        if kind == "video":
            rec.update(_video_info(f))
        else:
            rec["width"] = int(tags.get("ImageWidth") or 0)
            rec["height"] = int(tags.get("ImageHeight") or 0)
            orient = tags.get("Orientation")
            if isinstance(orient, int) and orient in (5, 6, 7, 8):
                rec["rotation"] = 90
        records.append((taken, f, rec))

    # 依拍攝時間排序後給 id（照片 p001…、影片 v001…）
    records.sort(key=lambda r: (r[0], r[1].name))
    items: list[dict[str, Any]] = []
    pc = vc = 0
    for _taken, f, rec in records:
        if rec["type"] == "photo":
            pc += 1
            rec["id"] = f"p{pc:03d}"
            if f.suffix.lower() in {".heic", ".heif"}:
                dst = project_dir / "work" / "converted" / f"{rec['id']}.jpg"
                w, h = _convert_heic(f, dst)
                rec["converted_path"] = dst.relative_to(project_dir).as_posix()
                rec["width"], rec["height"] = w, h
        else:
            vc += 1
            rec["id"] = f"v{vc:03d}"
        # id 放最前面比較好讀
        items.append({"id": rec.pop("id"), **rec})

    manifest = {
        "project": project_dir.name,
        "generated_at": datetime.now(tz).isoformat(timespec="seconds"),
        "items": items,
    }
    _validate(manifest, project_dir)
    out = project_dir / "manifest.json"
    save_json(out, manifest)
    return out


def _validate(manifest: dict[str, Any], project_dir: Path) -> None:
    import jsonschema

    schema_path = _repo_root() / "schemas" / "manifest.schema.json"
    if schema_path.exists():
        jsonschema.validate(manifest, load_json(schema_path))


def _repo_root() -> Path:
    # src/tripcut/ingest.py → repo 根目錄
    return Path(__file__).resolve().parents[2]


def summarize(manifest: dict[str, Any]) -> str:
    items = manifest["items"]
    photos = [i for i in items if i["type"] == "photo"]
    videos = [i for i in items if i["type"] == "video"]
    total = sum(v.get("duration", 0.0) for v in videos)
    lines = [
        f"{manifest['project']}：{len(photos)} 張照片、{len(videos)} 支影片"
        f"（總長 {total / 60:.1f} 分鐘）",
    ]
    for v in videos:
        lines.append(
            f"  {v['id']}  {v['taken_at'][11:16]}  {v['duration']:7.1f}s  "
            f"{v['width']}x{v['height']} rot{v.get('rotation', 0):<3} "
            f"{'audio' if v.get('has_audio') else 'mute '}  {v['path']}"
        )
    return "\n".join(lines)
