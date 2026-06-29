import type { EquationEntry } from "../../lib/paperTypes";

interface EquationListProps {
  items: EquationEntry[];
}

export function EquationList({ items }: EquationListProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <ol className="paper-equation-list">
      {items.map((equation) => (
        <li
          id={`paper-eq-${equation.equation_id}`}
          className="paper-equation-item"
          key={equation.equation_id}
        >
          <span className="paper-equation-id paper-token">{equation.equation_id}</span>
          <p className="paper-equation-body">{equation.latex_or_text}</p>
        </li>
      ))}
    </ol>
  );
}
