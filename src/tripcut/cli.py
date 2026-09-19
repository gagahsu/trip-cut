"""tripcut CLI 入口。

`tripcut <stage> <project_dir>` 對應 docs/PIPELINE.md 的四階段。
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    name="tripcut",
    help="旅遊素材 AI 剪輯 pipeline：本機分析 → 腳本 → 剪輯決策 → 渲染。",
    no_args_is_help=True,
)

ProjectDirArg = typer.Argument(..., help="旅行專案目錄，例如 projects/2026-10-okinawa")


def _ids(only: str | None) -> set[str] | None:
    return {s.strip() for s in only.split(",") if s.strip()} if only else None


@app.command()
def ingest(
    project_dir: Path = ProjectDirArg,
    tz: float = typer.Option(8.0, help="拍攝地時區（小時），影片 CreateDate 是 UTC 時用來換算"),
) -> None:
    """Stage 1：掃描 raw/，跑 exiftool + ffprobe，產出 manifest.json。"""
    from tripcut.common import load_json
    from tripcut.ingest import run_ingest, summarize

    out = run_ingest(project_dir, tz_hours=tz)
    typer.echo(summarize(load_json(out)))
    typer.echo(f"寫出 {out}")


@app.command()
def frames(
    project_dir: Path = ProjectDirArg,
    max_frames: int = typer.Option(12, help="每支影片抽幀上限"),
    scene_threshold: float = typer.Option(0.4, help="場景切換門檻（0–1）"),
    only: str | None = typer.Option(None, help="只處理這些 id，逗號分隔，例如 v001,v003"),
    force: bool = typer.Option(False, help="已抽過的也重抽"),
) -> None:
    """Stage 2：場景切換抽幀 + contact sheet。"""
    from tripcut.frames import run_frames

    out = run_frames(
        project_dir,
        max_frames=max_frames,
        scene_threshold=scene_threshold,
        only_ids=_ids(only),
        force=force,
    )
    typer.echo(f"contact sheet 在 {out}")


@app.command()
def transcribe(
    project_dir: Path = ProjectDirArg,
    model_size: str = typer.Option("small", help="faster-whisper 模型大小"),
    only: str | None = typer.Option(None, help="只處理這些 id，逗號分隔"),
    force: bool = typer.Option(False, help="做過的也重跑"),
    silence_db: float = typer.Option(-40.0, help="mean_volume 低於此值視為純環境音跳過"),
) -> None:
    """Stage 3：faster-whisper 逐字稿（僅處理有人聲的影片）。"""
    from tripcut.transcribe import run_transcribe

    out = run_transcribe(
        project_dir, model_size=model_size, only_ids=_ids(only), force=force, silence_db=silence_db
    )
    typer.echo(f"寫出 {out}")


EdlOpt = typer.Option(
    "edl.json", "--edl", help="EDL 檔名（同一專案可有多個版本，例如 edl-120.json）"
)


@app.command("edl-validate")
def edl_validate(project_dir: Path = ProjectDirArg, edl: str = EdlOpt) -> None:
    """Stage 4b：驗證 edl.json（schema、source 存在、時間碼越界、直式 crop）。"""
    from tripcut.edl import validate_edl

    problems = validate_edl(project_dir, edl)
    hard = [p for p in problems if not p.startswith("warn:")]
    for p in problems:
        typer.echo(f"[{'!' if not p.startswith('warn:') else '~'}] {p}")
    if hard:
        raise typer.Exit(code=1)
    typer.echo(f"{edl} 驗證通過" + ("（有警告）" if problems else ""))


@app.command()
def clips(
    project_dir: Path = ProjectDirArg,
    edl: str = EdlOpt,
    force: bool = typer.Option(False, help="已存在的預裁檔也重做"),
    kino: bool | None = typer.Option(
        None,
        "--kino/--no-kino",
        help="預設逐段自動選：來源 >3 分鐘走專案 ffmpeg，否則走 Kinocut（見 ADR-008）",
    ),
) -> None:
    """Stage 5 前置：把 EDL 的影片段落預裁成 work/clips/ 的 1080p 小檔。"""
    from tripcut.clips import run_clips

    outs = run_clips(project_dir, edl, force=force, use_kino=kino)
    typer.echo(f"{len(outs)} 個預裁檔在 {project_dir / 'work' / 'clips'}")


@app.command()
def props(
    project_dir: Path = ProjectDirArg,
    edl: str = EdlOpt,
    out: str | None = typer.Option(
        None, help="輸出檔名，預設把 edl 換成 props（edl-120.json → props-120.json）"
    ),
) -> None:
    """Stage 4b：把 edl.json 轉成 Remotion 用的 props.json。"""
    from tripcut.edl import build_props

    out_path = build_props(project_dir, edl, out)
    typer.echo(f"寫出 {out_path}")


MasterArg = typer.Argument(..., help="Remotion 出的母帶 mp4")
FinishOutOpt = typer.Option(None, help="輸出路徑，預設 <母帶>-share.mp4")
CrfOpt = typer.Option(22, help="交付檔畫質，數字越小越大檔")
LufsOpt = typer.Option(-14.0, help="目標整合響度（IG/TikTok 是 -14 LUFS）")


@app.command()
def finish(
    master: Path = MasterArg,
    out: Path | None = FinishOutOpt,
    crf: int = CrfOpt,
    lufs: float = LufsOpt,
) -> None:
    """Stage 6：母帶 → 交付檔（-14 LUFS 正規化 + bt709 tag + 降位元率）。"""
    from tripcut.finish import finish as run_finish
    from tripcut.finish import verify

    dst = run_finish(master, out, crf=crf, lufs=lufs)
    v = verify(dst)
    typer.echo(f"寫出 {dst}")
    typer.echo(
        f"  {v['duration']:.2f}s  {v['lufs']} LUFS  LRA {v['lra']} LU  "
        f"TP {v['true_peak']} dBFS  色彩 {v['color']}"
    )


if __name__ == "__main__":
    app()
