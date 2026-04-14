import { api } from "@/lib/api"
import { StrategyDetail } from "@/components/strategy/StrategyDetail"
import Link from "next/link"

export const revalidate = 0

export default async function StrategyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const profileId = parseInt(id)

  const [strategy, results] = await Promise.allSettled([
    api.strategy(profileId),
    api.backtestV2Results(profileId),
  ])

  if (strategy.status === "rejected") {
    return (
      <div className="max-w-7xl mx-auto py-16 text-center text-slate-400">
        <p className="text-xl mb-2">找不到策略</p>
        <Link href="/strategies" className="text-indigo-500 hover:underline">返回策略列表</Link>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <StrategyDetail
        strategy={strategy.value}
        backtestResults={results.status === "fulfilled" ? results.value : []}
      />
    </div>
  )
}
