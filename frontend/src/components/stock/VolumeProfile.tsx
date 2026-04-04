"use client"
import type { VolumeProfileData } from "@/lib/api"

export function VolumeProfile({ vp }: { vp: VolumeProfileData }) {
  const sorted = [...vp.levels].sort((a, b) => b.price_mid - a.price_mid)
  const maxTotal = Math.max(...vp.levels.map(l => l.total_vol))

  return (
    <div className="space-y-1">
      {sorted.map((lv, i) => {
        const buyW  = maxTotal > 0 ? (lv.buy_vol  / maxTotal) * 100 : 0
        const sellW = maxTotal > 0 ? (lv.sell_vol / maxTotal) * 100 : 0
        const isPoc = lv.is_poc
        const inVA  = lv.in_va

        return (
          <div key={i} className={`flex items-center gap-2 rounded px-1 py-0.5 ${isPoc ? "bg-amber-50" : inVA ? "bg-indigo-50/40" : ""}`}>
            <span className={`text-xs w-14 text-right font-mono ${isPoc ? "text-amber-600 font-bold" : "text-slate-500"}`}>
              {lv.price_mid.toFixed(1)}
            </span>
            <div className="flex-1 flex gap-0.5 h-3">
              {/* 買壓（綠，右邊向右長） */}
              <div className="flex-1 flex justify-end items-center">
                <div className="h-2.5 bg-green-400 rounded-l" style={{ width: `${buyW}%` }} />
              </div>
              {/* 中線 */}
              <div className="w-px bg-slate-300" />
              {/* 賣壓（紅，左邊向左長） */}
              <div className="flex-1 flex items-center">
                <div className="h-2.5 bg-red-400 rounded-r" style={{ width: `${sellW}%` }} />
              </div>
            </div>
            {isPoc && <span className="text-xs text-amber-600 font-bold w-8">POC</span>}
            {!isPoc && inVA && <span className="text-xs text-indigo-400 w-8">VA</span>}
            {!isPoc && !inVA && <span className="w-8" />}
          </div>
        )
      })}

      <div className="flex justify-center gap-6 pt-2 text-xs text-slate-400">
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-green-400 rounded inline-block" /> 買壓</span>
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-red-400 rounded inline-block" /> 賣壓</span>
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-amber-400 rounded inline-block" /> POC</span>
      </div>
    </div>
  )
}
