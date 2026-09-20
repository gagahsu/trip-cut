"""Stage 4b：驗證 edl.json、轉成 Remotion props.json。

規格見 docs/PIPELINE.md「Stage 4b — EDL」。

props.json 的時間軸在這裡就算好（frame 為單位），Remotion 只負責照 startFrame 擺 <Sequence>：
- 每段 `durationInFrames`；crossfade 會讓下一段提早 `overlapFrames` 開始，下一段淡入。
- 影片段落若 `work/clips/` 有預裁檔（`tripcut clips`），props 就指向預裁檔且 `inFrame` 從 0 起算。
- 所有用到的檔案 hard link 到 `work/public/`，props 的 src 相對於它；
  render 時 `--public-dir=<專案>/work/public`。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from tripcut.common import item_source_path, load_json, load_manifest, save_json

CROSSFADE_SEC = 0.5
FADE_BLACK_SEC = 0.6
DURATION_TOLERANCE = 0.15
ASPECT_SIZE = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
CROP_X = {"center": 0.5, "left": 0.2, "right": 0.8}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_edl(project_dir: Path, edl_name: str = "edl.json") -> dict[str, Any]:
    path = project_dir / edl_name
    if not path.exists():
        raise FileNotFoundError(f"{path} 不存在")
    return load_json(path)


def effective_size(item: dict[str, Any]) -> tuple[int, int]:
    """套用旋轉後的寬高（直式影片 rot 90/270 → 寬高互換）。"""
    w, h = int(item["width"]), int(item["height"])
    if int(item.get("rotation", 0)) in (90, 270):
        return h, w
    return w, h


def clip_duration(clip: dict[str, Any]) -> float:
    if "duration" in clip:
        return float(clip["duration"])
    return float(clip["out"]) - float(clip["in"])


def validate_edl(project_dir: Path, edl_name: str = "edl.json") -> list[str]:
    """對 schemas/edl.schema.json 驗證 edl.json，並檢查來源、時間碼、長度、直式 crop。

    Returns:
        問題清單（空清單代表通過）。以 "warn:" 開頭的是警告，不算失敗。
    """
    import jsonschema

    project_dir = project_dir.resolve()
    edl = load_edl(project_dir, edl_name)
    problems: list[str] = []
    schema = load_json(_repo_root() / "schemas" / "edl.schema.json")
    for err in sorted(jsonschema.Draft202012Validator(schema).iter_errors(edl), key=str):
        loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
        problems.append(f"schema {loc}: {err.message}")
    if problems:
        return problems

    manifest = load_manifest(project_dir)
    items = {it["id"]: it for it in manifest["items"]}
    aspect = edl["output"]["aspect"]
    out_w, out_h = ASPECT_SIZE[aspect]
    portrait_out = out_h > out_w

    seqs: set[int] = set()
    total = 0.0
    for clip in edl["clips"]:
        seq = int(clip["seq"])
        tag = f"clip seq={seq} ({clip.get('source')})"
        if seq in seqs:
            problems.append(f"{tag}: seq 重複")
        seqs.add(seq)
        item = items.get(clip["source"])
        if item is None:
            problems.append(f"{tag}: source 不在 manifest 裡")
            continue
        if item["type"] == "photo":
            if "duration" not in clip:
                problems.append(f"{tag}: 照片必須給 duration")
                continue
            if clip["duration"] <= 0:
                problems.append(f"{tag}: duration 必須 > 0")
        else:
            if "in" not in clip or "out" not in clip:
                problems.append(f"{tag}: 影片必須給 in/out")
                continue
            i, o, dur = float(clip["in"]), float(clip["out"]), float(item["duration"])
            if not 0 <= i < o:
                problems.append(f"{tag}: in/out 順序錯（in={i}, out={o}）")
            if o > dur + 0.05:
                problems.append(f"{tag}: out={o} 超過影片長度 {dur:.2f}")
            w, h = effective_size(item)
            if portrait_out and w > h and "crop" not in clip:
                problems.append(f"{tag}: 橫式影片輸出直式必須指定 crop（center/left/right/0..1）")
            if clip.get("keep_audio") and not item.get("has_audio"):
                problems.append(f"warn: {tag}: keep_audio 但來源沒有音軌")
        ao = clip.get("audio_override")
        if ao:
            src = items.get(ao["source"])
            if src is None or src["type"] != "video":
                problems.append(f"{tag}: audio_override.source 不是 manifest 裡的影片")
            elif float(ao["in"]) + clip_duration(clip) > float(src["duration"]) + 0.05:
                problems.append(f"{tag}: audio_override 超出 {ao['source']} 的長度")
        total += clip_duration(clip)

    overlaps = sum(
        CROSSFADE_SEC for c in edl["clips"][:-1] if c.get("transition_out") == "crossfade"
    )
    timeline = total - overlaps
    target = float(edl["output"]["target_duration"])
    if abs(timeline - target) / target > DURATION_TOLERANCE:
        problems.append(
            f"warn: 總長 {timeline:.1f}s 與 target_duration {target:.0f}s 差距超過 "
            f"{DURATION_TOLERANCE:.0%}"
        )
    return problems


def clip_file(project_dir: Path, clip: dict[str, Any]) -> Path:
    """`tripcut clips` 預裁檔的固定命名（同一段 in/out 在不同 EDL 可共用）。"""
    i, o = float(clip["in"]), float(clip["out"])
    return project_dir / "work" / "clips" / f"{clip['source']}_{i:07.2f}-{o:07.2f}.mp4"


def audio_file(project_dir: Path, clip: dict[str, Any]) -> Path:
    """audio_override 的預裁聲音檔（裁成跟畫面一樣長的小 mp4，Remotion 只取聲音）。"""
    ao = clip["audio_override"]
    i = float(ao["in"])
    o = i + clip_duration(clip)
    return project_dir / "work" / "clips" / f"{ao['source']}_{i:07.2f}-{o:07.2f}_audio.mp4"


def build_props(
    project_dir: Path, edl_name: str = "edl.json", props_name: str | None = None
) -> Path:
    """把 edl.json（秒）轉成 props.json（frame、絕對路徑），給 Remotion 用。"""
    project_dir = project_dir.resolve()
    hard = [p for p in validate_edl(project_dir, edl_name) if not p.startswith("warn:")]
    if hard:
        raise ValueError("edl 驗證未通過：\n" + "\n".join(hard))
    edl = load_edl(project_dir, edl_name)
    manifest = load_manifest(project_dir)
    items = {it["id"]: it for it in manifest["items"]}
    fps = int(edl["output"].get("fps", 30))
    width, height = ASPECT_SIZE[edl["output"]["aspect"]]

    def f(sec: float) -> int:
        return round(sec * fps)

    public_dir = project_dir / "work" / "public"

    def rel(p: Path, sub: str) -> str:
        """把檔案 stage 到 work/public/<sub>/（hard link，失敗就複製），回傳相對 public 的路徑。

        Remotion 的 bundler 會把整個 public dir 複製進暫存 bundle，且不能跨 junction，
        所以不能直接把專案目錄當 public dir；只放 render 真正用到的檔案。
        """
        dst = public_dir / sub / p.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not dst.samefile(p):
            dst.unlink()
        if not dst.exists():
            try:
                os.link(p, dst)
            except OSError:
                shutil.copy2(p, dst)
        staged.add(dst)
        return f"{sub}/{p.name}"

    staged: set[Path] = set()

    clips_out: list[dict[str, Any]] = []
    cursor = 0
    prev_overlap = 0
    for clip in sorted(edl["clips"], key=lambda c: int(c["seq"])):
        item = items[clip["source"]]
        dur_frames = f(clip_duration(clip))
        w, h = effective_size(item)
        entry: dict[str, Any] = {
            "seq": int(clip["seq"]),
            "source": clip["source"],
            "type": item["type"],
            "startFrame": cursor,
            "durationInFrames": dur_frames,
            "srcWidth": w,
            "srcHeight": h,
            "transitionOut": clip.get("transition_out", "cut"),
            "fadeInFrames": prev_overlap,
        }
        if item["type"] == "photo":
            entry["src"] = rel(item_source_path(project_dir, item), "photos")
            entry["effect"] = clip.get("effect", "kenburns")
            kb = clip.get("kenburns") or {"from": [0.5, 0.5, 1.0], "to": [0.5, 0.5, 1.1]}
            entry["kenburns"] = kb
        else:
            pre = clip_file(project_dir, clip)
            if pre.exists():
                entry["src"] = rel(pre, "clips")
                entry["inFrame"] = 0
                entry["precut"] = True
            else:
                # 沒預裁：整支原檔 stage 進去（大檔會很慢，建議先跑 tripcut clips）
                entry["src"] = rel(project_dir / item["path"], "raw")
                entry["inFrame"] = f(float(clip["in"]))
                entry["precut"] = False
            entry["keepAudio"] = bool(clip.get("keep_audio", False))
            crop = clip.get("crop", "center")
            entry["cropX"] = CROP_X[crop] if isinstance(crop, str) else float(crop)
        ao = clip.get("audio_override")
        if ao:
            src_item = items[ao["source"]]
            pre_audio = audio_file(project_dir, clip)
            if pre_audio.exists():
                entry["audioOverride"] = {"src": rel(pre_audio, "clips"), "inFrame": 0}
            else:
                entry["audioOverride"] = {
                    "src": rel(project_dir / src_item["path"], "raw"),
                    "inFrame": f(float(ao["in"])),
                }
        if clip.get("title"):
            entry["title"] = {
                "text": clip["title"]["text"],
                "style": clip["title"].get("style", "lower-third"),
            }
        # --- STYLE-TEMPLATE 的新層（見 docs/STYLE-TEMPLATE.md）---
        grade = clip.get("grade", edl["output"].get("grade", "none"))
        if grade and grade != "none":
            entry["grade"] = grade
        caps = clip.get("captions") or []
        if caps:
            entry["captions"] = [
                {
                    "layer": c["layer"],
                    "text": c["text"],
                    "fromFrame": f(float(c.get("in", 0.0))),
                    "durFrames": f(
                        float(c.get("out", clip_duration(clip))) - float(c.get("in", 0.0))
                    ),
                    **({"pos": c["pos"]} if c.get("pos") else {}),
                    **({"tone": c["tone"]} if c.get("tone") else {}),
                    **({"anim": c["anim"]} if c.get("anim") else {}),
                    **({"size": c["size"]} if c.get("size") else {}),
                }
                for c in caps
            ]
        if clip.get("badge"):
            b = clip["badge"]
            entry["badge"] = {
                "icon": b.get("icon", "📍"),
                "primary": b["primary"],
                **({"secondary": b["secondary"]} if b.get("secondary") else {}),
                "fromFrame": f(float(b.get("in", 0.0))),
                "durFrames": f(float(b.get("out", clip_duration(clip))) - float(b.get("in", 0.0))),
                **({"pos": b["pos"]} if b.get("pos") else {}),
            }
        if clip.get("photo_frame") and clip["photo_frame"] != "none":
            entry["photoFrame"] = clip["photo_frame"]
            entry["rotate"] = float(clip.get("rotate", -4))
        if clip.get("silence"):
            entry["silence"] = {
                "fromFrame": f(float(clip["silence"]["in"])),
                "toFrame": f(float(clip["silence"]["out"])),
            }
        trans = entry["transitionOut"]
        prev_overlap = 0
        if trans == "crossfade":
            entry["overlapFrames"] = f(CROSSFADE_SEC)
            prev_overlap = entry["overlapFrames"]
            cursor += dur_frames - entry["overlapFrames"]
        elif trans == "fade-black":
            entry["fadeOutFrames"] = f(FADE_BLACK_SEC)
            cursor += dur_frames
        else:
            cursor += dur_frames
        clips_out.append(entry)

    total_frames = max(c["startFrame"] + c["durationInFrames"] for c in clips_out)
    props: dict[str, Any] = {
        "project": edl["project"],
        "fps": fps,
        "width": width,
        "height": height,
        "durationInFrames": total_frames,
        "bgm": None,
        "preset": edl["output"].get("preset", "family"),
        "clips": clips_out,
    }
    if edl.get("bgm", {}).get("path"):
        props["bgm"] = {
            "src": rel(project_dir / edl["bgm"]["path"], "bgm"),
            "volume": float(edl["bgm"].get("volume", 0.5)),
            "duckUnderSpeech": bool(edl["bgm"].get("duck_under_speech", True)),
        }
    out_name = props_name or edl_name.replace("edl", "props", 1)
    out = project_dir / out_name
    _prune_public(project_dir, public_dir, staged, out)
    save_json(out, props)
    return out


def _prune_public(
    project_dir: Path, public_dir: Path, staged: set[Path], current_props: Path
) -> None:
    """清掉 work/public 裡沒有任何 props 指到的檔案。

    Remotion bundle 會把整個 public dir 複製一份，殘留的舊 clip 等於每次 render 都白複製
    幾百 MB（溪頭一度累積到 75 個 clip / 1.6 GB）。但專案可能同時有多份 props（60s / 120s /
    style），所以保留「任何一份 props 還指到的檔案」，只刪真正沒人用的。
    """
    keep = set(staged)
    for pf in project_dir.glob("props*.json"):
        if pf == current_props:
            continue
        try:
            data = load_json(pf)
        except (OSError, ValueError):
            continue
        srcs = [c["src"] for c in data.get("clips", []) if c.get("src")]
        srcs += [c["audioOverride"]["src"] for c in data.get("clips", []) if c.get("audioOverride")]
        if data.get("bgm", {}).get("src"):
            srcs.append(data["bgm"]["src"])
        keep.update(public_dir / s for s in srcs)
    for stale in public_dir.rglob("*"):
        if stale.is_file() and stale not in keep:
            stale.unlink()
