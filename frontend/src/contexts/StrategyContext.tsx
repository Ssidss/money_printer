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
import { api } from "@/lib/api"
import type { V3ActiveConfig, V3ActiveSignals, BatchSignalResult } from "@/lib/api"

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

export type V3ActivationState = {
  active: boolean
  config: V3ActiveConfig | null
  signals: BatchSignalResult[]
  signalMap: Record<string, BatchSignalResult[]>  // ticker → signals
  buyCount: number
  loading: boolean
  dataDate: string | null
}

export type StrategyState = {
  mode: StrategyMode
  selectedStrategies: string[]      // 已選策略 ID 列表
  primaryStrategy: string           // 主策略
  panelOpen: boolean
  registry: StrategyDef[]
  v3: V3ActivationState             // V3 配置啟動狀態
}

type StrategyActions = {
  setPrimaryStrategy: (id: string) => void
  toggleStrategy: (id: string) => void
  setMode: (mode: StrategyMode) => void
  setPanelOpen: (open: boolean) => void
  togglePanel: () => void
  updateStrategyMetrics: (id: string, metrics: StrategyDef["metrics"]) => void
  primaryDef: StrategyDef | undefined  // useMemo derived, not a function
  activateV3: (backtestId?: number, params?: { strategies?: string[]; min_conditions?: number; min_rr?: number; market_filter?: string }) => Promise<void>
  deactivateV3: () => Promise<void>
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
  v3Config: V3ActiveConfig | null
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
const V3_INITIAL: V3ActivationState = {
  active: false,
  config: null,
  signals: [],
  signalMap: {},
  buyCount: 0,
  loading: false,
  dataDate: null,
}

function buildSignalMap(signals: BatchSignalResult[]): Record<string, BatchSignalResult[]> {
  const map: Record<string, BatchSignalResult[]> = {}
  for (const s of signals) {
    if (!map[s.ticker]) map[s.ticker] = []
    map[s.ticker].push(s)
  }
  return map
}

export function StrategyProvider({ children }: { children: ReactNode }) {
  const [mode, setModeRaw] = useState<StrategyMode>("single")
  const [selectedStrategies, setSelected] = useState<string[]>(["explosion_scanner"])
  const [primaryStrategy, setPrimaryRaw] = useState<string>("explosion_scanner")
  const [panelOpen, setPanelOpen] = useState(false)
  const [registry, setRegistry] = useState<StrategyDef[]>(STRATEGY_REGISTRY)
  const [hydrated, setHydrated] = useState(false)
  const [v3, setV3] = useState<V3ActivationState>(V3_INITIAL)

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
    // Restore V3 active config — fetch signals from backend if was active
    if (saved.v3Config) {
      setV3(prev => ({ ...prev, active: true, config: saved.v3Config!, loading: true }))
      api.backtestV3ActiveSignals()
        .then((res) => {
          setV3({
            active: true,
            config: res.config,
            signals: res.results,
            signalMap: buildSignalMap(res.results),
            buyCount: res.buy_count,
            loading: false,
            dataDate: res.data_date,
          })
        })
        .catch(() => {
          // Backend lost state — deactivate
          setV3(V3_INITIAL)
        })
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
    saveState({ mode, selectedStrategies, primaryStrategy, metricsMap, v3Config: v3.config })
  }, [mode, selectedStrategies, primaryStrategy, registry, hydrated, v3.config])

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

  // ── V3 Activation ─────────────────────────────────────
  const activateV3 = useCallback(async (
    backtestId?: number,
    params?: { strategies?: string[]; min_conditions?: number; min_rr?: number; market_filter?: string },
  ) => {
    setV3(prev => ({ ...prev, loading: true }))
    try {
      const res = await api.backtestV3Activate({
        backtest_id: backtestId,
        strategies: params?.strategies,
        min_conditions: params?.min_conditions,
        min_rr: params?.min_rr,
        market_filter: params?.market_filter,
      })
      setV3({
        active: true,
        config: res.config,
        signals: res.results,
        signalMap: buildSignalMap(res.results),
        buyCount: res.buy_count,
        loading: false,
        dataDate: res.data_date,
      })
    } catch (e) {
      setV3(prev => ({ ...prev, loading: false }))
      throw e
    }
  }, [])

  const deactivateV3 = useCallback(async () => {
    try {
      await api.backtestV3Deactivate()
    } catch { /* ignore */ }
    setV3(V3_INITIAL)
  }, [])

  return (
    <StrategyContext.Provider
      value={{
        mode,
        selectedStrategies,
        primaryStrategy,
        panelOpen,
        registry,
        v3,
        setPrimaryStrategy,
        toggleStrategy,
        setMode,
        setPanelOpen,
        togglePanel,
        updateStrategyMetrics,
        primaryDef,
        activateV3,
        deactivateV3,
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
