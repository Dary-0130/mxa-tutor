import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { label: "上传", to: "/" },
  { label: "导览", to: "/view/test-123" },
  { label: "问答", to: "/view/test-123/chat" },
];

export function Layout() {
  return (
    <div className="texture-concrete min-h-screen bg-[var(--color-concrete)] text-[var(--color-ite)]">
      <header className="border-b-2 border-[var(--color-rebar)] bg-[var(--color-formwork)]">
        <nav className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <NavLink to="/" className="text-xl font-black tracking-normal text-[var(--color-signal)]">
            工科仿真 AI 助教
          </NavLink>
          <div className="flex gap-2 font-mono text-xs font-bold uppercase">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `border-2 px-4 py-2 ${
                    isActive
                      ? "border-[var(--color-signal)] bg-[var(--color-signal)] text-[var(--color-concrete)]"
                      : "border-[var(--color-rebar)] text-[var(--color-ite)]"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-16">
        <Outlet />
      </main>
    </div>
  );
}
