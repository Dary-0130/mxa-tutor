import { useEffect, useState } from "react";

const SECTIONS = [
  { id: "paper-summary", label: "论文摘要" },
  { id: "paper-subsystems", label: "子系统划分" },
  { id: "paper-build-steps", label: "建模步骤" },
  { id: "paper-parameters", label: "参数对照" },
  { id: "paper-tuning", label: "调参建议" },
] as const;

export function SectionNav() {
  const [activeId, setActiveId] = useState<string>(SECTIONS[0].id);

  useEffect(() => {
    if (!("IntersectionObserver" in window)) {
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
        if (visible?.target.id) {
          setActiveId(visible.target.id);
        }
      },
      { rootMargin: "-18% 0px -62% 0px", threshold: [0.2, 0.45, 0.7] },
    );
    for (const section of SECTIONS) {
      const element = document.getElementById(section.id);
      if (element) {
        observer.observe(element);
      }
    }
    return () => observer.disconnect();
  }, []);

  return (
    <nav className="paper-section-nav" aria-label="论文工作台章节">
      {SECTIONS.map((section) => (
        <a
          key={section.id}
          href={`#${section.id}`}
          data-active={activeId === section.id ? "true" : undefined}
          onClick={() => setActiveId(section.id)}
        >
          {section.label}
        </a>
      ))}
    </nav>
  );
}
