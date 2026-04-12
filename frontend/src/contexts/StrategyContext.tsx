"use client"
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from "react"

// ── Strategy definitions ────────────────────────────────
export type StrategyDef = {
  id: string               // "explosion_scanner" | "momentum_breakout" | "smc_v2"
  label: string            // 顯示名稱
  shortLabel: string       // 簡稱（用於小空間）
  description: string      // 一句話描述
  category: "breakout" | "trend"
  defaultParams: Record<string, number | string>
  // 最近回測結果（從 localStorage 或 API 載入）
  metrics?: {
    cagr: number
    sharpe: number
    mdd: number
    trades: number
    winRate: number
    profitFactor: number
  }
}

export const STRATEGY_REGISTRY: StrategyDef[] = [
  {
    id: "explosion_scanner",
    label: "Explosion Scanner",
    shortLabel: "Explosion",
    description: "放量突破爆擊掃描，score >= 50 觸發",
    category: "breakout",
    defaultParams: { score_threshold: 50, stop_pct: 8, target_pct: 25 },
  },
  {
    id: "momentum_breakout",
    label: "Momentum Breakout",
    shortLabel: "Momentum",
    description: "N 日新高突破 + 放量確認",
    category: "breakout",
    defaultParams: { breakout_period: 20, volume_ratio_min: 1.5, min_rr: 1.5 },
  },
  {
    id: "smc_v2",
    label: "SMC v2",
    shortLabel: "SMC",
    description: "Smart Money Concept 結構分析 + OB/FVG 進場",
    category: "trend",
    defaultParams: { min_conditions: 3, min_rr: 2.0 },
  },
]

// ── State types ─────────────────────────────────────────
export type StrategyMode = "single" | "multi"

export type StrategyState = {
  mode: StrategyMode
  selectedStrategies: string[]      // 已選策略 ID 列表
  primaryStrategy: string           // 主策略
  panelOpen: boolean
  registry: StrategyDef[]
}

type StrategyActions = {
  setPrimaryStrategy: (id: string) => void
  toggleStrategy: (id: string) => void
  setMode: (mode: StrategyMode) => void
  setPanelOpen: (open: boolean) => void
  togglePanel: () => void
  updateStrategyMetrics: (id: string, metrics: StrategyDef["metrics"]) => void
  primaryDef: StrategyDef | undefined  // useMemo derived, not a function
}

type StrategyContextType = StrategyState & StrategyActions

const StrategyContext = createContext<StrategyContextType | null>(null)

// ── localStorage key ────────────────────────────────────
const LS_KEY = "mp_strategy_state"

type PersistedState = {
  mode: StrategyMode
  selectedStrategies: string[]
  primaryStrategy: string
  metricsMap: Record<string, StrategyDef["metrics"]>
}

function loadState(): Partial<PersistedState> {
  if (typeof window === "undefined") return {}
  try {
    const raw = localStorage.getItem(LS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveState(s: PersistedState) {
  if (typeof window === "undefined") return
  localStorage.setItem(LS_KEY, JSON.stringify(s))
}

// ── Provider ────────────────────────────────────────────
export function StrategyProvider({ children }: { children: ReactNode }) {
  const [mode, setModeRaw] = useState<StrategyMode>("single")
  const [selectedStrategies, setSelected] = useState<string[]>(["explosion_scanner"])
  const [primaryStrategy, setPrimaryRaw] = useState<string>("explosion_scanner")
  const [panelOpen, setPanelOpen] = useState(false)
  const [registry, setRegistry] = useState<StrategyDef[]>(STRATEGY_REGISTRY)
  const [hydrated, setHydrated] = useState(false)

  // Hydrate from localStorage on mount
  useEffect(() => {
    const saved = loadState()
    if (saved.mode) setModeRaw(saved.mode)
    if (saved.selectedStrategies?.length) setSelected(saved.selectedStrategies)
    if (saved.primaryStrategy) setPrimaryRaw(saved.primaryStrategy)
    if (saved.metricsMap) {
      setRegistry((prev) =>
        prev.map((s) => ({
          ...s,
          metrics: saved.metricsMap?.[s.id] ?? s.metrics,
        }))
      )
    }
    setHydrated(true)
  }, [])

  // Persist on change (after hydration)
  useEffect(() => {
    if (!hydrated) return
    const metricsMap: Record<string, StrategyDef["metrics"]> = {}
    registry.forEach((s) => {
      if (s.metrics) metricsMap[s.id] = s.metrics
    })
    saveState({ mode, selectedStrategies, primaryStrategy, metricsMap })
  }, [mode, selectedStrategies, primaryStrategy, registry, hydrated])

  // ── Actions ───────────────────────────────────────────
  const setPrimaryStrategy = useCallback((id: string) => {
    setPrimaryRaw(id)
    // Ensure primary is in selected
    setSelected((prev) => (prev.includes(id) ? prev : [...prev, id]))
  }, [])

  const toggleStrategy = useCallback((id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) {
        // Don't remove if it's the only one
        if (prev.length <= 1) return prev
        const next = prev.filter((s) => s !== id)
        // If removing primary, switch to first remaining
        setPrimaryRaw((cur) => (cur === id ? next[0] : cur))
        return next
      }
      return [...prev, id]
    })
  }, [])

  const setMode = useCallback((m: StrategyMode) => {
    setModeRaw(m)
  }, [])

  const togglePanel = useCallback(() => {
    setPanelOpen((p) => !p)
  }, [])

  const updateStrategyMetrics = useCallback(
    (id: string, metrics: StrategyDef["metrics"]) => {
      setRegistry((prev) =>
        prev.map((s) => (s.id === id ? { ...s, metrics } : s))
      )
    },
    []
  )

  const primaryDef = useMemo(
    () => registry.find((s) => s.id === primaryStrategy),
    [registry, primaryStrategy]
  )

  return (
    <StrategyContext.Provider
      value={{
        mode,
        selectedStrategies,
        primaryStrategy,
        panelOpen,
        registry,
        setPrimaryStrategy,
        toggleStrategy,
        setMode,
        setPanelOpen,
        togglePanel,
        updateStrategyMetrics,
        primaryDef,
      }}
    >
      {children}
    </StrategyContext.Provider>
  )
}

export function useStrategy() {
  const ctx = useContext(StrategyContext)
  if (!ctx) throw new Error("useStrategy must be used inside StrategyProvider")
  return ctx
}
