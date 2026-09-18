"""把抽幀／照片拼成 contact sheet 圖片，給 Claude 讀圖用。

規格見 docs/PIPELINE.md「Stage 2 — frames」：
- 影片：每列 4 張（直式素材改 6 張），每張下方寫 `v001 @ 12.40s`，
  頂部寫檔名、拍攝時間、總長度、資料夾。
- 照片：每列 5 張，標 `p001 · 03/16 11:26`。
- 單張 sheet 不超過 2000px 寬、8 列；超過就分頁 `v001_1.jpg`、`v001_2.jpg`。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from tripcut.common import find_font, load_json

MAX_WIDTH = 2000
MAX_ROWS = 8
LABEL_H = 26
HEADER_H = 44
PAD = 8
BG = (24, 24, 24)
FG = (235, 235, 235)
DIM = (160, 160, 160)


def _layout(is_portrait: bool, cols_override: int | None = None) -> tuple[int, int, int]:
    """回傳 (cols, cell_w, cell_h)。"""
    if is_portrait:
        cols = cols_override or 6
        cell_h = 480
    else:
        cols = cols_override or 4
        cell_h = 300
    cell_w = (MAX_WIDTH - PAD * (cols + 1)) // cols
    return cols, cell_w, cell_h


def _fit(im: Image.Image, w: int, h: int) -> Image.Image:
    im = im.copy()
    im.thumbnail((w, h))
    return im


def _paginate(n: int, per_page: int) -> list[tuple[int, int]]:
    pages: list[tuple[int, int]] = []
    start = 0
    while start < n:
        pages.append((start, min(n, start + per_page)))
        start += per_page
    return pages or [(0, 0)]


def _render_sheet(
    tiles: list[tuple[Image.Image, str]],
    header: str,
    is_portrait: bool,
    cols_override: int | None = None,
) -> Image.Image:
    cols, cell_w, cell_h = _layout(is_portrait, cols_override)
    rows = max(1, (len(tiles) + cols - 1) // cols)
    width = PAD + cols * (cell_w + PAD)
    height = HEADER_H + rows * (cell_h + LABEL_H + PAD) + PAD
    sheet = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(sheet)
    font = find_font(18)
    font_small = find_font(16)
    draw.text((PAD, 12), header, fill=FG, font=font)
    for i, (im, label) in enumerate(tiles):
        r, c = divmod(i, cols)
        x0 = PAD + c * (cell_w + PAD)
        y0 = HEADER_H + r * (cell_h + LABEL_H + PAD)
        thumb = _fit(im, cell_w, cell_h)
        ox = x0 + (cell_w - thumb.width) // 2
        oy = y0 + (cell_h - thumb.height) // 2
        sheet.paste(thumb, (ox, oy))
        draw.text((x0 + 2, y0 + cell_h + 4), label, fill=DIM, font=font_small)
    return sheet


def build_video_sheet(
    project_dir: Path, item: dict[str, Any], vid_dir: Path, contact_dir: Path
) -> list[Path]:
    index = load_json(vid_dir / "index.json")
    frames = index["frames"]
    if not frames:
        return []
    first = Image.open(vid_dir / frames[0]["file"])
    is_portrait = first.height > first.width
    first.close()
    cols, _, _ = _layout(is_portrait)
    per_page = cols * MAX_ROWS
    pages = _paginate(len(frames), per_page)
    taken = item["taken_at"][:16].replace("T", " ")
    header = (
        f"{item['id']}  {item['filename']}   拍攝 {taken}   "
        f"長度 {float(item['duration']):.1f}s   "
        f"{item['width']}x{item['height']} rot{item.get('rotation', 0)}"
        + (f"   資料夾 {item['folder']}" if item.get("folder") else "")
        + f"   抽幀 {index.get('strategy', '')}"
    )
    outputs: list[Path] = []
    for pi, (a, b) in enumerate(pages, start=1):
        tiles: list[tuple[Image.Image, str]] = []
        for fr in frames[a:b]:
            with Image.open(vid_dir / fr["file"]) as im:
                tiles.append((im.convert("RGB"), f"{item['id']} @ {fr['t']:.2f}s"))
        suffix = f"_{pi}" if len(pages) > 1 else ""
        sheet = _render_sheet(
            tiles, header + (f"  (page {pi}/{len(pages)})" if len(pages) > 1 else ""), is_portrait
        )
        out = contact_dir / f"{item['id']}{suffix}.jpg"
        sheet.save(out, "JPEG", quality=85)
        outputs.append(out)
    return outputs


def build_photo_sheet(
    project_dir: Path, photos: list[tuple[dict[str, Any], Path]], contact_dir: Path
) -> list[Path]:
    if not photos:
        return []
    with Image.open(photos[0][1]) as im0:
        is_portrait = im0.height > im0.width
    cols = 5 if not is_portrait else 7
    per_page = cols * MAX_ROWS
    pages = _paginate(len(photos), per_page)
    outputs: list[Path] = []
    for pi, (a, b) in enumerate(pages, start=1):
        tiles: list[tuple[Image.Image, str]] = []
        for item, thumb_path in photos[a:b]:
            t = item["taken_at"]
            label = f"{item['id']} · {t[5:7]}/{t[8:10]} {t[11:16]}"
            if item.get("folder"):
                label += f" · {item['folder']}"
            with Image.open(thumb_path) as im:
                tiles.append((im.convert("RGB"), label))
        header = f"{project_dir.name}  所有照片 {len(photos)} 張" + (
            f"  (page {pi}/{len(pages)})" if len(pages) > 1 else ""
        )
        sheet = _render_sheet(tiles, header, is_portrait, cols_override=cols)
        suffix = f"_{pi}" if len(pages) > 1 else ""
        out = contact_dir / f"ALL_photos{suffix}.jpg"
        sheet.save(out, "JPEG", quality=85)
        outputs.append(out)
    return outputs


def build_contact_sheet(frame_paths: list[Path], out_path: Path, cols: int = 4) -> Path:
    """通用版：把任意一組圖拼成 sheet（標籤用檔名）。"""
    tiles: list[tuple[Image.Image, str]] = []
    for p in frame_paths:
        with Image.open(p) as im:
            tiles.append((im.convert("RGB"), p.stem))
    with Image.open(frame_paths[0]) as im0:
        is_portrait = im0.height > im0.width
    sheet = _render_sheet(tiles, out_path.stem, is_portrait, cols_override=cols)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, "JPEG", quality=85)
    return out_path
