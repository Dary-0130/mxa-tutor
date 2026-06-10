import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PanoramaScene } from "../components/scene/PanoramaScene";
import { PanelIndicator } from "../components/ui/PanelIndicator";
import { ApiException } from "../lib/api";
import { resolveErrorMessage } from "../lib/errorMessages";
import {
  hasSeenOverview,
  markOverviewSeen,
  markScrollHintShown,
  shouldShowScrollHint,
} from "../lib/localStore";
import type { ProjectOverview } from "../lib/types";
import { OverviewTopAction } from "./overview/OverviewTopAction";
import { PanelEntries } from "./overview/panels/PanelEntries";
import { PanelEvidenceCta } from "./overview/panels/PanelEvidenceCta";
import { PanelFlow } from "./overview/panels/PanelFlow";
import { PanelIntro } from "./overview/panels/PanelIntro";
import { PanelKeyItems } from "./overview/panels/PanelKeyItems";
import { PanelLearning } from "./overview/panels/PanelLearning";
import { useHorizontalScroll } from "./overview/useHorizontalScroll";
import { usePanelObserver } from "./overview/usePanelObserver";
import { useParallaxBg } from "./overview/useParallaxBg";
import { useProjectOverview } from "./overview/useProjectOverview";

const PANEL_COUNT = 6;

function OverviewLoading() {
  return (
    <main className="overview-state-page">
      <PanoramaScene panoramaX={0} />
      <p>正在生成工程导览 · 请稍候</p>
    </main>
  );
}

function OverviewError({
  error,
  retry,
}: {
  error: ApiException;
  retry: () => void;
}) {
  const notFound = error.code === "project_not_found" || error.status === 404;
  const generationFailed = error.code === "overview_generation";
  const serviceUnavailable = error.status === 503 || error.status === 504;
  const title = notFound
    ? "工程不存在"
    : generationFailed
      ? "导览生成失败"
      : serviceUnavailable
        ? "服务暂时不可用"
        : resolveErrorMessage(error.code);

  return (
    <main className="overview-state-page">
      <PanoramaScene panoramaX={0} />
      <section className="overview-error-panel">
        <h1>{title}</h1>
        <p>{notFound ? "可能已过期或被删除" : resolveErrorMessage(error.code)}</p>
        <div>
          {!notFound ? (
            <button type="button" onClick={retry}>
              重试
            </button>
          ) : null}
          <Link to="/">{generationFailed ? "重新上传" : "返回上传页"}</Link>
        </div>
      </section>
    </main>
  );
}

function OverviewExperience({ data, projectId }: { data: ProjectOverview; projectId: string }) {
  const scrollRef = useRef<HTMLElement | null>(null);
  const [seen, setSeen] = useState(() => hasSeenOverview(projectId));
  const [showHint, setShowHint] = useState(() => shouldShowScrollHint());
  const scrollToPanel = useHorizontalScroll(scrollRef, PANEL_COUNT);
  const panoramaX = useParallaxBg(scrollRef, PANEL_COUNT);

  const markSeen = useCallback(() => {
    markOverviewSeen(projectId);
    setSeen(true);
  }, [projectId]);

  const onPanelVisible = useCallback(
    (index: number) => {
      if (index === PANEL_COUNT - 1) {
        markSeen();
      }
    },
    [markSeen],
  );

  const currentIndex = usePanelObserver(scrollRef, onPanelVisible);

  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "preload";
    link.as = "image";
    link.href = "/assets/panorama.webp";
    document.head.appendChild(link);
    return () => link.remove();
  }, []);

  useEffect(() => {
    if (!showHint) {
      return undefined;
    }
    markScrollHintShown();
    const timer = window.setTimeout(() => setShowHint(false), 2500);
    return () => window.clearTimeout(timer);
  }, [showHint]);

  return (
    <main className="overview-page">
      <PanoramaScene panoramaX={panoramaX} />
      <OverviewTopAction
        projectId={projectId}
        seen={seen}
        onJumpToEnd={() => scrollToPanel(PANEL_COUNT - 1)}
      />
      <section ref={scrollRef} className="overview-scroll" role="region" aria-label="工程导览">
        <PanelIntro overview={data} onFocusPanel={scrollToPanel} />
        <PanelEntries overview={data} onFocusPanel={scrollToPanel} />
        <PanelFlow overview={data} onFocusPanel={scrollToPanel} />
        <PanelKeyItems overview={data} onFocusPanel={scrollToPanel} />
        <PanelLearning overview={data} onFocusPanel={scrollToPanel} />
        <PanelEvidenceCta
          overview={data}
          projectId={projectId}
          onCta={markSeen}
          onFocusPanel={scrollToPanel}
        />
      </section>
      {showHint ? <div className="scroll-hint">用 ← → 方向键或滚轮浏览</div> : null}
      <PanelIndicator currentIndex={currentIndex} total={PANEL_COUNT} onSelect={scrollToPanel} />
    </main>
  );
}

export function OverviewPage() {
  const { projectId } = useParams();
  const resolvedProjectId = projectId ?? "";
  const { data, loading, error, retry } = useProjectOverview(resolvedProjectId);

  if (!resolvedProjectId) {
    return <OverviewError error={new ApiException(404, "project_not_found", "")} retry={() => undefined} />;
  }
  if (loading) {
    return <OverviewLoading />;
  }
  if (error || !data) {
    return <OverviewError error={error ?? new ApiException(500, "internal_error", "")} retry={retry} />;
  }

  return <OverviewExperience data={data} projectId={resolvedProjectId} />;
}
