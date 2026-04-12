"use client"
import { usePathname } from "next/navigation"
import { UserMenu } from "./UserMenu"
import { useStrategy } from "@/contexts/StrategyContext"

function StrategyBadge() {
  const { primaryDef: primary, mode, selectedStrategies, togglePanel } = useStrategy()
  if (!primary) return null

  return (
    <button
      onClick={togglePanel}
      className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:border-indigo-200 hover:text-indigo-600 transition-colors"
    >
      <span className="font-medium">{primary.shortLabel}</span>
      {mode === "multi" && selectedStrategies.length > 1 && (
        <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] text-indigo-600">
          +{selectedStrategies.length - 1}
        </span>
      )}
      {primary.metrics && (
        <span className="text-slate-400">
          CAGR {primary.metrics.cagr > 0 ? "+" : ""}{primary.metrics.cagr.toFixed(1)}%
        </span>
      )}
    </button>
  )
}

export function TopBar() {
  const path = usePathname()
  if (path === "/login") return null

  return (
    <div className="flex items-center justify-between px-6 py-3 border-b border-slate-200 bg-white">
      <StrategyBadge />
      <UserMenu />
    </div>
  )
}
