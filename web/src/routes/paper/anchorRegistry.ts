import type { PaperCitationTarget } from "../../lib/paperTypes";
import { makeMissingPromptAnchorId, makePlanMappingAnchorId } from "./paperAnchors";

const anchorHighlightClass = "paper-anchor-highlight";
const anchorHighlightDurationMs = 1400;

let highlightedElement: HTMLElement | null = null;
let highlightTimer: ReturnType<typeof window.setTimeout> | null = null;

function assertNever(value: never): never {
  throw new Error(`Unsupported paper citation target: ${String(value)}`);
}

function clearCurrentHighlight(): void {
  if (highlightTimer !== null) {
    window.clearTimeout(highlightTimer);
    highlightTimer = null;
  }
  if (highlightedElement !== null) {
    highlightedElement.classList.remove(anchorHighlightClass);
    highlightedElement = null;
  }
}

function applyAnchorHighlight(target: HTMLElement): void {
  void target.offsetWidth;
  target.classList.add(anchorHighlightClass);
  highlightedElement = target;
  highlightTimer = window.setTimeout(() => {
    if (highlightedElement === target) {
      target.classList.remove(anchorHighlightClass);
      highlightedElement = null;
    }
    highlightTimer = null;
  }, anchorHighlightDurationMs);
}

export function resolveCitationTargetAnchorId(target: PaperCitationTarget): string {
  switch (target.kind) {
    case "section":
      return target.result_section;
    case "equation":
      return `paper-eq-${target.equation_id}`;
    case "parameter":
      switch (target.origin) {
        case "plan_mapping":
          return makePlanMappingAnchorId(
            target.row_index,
            target.paper_param_name,
            target.model_param_name,
          );
        case "missing_prompt":
          return makeMissingPromptAnchorId(target.prompt_id);
        default:
          return assertNever(target);
      }
    default:
      return assertNever(target);
  }
}

export function resolveCitationTargetElement(target: PaperCitationTarget): HTMLElement | null {
  return document.getElementById(resolveCitationTargetAnchorId(target));
}

export function scrollToCitationTarget(target: PaperCitationTarget): HTMLElement | null {
  const el = resolveCitationTargetElement(target);
  if (el === null) {
    return null;
  }
  const visibleTarget =
    el.closest<HTMLElement>(".paper-equation-item, .paper-param-row, .paper-section") ?? el;
  clearCurrentHighlight();
  visibleTarget.scrollIntoView({ behavior: "smooth", block: "start" });
  applyAnchorHighlight(visibleTarget);
  return visibleTarget;
}
