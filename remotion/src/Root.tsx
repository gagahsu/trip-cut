import "./index.css";
import { CalculateMetadataFunction, Composition } from "remotion";
import { Montage, MontageProps } from "./Montage";

/** 沒帶 --props 時的空白預設（studio 開得起來就好） */
const emptyProps: MontageProps = {
  project: "empty",
  fps: 30,
  width: 1080,
  height: 1920,
  durationInFrames: 30,
  bgm: null,
  clips: [],
};

/** 主 composition：尺寸／長度／fps 全由 props.json 決定 */
const fromProps: CalculateMetadataFunction<MontageProps> = ({ props }) => ({
  durationInFrames: Math.max(1, props.durationInFrames),
  fps: props.fps,
  width: props.width,
  height: props.height,
});

/** 同一份 props 硬轉 16:9（影片 cover crop、照片 Ken Burns 會自動重算） */
const as16x9: CalculateMetadataFunction<MontageProps> = ({ props }) => ({
  durationInFrames: Math.max(1, props.durationInFrames),
  fps: props.fps,
  width: 1920,
  height: 1080,
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Montage"
        component={Montage}
        defaultProps={emptyProps}
        durationInFrames={30}
        fps={30}
        width={1080}
        height={1920}
        calculateMetadata={fromProps}
      />
      <Composition
        id="Montage16x9"
        component={Montage}
        defaultProps={emptyProps}
        durationInFrames={30}
        fps={30}
        width={1920}
        height={1080}
        calculateMetadata={as16x9}
      />
    </>
  );
};
