import type { CSSProperties } from "react";
import { DustCanvas } from "./DustCanvas";

interface PanoramaSceneProps {
  panoramaX: number;
}

export function PanoramaScene({ panoramaX }: PanoramaSceneProps) {
  return (
    <div className="panorama-scene" aria-hidden="true">
      <img
        className="scene-panorama"
        src="/assets/panorama.webp"
        alt=""
        style={{ transform: `translate3d(${panoramaX}px, 0, 0)` } as CSSProperties}
        onError={(event) => {
          event.currentTarget.hidden = true;
        }}
      />
      <div className="scene-fog" />
      <DustCanvas opacity={0.38} />
      <div className="scene-vignette" />
    </div>
  );
}
