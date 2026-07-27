"use client";

export function Footer({
  total,
  page,
  pages,
  pageSize,
  onPage,
  onPageSize,
}: {
  total: number;
  page: number;
  pages: number;
  pageSize: number;
  onPage: (p: number) => void;
  onPageSize: (n: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] px-4 py-3 text-sm text-[var(--muted)]">
      <div className="flex items-center gap-2">
        <span>Show</span>
        {[10, 25, 50].map((n) => (
          <button
            key={n}
            onClick={() => onPageSize(n)}
            className={n === pageSize ? "text-[var(--accent)] font-semibold" : ""}
          >
            {n}
          </button>
        ))}
        <span className="ml-3">Found: {total.toLocaleString()}</span>
      </div>
      <div className="flex items-center gap-2">
        <button disabled={page <= 1} onClick={() => onPage(page - 1)} className="disabled:opacity-40">
          Previous
        </button>
        <span>
          Page {page} of {pages}
        </span>
        <button disabled={page >= pages} onClick={() => onPage(page + 1)} className="disabled:opacity-40">
          Next
        </button>
      </div>
    </div>
  );
}
