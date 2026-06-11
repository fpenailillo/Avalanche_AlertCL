export default function GlassCard({ icon: Icon, title, children, className = '' }) {
  return (
    <section
      className={`flex flex-col rounded-3xl border border-white/15 bg-white/10 shadow-lg shadow-black/10 backdrop-blur-xl ${className}`}
    >
      {title && (
        <header className="flex items-center gap-1.5 px-5 pt-4 pb-2 text-[11px] font-semibold uppercase tracking-wider text-white/60">
          {Icon && <Icon className="h-3.5 w-3.5" />}
          {title}
        </header>
      )}
      <div className="flex min-h-0 flex-1 flex-col px-5 pb-5">{children}</div>
    </section>
  )
}
