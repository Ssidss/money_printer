"use client"
import { useStrategy, type StrategyDef } from "@/contexts/StrategyContext"

// ── Floating toggle button (always visible) ─────────────
export function StrategyToggle() {
  const { togglePanel, panelOpen, primaryDef: primary, v3 } = useStrategy()

  if (panelOpen) return null

  return (
    <button
      onClick={togglePanel}
      className={`fixed right-4 top-20 z-40 flex items-center gap-2 rounded-lg border px-3 py-2 text-sm shadow-md transition-all ${
        v3.active
          ? "border-emerald-300 bg-emerald-50 text-emerald-700 hover:border-emerald-400"
          : "border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-600"
      }`}
      title="策略面板"
    >
      {v3.active && <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />}
      <span className="text-base">&#9881;</span>
      <span className="hidden sm:inline max-w-[120px] truncate">
        {v3.active ? "V3" : primary?.shortLabel ?? "策略"}
      </span>
    </button>
  )
}

// ── Side panel ──────────────────────────────────────────
export function StrategyPanel() {
  const {
    panelOpen,
    setPanelOpen,
    mode,
    setMode,
    registry,
    primaryStrategy,
    selectedStrategies,
    setPrimaryStrategy,
    toggleStrategy,
    v3,
    deactivateV3,
  } = useStrategy()

  if (!panelOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/10"
        onClick={() => setPanelOpen(false)}
      />

      {/* Panel */}
      <aside className="fixed right-0 top-0 z-50 flex h-full w-80 flex-col border-l border-slate-200 bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-800">
            Strategy Panel
          </h2>
          <button
            onClick={() => setPanelOpen(false)}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Mode toggle */}
        <div className="border-b border-slate-100 px-5 py-3">
          <div className="flex rounded-lg bg-slate-100 p-0.5">
            <button
              className={`flex-1 rounded-md py-1.5 text-xs font-medium transition-colors ${
                mode === "single"
                  ? "bg-white text-slate-800 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
              onClick={() => setMode("single")}
            >
              Single
            </button>
            <button
              className={`flex-1 rounded-md py-1.5 text-xs font-medium transition-colors ${
                mode === "multi"
                  ? "bg-white text-slate-800 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
              onClick={() => setMode("multi")}
            >
              Multi
            </button>
          </div>
          <p className="mt-1.5 text-xs text-slate-400">
            {mode === "single"
              ? "全站按主策略顯示"
              : "同時顯示多策略分析"}
          </p>
        </div>

        {/* V3 Active Config Banner */}
        {v3.active && (
          <div className="border-b border-slate-100 px-5 py-3">
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs font-semibold text-emerald-700">V3 配置已啟動</span>
                </div>
                <button
                  onClick={deactivateV3}
                  className="text-[10px] text-red-500 hover:text-red-700"
                >
                  停用
                </button>
              </div>
              <div className="text-[10px] text-emerald-600 space-y-0.5">
                <div>
                  策略: {v3.config?.strategies.map(s =>
                    s === "smc_v2" ? "SMC" : s === "explosion_scanner" ? "Explosion" : s === "momentum_breakout" ? "Momentum" : s
                  ).join(" + ")}
                </div>
                <div>
                  min_cond={v3.config?.params.min_conditions} | min_rr={v3.config?.params.min_rr}
                </div>
                <div className="font-medium">
                  {v3.buyCount} BUY signals | {v3.dataDate && `數據日期: ${v3.dataDate}`}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Strategy list */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-2">
          {registry.map((s) => (
            <StrategyCard
              key={s.id}
              strategy={s}
              isPrimary={primaryStrategy === s.id}
              isSelected={selectedStrategies.includes(s.id)}
              mode={mode}
              onSelect={() => {
                if (mode === "single") {
                  setPrimaryStrategy(s.id)
                } else {
                  toggleStrategy(s.id)
                }
              }}
              onSetPrimary={() => setPrimaryStrategy(s.id)}
            />
          ))}
        </div>

        {/* Footer hint */}
        <div className="border-t border-slate-100 px-5 py-3">
          <p className="text-xs text-slate-400">
            回測結果會自動更新策略指標。到「策略回測」頁面跑回測。
          </p>
        </div>
      </aside>
    </>
  )
}

// ── Strategy card ───────────────────────────────────────
function StrategyCard({
  strategy,
  isPrimary,
  isSelected,
  mode,
  onSelect,
  onSetPrimary,
}: {
  strategy: StrategyDef
  isPrimary: boolean
  isSelected: boolean
  mode: "single" | "multi"
  onSelect: () => void
  onSetPrimary: () => void
}) {
  const active = mode === "single" ? isPrimary : isSelected
  const m = strategy.metrics

  return (
    <div
      className={`rounded-lg border p-3 transition-all cursor-pointer ${
        active
          ? "border-indigo-300 bg-indigo-50/50"
          : "border-slate-200 bg-white hover:border-slate-300"
      }`}
      onClick={onSelect}
    >
      {/* Title row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Radio / Checkbox indicator */}
          <span
            className={`flex h-4 w-4 items-center justify-center rounded-full border text-[10px] ${
              active
                ? "border-indigo-500 bg-indigo-500 text-white"
                : "border-slate-300 bg-white"
            }`}
          >
            {active && (mode === "single" ? "\u2022" : "\u2713")}
          </span>
          <span className="text-sm font-medium text-slate-800">
            {strategy.label}
          </span>
        </div>
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
            strategy.category === "breakout"
              ? "bg-amber-100 text-amber-700"
              : "bg-blue-100 text-blue-700"
          }`}
        >
          {strategy.category}
        </span>
      </div>

      {/* Description */}
      <p className="mt-1 text-xs text-slate-500 leading-relaxed">
        {strategy.description}
      </p>

      {/* Params */}
      <div className="mt-2 flex flex-wrap gap-1">
        {Object.entries(strategy.defaultParams).map(([k, v]) => (
          <span
            key={k}
            className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500"
          >
            {k}={String(v)}
          </span>
        ))}
      </div>

      {/* Metrics (if available) */}
      {m && (
        <div className="mt-2 grid grid-cols-3 gap-x-3 gap-y-1 text-[11px]">
          <MetricCell label="CAGR" value={`${m.cagr > 0 ? "+" : ""}${m.cagr.toFixed(1)}%`} positive={m.cagr > 0} />
          <MetricCell label="Sharpe" value={m.sharpe.toFixed(2)} positive={m.sharpe > 1} />
          <MetricCell label="MDD" value={`${m.mdd.toFixed(1)}%`} positive={m.mdd < 10} />
          <MetricCell label="Trades" value={String(m.trades)} />
          <MetricCell label="WR" value={`${m.winRate.toFixed(1)}%`} positive={m.winRate > 50} />
          <MetricCell label="PF" value={m.profitFactor.toFixed(2)} positive={m.profitFactor > 1.5} />
        </div>
      )}

      {/* Set as primary (multi mode only) */}
      {mode === "multi" && isSelected && !isPrimary && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onSetPrimary()
          }}
          className="mt-2 text-[11px] text-indigo-500 hover:text-indigo-700"
        >
          Set as primary
        </button>
      )}
      {isPrimary && (
        <span className="mt-2 inline-block text-[11px] text-indigo-600 font-medium">
          Primary
        </span>
      )}
    </div>
  )
}

function MetricCell({
  label,
  value,
  positive,
}: {
  label: string
  value: string
  positive?: boolean
}) {
  return (
    <div>
      <span className="text-slate-400">{label} </span>
      <span
        className={
          positive === undefined
            ? "text-slate-700"
            : positive
            ? "text-emerald-600"
            : "text-slate-600"
        }
      >
        {value}
      </span>
    </div>
  )
}
