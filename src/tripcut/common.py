"""各 stage 共用的小工具：subprocess 包裝、找外部程式、讀寫 manifest、字型。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v"}


class ToolMissing(RuntimeError):
    """外部工具（ffmpeg / exiftool）找不到。"""


def find_tool(name: str) -> str:
    """回傳外部程式的完整路徑；PATH 找不到時再試幾個 Windows 常見安裝位置。"""
    found = shutil.which(name)
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA", "")
    candidates: list[Path] = []
    if name == "exiftool":
        candidates.append(Path(local) / "Programs" / "ExifTool" / "ExifTool.exe")
    for c in candidates:
        if c.exists():
            return str(c)
    raise ToolMissing(f"找不到 {name}，請確認已安裝並在 PATH 上（見 docs/SETUP.md）")


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str


def _clean_env() -> dict[str, str]:
    """給外部指令用的環境變數。

    uv 管理的 venv 會設 PYTHONHOME 指向 3.11；`uvx --from kinocut kino` 自己跑 3.12，
    繼承到會炸 "SRE module mismatch"。ffmpeg/exiftool 不在乎，一律拿掉最安全。
    """
    drop = ("PYTHONHOME", "PYTHONPATH", "UV_INTERNAL__PYTHONHOME", "__PYVENV_LAUNCHER__")
    return {k: v for k, v in os.environ.items() if k.upper() not in drop}


def run(cmd: list[str], *, check: bool = True, timeout: float | None = None) -> RunResult:
    """跑外部指令，stdout/stderr 都以 UTF-8 讀回來（壞字元用 replace）。"""
    proc = subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        check=False,
        encoding="utf-8",
        errors="replace",
        env=_clean_env(),
    )
    if check and proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()[-5:]
        raise RuntimeError(f"指令失敗 ({proc.returncode}): {cmd[0]} …\n" + "\n".join(tail))
    return RunResult(proc.returncode, proc.stdout, proc.stderr)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_manifest(project_dir: Path) -> dict[str, Any]:
    mpath = project_dir / "manifest.json"
    if not mpath.exists():
        raise FileNotFoundError(f"{mpath} 不存在，請先跑 `tripcut ingest`")
    return load_json(mpath)


def item_source_path(project_dir: Path, item: dict[str, Any]) -> Path:
    """照片優先用 converted_path（HEIC 轉檔後的 jpg），否則用原始 path。"""
    rel = item.get("converted_path") or item["path"]
    return project_dir / rel


def find_font(size: int) -> Any:
    """找一個有 CJK 字元的 TrueType 字型給 Pillow 用；找不到就退回內建點陣字。"""
    from PIL import ImageFont

    windir = os.environ.get("WINDIR", "C:/Windows")
    candidates = [
        Path(windir) / "Fonts" / "msjh.ttc",  # 微軟正黑體
        Path(windir) / "Fonts" / "msjhbd.ttc",
        Path(windir) / "Fonts" / "mingliu.ttc",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path(windir) / "Fonts" / "arial.ttf",
    ]
    for c in candidates:
        if c.exists():
            try:
                return ImageFont.truetype(str(c), size)
            except OSError:
                continue
    return ImageFont.load_default()


def fmt_seconds(sec: float) -> str:
    """12.4 → '00:12.40'；3725.1 → '1:02:05.10'。"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}" if h else f"{m:02d}:{s:05.2f}"
