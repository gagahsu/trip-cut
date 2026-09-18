/**
 * Montage：單一 props 檔驅動的主 composition。
 *
 * props.json 由 `tripcut props` 產生（時間軸已經算成 frame），這裡只負責：
 * - 依 startFrame / durationInFrames 擺 <Sequence>
 * - 照片 Ken Burns、影片 cover crop（cropX 決定橫式素材裁哪邊）
 * - crossfade（下一段淡入蓋在上一段上面）、fade-black
 * - 字卡（center / lower-third / chapter）
 * - 可選 BGM，有人聲的段落自動 duck
 *
 * 動畫只用 useCurrentFrame / interpolate / <Sequence>（CLAUDE.md §6）。
 * 所有 src 都是相對於專案目錄的路徑，render 時用 --public-dir 指到專案目錄。
 */
import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type KenBurns = { from: [number, number, number]; to: [number, number, number] };
export type Title = { text: string; style: "center" | "lower-third" | "chapter" };

export type Clip = {
  seq: number;
  source: string;
  type: "photo" | "video";
  src: string;
  startFrame: number;
  durationInFrames: number;
  srcWidth: number;
  srcHeight: number;
  transitionOut: "cut" | "crossfade" | "fade-black" | "slide";
  fadeInFrames: number;
  overlapFrames?: number;
  fadeOutFrames?: number;
  // photo
  effect?: "none" | "kenburns";
  kenburns?: KenBurns;
  // video
  inFrame?: number;
  precut?: boolean;
  keepAudio?: boolean;
  cropX?: number;
  audioOverride?: { src: string; inFrame: number };
  title?: Title;
};

export type MontageProps = {
  project: string;
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  bgm: { src: string; volume: number; duckUnderSpeech: boolean } | null;
  clips: Clip[];
};

const FONT = '"Noto Sans TC", "Microsoft JhengHei", "PingFang TC", sans-serif';
const TITLE_FADE = 10;
const SAFE_BOTTOM = 250; // IG 直式安全區

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** 照片：cover 之後再依 kenburns [cx, cy, scale] 從 from 動到 to */
const KenBurnsPhoto: React.FC<{ clip: Clip }> = ({ clip }) => {
  const frame = useCurrentFrame();
  const { width: W, height: H } = useVideoConfig();
  const kb = clip.kenburns ?? { from: [0.5, 0.5, 1], to: [0.5, 0.5, 1.1] };
  const t = interpolate(frame, [0, clip.durationInFrames], [0, 1], clamp);
  const cx = kb.from[0] + (kb.to[0] - kb.from[0]) * t;
  const cy = kb.from[1] + (kb.to[1] - kb.from[1]) * t;
  const s = clip.effect === "none" ? 1 : kb.from[2] + (kb.to[2] - kb.from[2]) * t;
  const cover = Math.max(W / clip.srcWidth, H / clip.srcHeight);
  const dw = clip.srcWidth * cover * s;
  const dh = clip.srcHeight * cover * s;
  // 焦點 (cx, cy) 對到畫面中心，但不讓邊緣露出黑底
  const left = Math.min(0, Math.max(W - dw, W / 2 - cx * dw));
  const top = Math.min(0, Math.max(H - dh, H / 2 - cy * dh));
  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "black" }}>
      <Img
        src={staticFile(clip.src)}
        style={{ position: "absolute", left, top, width: dw, height: dh }}
      />
    </AbsoluteFill>
  );
};

const VideoClip: React.FC<{ clip: Clip }> = ({ clip }) => {
  const inFrame = clip.inFrame ?? 0;
  const cropX = clip.cropX ?? 0.5;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <OffthreadVideo
        src={staticFile(clip.src)}
        startFrom={inFrame}
        endAt={inFrame + clip.durationInFrames}
        muted={!clip.keepAudio}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: `${cropX * 100}% 50%`,
        }}
      />
      {clip.audioOverride ? (
        <Audio
          src={staticFile(clip.audioOverride.src)}
          startFrom={clip.audioOverride.inFrame}
          endAt={clip.audioOverride.inFrame + clip.durationInFrames}
        />
      ) : null}
    </AbsoluteFill>
  );
};

const TitleCard: React.FC<{ title: Title; durationInFrames: number }> = ({
  title,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps, width: W, height: H } = useVideoConfig();
  const show = Math.min(durationInFrames, Math.round(fps * 3.5));
  const opacity = interpolate(
    frame,
    [0, TITLE_FADE, show - TITLE_FADE, show],
    [0, 1, 1, 0],
    clamp,
  );
  const rise = interpolate(frame, [0, TITLE_FADE * 1.5], [16, 0], clamp);
  const base: React.CSSProperties = {
    position: "absolute",
    left: 0,
    right: 0,
    color: "white",
    fontFamily: FONT,
    textShadow: "0 2px 18px rgba(0,0,0,0.75), 0 0 2px rgba(0,0,0,0.9)",
    opacity,
    transform: `translateY(${rise}px)`,
    padding: `0 ${Math.round(W * 0.08)}px`,
    letterSpacing: 2,
  };
  if (title.style === "center") {
    return (
      <div
        style={{
          ...base,
          top: 0,
          bottom: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          fontSize: Math.round(W * 0.075),
          fontWeight: 500,
        }}
      >
        {title.text}
      </div>
    );
  }
  if (title.style === "chapter") {
    return (
      <div
        style={{
          ...base,
          top: Math.round(H * 0.16),
          fontSize: Math.round(W * 0.06),
          fontWeight: 500,
        }}
      >
        <div
          style={{
            width: Math.round(W * 0.1),
            height: 3,
            background: "white",
            marginBottom: 14,
            opacity: 0.85,
          }}
        />
        {title.text}
      </div>
    );
  }
  return (
    <div
      style={{
        ...base,
        bottom: SAFE_BOTTOM + Math.round(H * 0.04),
        fontSize: Math.round(W * 0.05),
        fontWeight: 400,
      }}
    >
      {title.text}
    </div>
  );
};

/** 一段素材：淡入（crossfade 的上層）、fade-black 淡出、字卡 */
const ClipLayer: React.FC<{ clip: Clip }> = ({ clip }) => {
  const frame = useCurrentFrame();
  const fadeIn = clip.fadeInFrames > 0 ? interpolate(frame, [0, clip.fadeInFrames], [0, 1], clamp) : 1;
  const fadeOut =
    clip.transitionOut === "fade-black" && clip.fadeOutFrames
      ? interpolate(
          frame,
          [clip.durationInFrames - clip.fadeOutFrames, clip.durationInFrames],
          [1, 0],
          clamp,
        )
      : 1;
  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
      {clip.type === "photo" ? <KenBurnsPhoto clip={clip} /> : <VideoClip clip={clip} />}
      {clip.title ? <TitleCard title={clip.title} durationInFrames={clip.durationInFrames} /> : null}
    </AbsoluteFill>
  );
};

const Bgm: React.FC<{ props: MontageProps }> = ({ props }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!props.bgm) return null;
  const speaking = props.bgm.duckUnderSpeech
    ? props.clips.some(
        (c) =>
          (c.keepAudio || c.audioOverride) &&
          frame >= c.startFrame &&
          frame < c.startFrame + c.durationInFrames,
      )
    : false;
  const tail = interpolate(
    frame,
    [props.durationInFrames - fps * 1.5, props.durationInFrames],
    [1, 0],
    clamp,
  );
  const volume = props.bgm.volume * (speaking ? 0.3 : 1) * tail;
  return <Audio src={staticFile(props.bgm.src)} volume={volume} loop />;
};

export const Montage: React.FC<MontageProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const openFade = interpolate(frame, [0, fps * 0.5], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <AbsoluteFill style={{ opacity: openFade }}>
        {props.clips.map((clip) => (
          <Sequence
            key={clip.seq}
            from={clip.startFrame}
            durationInFrames={clip.durationInFrames}
            name={`${clip.seq} ${clip.source}`}
          >
            <ClipLayer clip={clip} />
          </Sequence>
        ))}
      </AbsoluteFill>
      <Bgm props={props} />
    </AbsoluteFill>
  );
};
