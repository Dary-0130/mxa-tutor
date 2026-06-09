import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="brutal-panel max-w-3xl p-8">
      <p className="font-mono text-sm font-bold uppercase text-[var(--color-signal)]">404</p>
      <h1 className="mt-4 text-4xl font-black leading-tight md:text-5xl">页面不存在</h1>
      <p className="mt-6 max-w-2xl text-sm leading-7 text-[var(--color-rebar)]">
        当前路径没有匹配的前端页面。
      </p>
      <Link
        className="mt-8 inline-block bg-[var(--color-signal)] px-5 py-3 font-mono text-xs font-bold uppercase text-[var(--color-concrete)]"
        to="/"
      >
        返回上传页
      </Link>
    </section>
  );
}
