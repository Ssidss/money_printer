import { api } from "@/lib/api"
import type { StrategyListItem } from "@/lib/api"
import { StrategyList } from "@/components/strategy/StrategyList"

export const revalidate = 0

export default async function StrategiesPage() {
  const strategies = await api.strategies().catch(() => [] as StrategyListItem[])

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">策略管理</h1>
          <p className="text-slate-500 text-sm mt-1">
            建立策略檔案 · 回測驗證 · 實戰追蹤
          </p>
        </div>
      </div>
      <StrategyList initialStrategies={strategies} />
    </div>
  )
}
