import { api } from "@/lib/api"
import type { StrategyListItem } from "@/lib/api"
import { StrategyList } from "@/components/strategy/StrategyList"
import { BacktestV3Panel } from "@/components/strategy/BacktestV3Panel"

export const revalidate = 0

export default async function StrategiesPage() {
  const strategies = await api.strategies().catch(() => [] as StrategyListItem[])

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* V3 Multi-Strategy Backtest */}
      <section>
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-slate-800">V3 回測引擎</h1>
          <p className="text-slate-500 text-sm mt-1">
            Multi-Strategy Engine — Signal → Decision → Order → Fill → Position
          </p>
        </div>
        <BacktestV3Panel />
      </section>

      {/* V2 Strategy Profiles */}
      <section>
        <div className="mb-4">
          <h2 className="text-xl font-bold text-slate-800">V2 策略管理</h2>
          <p className="text-slate-500 text-sm mt-1">
            建立策略檔案 · 回測驗證 · 實戰追蹤
          </p>
        </div>
        <StrategyList initialStrategies={strategies} />
      </section>
    </div>
  )
}
