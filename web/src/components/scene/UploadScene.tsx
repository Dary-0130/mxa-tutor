import type { CSSProperties } from "react";
import { DustCanvas } from "./DustCanvas";

interface UploadSceneProps {
  state: "idle" | "dragging" | "uploading" | "parsing" | "failed";
  progress: number;
}

export function UploadScene({ state, progress }: UploadSceneProps) {
  const sceneProgress =
    state === "uploading" ? progress / 100 : state === "parsing" ? 1 : state === "dragging" ? 0.05 : 0;

  return (
    <div
      className="upload-scene"
      data-scene={state}
      data-scene-failed={state === "failed" ? "true" : undefined}
      style={{ "--scene-progress": String(sceneProgress) } as CSSProperties}
      aria-hidden="true"
    >
      <img className="scene-far-bg" src="/assets/upload-bg.webp" alt="" />
      <div className="scene-fog" />
      <DustCanvas opacity={state === "parsing" ? 0.55 : 0.32} />
      <div className="scene-vignette" />
    </div>
  );
}
