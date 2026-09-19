/**
 * STYLE-TEMPLATE 的視覺層（docs/STYLE-TEMPLATE.md）。
 *
 * 四層字幕、強調字脈動、位置膠囊、拍立得外框、warm/cool 調色。
 * 動畫只用 useCurrentFrame / interpolate（CLAUDE.md §6），不可用 CSS animation。
 */
import React from "react";
import { loadVariableFont } from "@remotion/google-fonts/NotoSansTC";
import {
  AbsoluteFill,
  Img,
  cancelRender,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

/**
 * 字型從 Google Fonts 載入，不依賴機器上裝了什麼。
 *
 * 之前寫死系統字型 "Noto Sans TC Black"，沒裝的機器會靜默退回 Microsoft JhengHei UI
 * （沒有 Black 字重），章節標和強調字會變細、整個風格跑掉，而且不會報錯。
 *
 * 用 variable font：一次涵蓋 100-900 全部字重（900 = 章節標／主字幕／強調字、
 * 500 = translit 層），請求數是靜態版的一半（102 vs 204）。CJK 字型被 Google 切成
 * 上百個 unicode-range 分塊，所以請求數本來就高，這裡明確關掉警告。
 * 代價是 render 時要能連外網抓字型。
 */
const fontHandle = delayRender("載入 Noto Sans TC");
loadVariableFont("normal", {
  subsets: ["chinese-traditional", "latin"],
  ignoreTooManyRequestsWarning: true,
})
  .waitUntilDone()
  .then(() => continueRender(fontHandle))
  .catch((err) => cancelRender(err));

export type CaptionLayerName = "chapter" | "main" | "translit" | "emphasis";

export type Caption = {
  layer: CaptionLayerName;
  text: string;
  fromFrame: number;
  durFrames: number;
  pos?: [number, number];
  tone?: "neutral" | "author";
  anim?: "none" | "pulse" | "pop";
  size?: number;
};

export type Badge = {
  icon: string;
  primary: string;
  secondary?: string;
  fromFrame: number;
  durFrames: number;
  pos?: [number, number];
};

export type Grade = "warm" | "cool" | "none";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const FONT_HEAVY = '"Noto Sans TC", "Microsoft JhengHei UI", sans-serif';
const FONT_LATIN = '"Segoe UI", "Noto Sans TC", sans-serif';

const PINK = "#FF4D8D";
const EMPH_OUTER = "#D62200";
const EMPH_INNER = "#FF9A1F";

/** 每層的預設位置與字級（佔畫面寬的比例），量自 sample 兩支片 */
const LAYER_SPEC: Record<
  CaptionLayerName,
  { pos: [number, number]; size: number; weight: number; font: string; stroke: number }
> = {
  chapter: { pos: [0.5, 0.19], size: 0.055, weight: 900, font: FONT_HEAVY, stroke: 0.0062 },
  main: { pos: [0.5, 0.72], size: 0.058, weight: 900, font: FONT_HEAVY, stroke: 0.0062 },
  translit: { pos: [0.5, 0.785], size: 0.05, weight: 500, font: FONT_LATIN, stroke: 0 },
  emphasis: { pos: [0.5, 0.45], size: 0.115, weight: 900, font: FONT_HEAVY, stroke: 0.013 },
};

/**
 * 描邊字：底層畫粗描邊、上層畫填色，兩層完全重疊。
 * 不用 -webkit-text-stroke 單層，因為它從字身內側吃掉筆畫，中文會糊。
 */
const StrokeText: React.FC<{
  text: string;
  color: string;
  strokes: { color: string; width: number }[];
  style: React.CSSProperties;
}> = ({ text, color, strokes, style }) => (
  <div style={{ position: "relative", display: "inline-block", whiteSpace: "pre-wrap" }}>
    {strokes.map((s, i) => (
      <div
        key={i}
        style={{
          ...style,
          position: i === 0 ? "relative" : "absolute",
          left: 0,
          top: 0,
          color: "transparent",
          WebkitTextStroke: `${s.width}px ${s.color}`,
          zIndex: i,
        }}
      >
        {text}
      </div>
    ))}
    <div
      style={{
        ...style,
        position: strokes.length === 0 ? "relative" : "absolute",
        left: 0,
        top: 0,
        color,
        zIndex: strokes.length + 1,
      }}
    >
      {text}
    </div>
  </div>
);

const CaptionItem: React.FC<{ cap: Caption; frame: number }> = ({ cap, frame }) => {
  const { fps, width: W } = useVideoConfig();
  const spec = LAYER_SPEC[cap.layer];
  const [px, py] = cap.pos ?? spec.pos;
  const size = Math.round(W * (cap.size ?? spec.size));
  // 描邊隨字級等比放大，字大了描邊才不會顯得細
  const sw = Math.round(W * spec.stroke * ((cap.size ?? spec.size) / spec.size));

  // 樣本的字幕幾乎是瞬間出現，只留 3 frame 的緩衝避免閃爍
  const fade = interpolate(
    frame,
    [0, 3, Math.max(4, cap.durFrames - 3), cap.durFrames],
    [0, 1, 1, 0],
    clamp,
  );

  let scale = 1;
  if (cap.anim === "pulse") {
    // 實測樣本：週期 0.65s、幅度約 ±12%
    scale = 1 + 0.12 * Math.sin((2 * Math.PI * frame) / (0.65 * fps));
  } else if (cap.anim === "pop") {
    scale = interpolate(frame, [0, 4, 7], [0.7, 1.08, 1], clamp);
  }

  let strokes: { color: string; width: number }[] = [];
  if (cap.layer === "emphasis") {
    strokes = [
      { color: EMPH_OUTER, width: sw * 2 },
      { color: EMPH_INNER, width: sw },
    ];
  } else if (cap.layer === "main") {
    strokes = [{ color: cap.tone === "author" ? PINK : "#101010", width: sw * 2 }];
  } else if (cap.layer === "chapter") {
    strokes = [{ color: "#101010", width: sw * 2 }];
  }

  const textStyle: React.CSSProperties = {
    fontFamily: spec.font,
    fontWeight: spec.weight,
    fontSize: size,
    lineHeight: 1.28,
    letterSpacing: cap.layer === "translit" ? 0.5 : 1.5,
    textAlign: "center",
    margin: 0,
    textShadow:
      cap.layer === "translit"
        ? "0 2px 12px rgba(0,0,0,0.85), 0 0 3px rgba(0,0,0,0.9)"
        : "0 4px 14px rgba(0,0,0,0.45)",
  };

  return (
    // 外層鋪滿整個寬度再置中，字才有整幀的寬度可用；
    // 只用 left:%+translateX(-50%) 的話可用寬度只剩一半，長句會被硬斷行。
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: `${py * 100}%`,
        display: "flex",
        justifyContent: "center",
        transform: `translate(${(px - 0.5) * 100}%, -50%) scale(${scale})`,
        opacity: fade,
        pointerEvents: "none",
      }}
    >
      <div style={{ maxWidth: "86%" }}>
        <StrokeText text={cap.text} color="white" strokes={strokes} style={textStyle} />
      </div>
    </div>
  );
};

export const Captions: React.FC<{ captions: Caption[] }> = ({ captions }) => {
  const frame = useCurrentFrame();
  return (
    <>
      {captions.map((cap, i) => {
        const local = frame - cap.fromFrame;
        if (local < 0 || local >= cap.durFrames) return null;
        return <CaptionItem key={i} cap={cap} frame={local} />;
      })}
    </>
  );
};

export const LocationBadge: React.FC<{ badge: Badge }> = ({ badge }) => {
  const frame = useCurrentFrame();
  const { width: W } = useVideoConfig();
  const local = frame - badge.fromFrame;
  if (local < 0 || local >= badge.durFrames) return null;
  const [px, py] = badge.pos ?? [0.34, 0.25];
  const size = Math.round(W * 0.046);
  const fade = interpolate(local, [0, 4, badge.durFrames - 4, badge.durFrames], [0, 1, 1, 0], clamp);
  const rise = interpolate(local, [0, 8], [10, 0], clamp);
  return (
    <div
      style={{
        position: "absolute",
        left: `${px * 100}%`,
        top: `${py * 100}%`,
        transform: `translate(-50%, -50%) translateY(${rise}px)`,
        opacity: fade,
        background: "#FBF3DE",
        borderRadius: 999,
        padding: `${Math.round(size * 0.34)}px ${Math.round(size * 0.66)}px`,
        display: "flex",
        alignItems: "center",
        gap: Math.round(size * 0.3),
        fontFamily: FONT_HEAVY,
        fontWeight: 900,
        fontSize: size,
        boxShadow: "0 6px 22px rgba(0,0,0,0.28)",
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ fontSize: size * 1.05 }}>{badge.icon}</span>
      <span style={{ color: "#E2761B" }}>{badge.primary}</span>
      {badge.secondary ? <span style={{ color: "#5A3A1B" }}>{badge.secondary}</span> : null}
    </div>
  );
};

/** 拍立得卡：米白紙鋪滿全幀，照片旋轉後貼上，帶柔和投影。照片不動（sample 實測 diff=0）*/
export const PolaroidPhoto: React.FC<{
  src: string;
  srcWidth: number;
  srcHeight: number;
  rotate: number;
}> = ({ src, srcWidth, srcHeight, rotate }) => {
  const { width: W, height: H } = useVideoConfig();
  const boxW = Math.round(W * 0.82);
  const boxH = Math.round(boxW * (srcHeight / srcWidth));
  const maxH = Math.round(H * 0.66);
  const scale = boxH > maxH ? maxH / boxH : 1;
  return (
    <AbsoluteFill style={{ background: "#F2F0EB", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "47%",
          width: boxW,
          height: boxH,
          transform: `translate(-50%, -50%) rotate(${rotate}deg) scale(${scale})`,
          boxShadow: "0 18px 54px rgba(0,0,0,0.30), 0 2px 8px rgba(0,0,0,0.18)",
          background: "white",
          overflow: "hidden",
        }}
      >
        <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
    </AbsoluteFill>
  );
};

/**
 * 調色。CSS filter（GPU）+ soft-light 疊色，比 SVG feComponentTransfer 快很多。
 * 參數對著 docs/STYLE-TEMPLATE.md §5 的目標值調：
 *   contrast 0.93 把溪頭素材爆掉的天空 (p99=1.00) 壓回 ~0.94，順便把對比拉到 0.71
 *   疊色負責中間調的 R/B 偏移
 */
export const GRADE_CSS: Record<Exclude<Grade, "none">, { filter: string; tint: string; alpha: number }> = {
  warm: { filter: "saturate(1.18) contrast(0.93) brightness(0.99)", tint: "#FF8A2B", alpha: 0.16 },
  cool: { filter: "saturate(0.97) contrast(0.93) brightness(1.02)", tint: "#2B7BFF", alpha: 0.16 },
};

export const GradeWrap: React.FC<{ grade?: Grade; children: React.ReactNode }> = ({
  grade,
  children,
}) => {
  if (!grade || grade === "none") return <>{children}</>;
  const g = GRADE_CSS[grade];
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ filter: g.filter }}>{children}</AbsoluteFill>
      <AbsoluteFill
        style={{ background: g.tint, opacity: g.alpha, mixBlendMode: "soft-light" }}
      />
    </AbsoluteFill>
  );
};
