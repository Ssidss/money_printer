"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import type { AiNote } from "@/lib/api"

const REC_BADGE: Record<string, string> = {
  "強力推薦": "bg-green-100 text-green-700",
  "推薦":     "bg-blue-100 text-blue-700",
  "觀察":     "bg-yellow-100 text-yellow-700",
  "不推薦":   "bg-slate-100 text-slate-500",
}

const ACTION_BADGE: Record<string, string> = {
  "買入": "bg-green-100 text-green-700",
  "加碼": "bg-green-50 text-green-600",
  "持有": "bg-blue-50 text-blue-600",
  "減倉": "bg-orange-100 text-orange-600",
  "出場": "bg-red-100 text-red-600",
  "觀望": "bg-slate-100 text-slate-500",
}

const OUTCOME_LABEL: Record<string, string> = {
  "hit_target": "達標",
  "hit_stop": "停損",
  "expired": "到期",
  "pending": "進行中",
}

const OUTCOME_BADGE: Record<string, string> = {
  "hit_target": "bg-green-100 text-green-700 border-green-200",
  "hit_stop": "bg-red-100 text-red-700 border-red-200",
  "expired": "bg-slate-100 text-slate-500 border-slate-200",
  "pending": "bg-blue-100 text-blue-700 border-blue-200",
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins} 分鐘前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小時前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

function renderMarkdown(text: string) {
  // Very simple markdown rendering
  return text.split("\n").map((line, i) => {
    if (line.startsWith("### ")) {
      return <h4 key={i} className="text-sm font-semibold text-slate-700 mt-3 mb-1">{line.slice(4)}</h4>
    }
    if (line.startsWith("## ")) {
      return <h3 key={i} className="text-sm font-bold text-slate-800 mt-4 mb-1">{line.slice(3)}</h3>
    }
    if (line.startsWith("- ")) {
      return <li key={i} className="text-xs text-slate-600 ml-4 list-disc">{formatInline(line.slice(2))}</li>
    }
    if (line.startsWith("**") && line.endsWith("**")) {
      return <p key={i} className="text-xs font-semibold text-slate-700 mt-2">{line.slice(2, -2)}</p>
    }
    if (line.trim() === "") {
      return <div key={i} className="h-1" />
    }
    return <p key={i} className="text-xs text-slate-600 leading-relaxed">{formatInline(line)}</p>
  })
}

function formatInline(text: string) {
  // Bold: **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="font-semibold text-slate-700">{part.slice(2, -2)}</strong>
    }
    return <span key={i}>{part}</span>
  })
}

export function AiNotes({ ticker }: { ticker: string }) {
  const [notes, setNotes] = useState<AiNote[]>([])
  const [expanded, setExpanded] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.aiNotes(ticker, 5)
      .then(setNotes)
      .catch(() => setNotes([]))
      .finally(() => setLoading(false))
  }, [ticker])

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold text-slate-800 mb-3">🤖 AI 分析記錄</h3>
        <div className="text-xs text-slate-400 animate-pulse">載入中...</div>
      </div>
    )
  }

  if (notes.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold text-slate-800 mb-3">🤖 AI 分析記錄</h3>
        <p className="text-xs text-slate-400">尚無 AI 分析記錄</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-semibold text-slate-800 mb-3">🤖 AI 分析記錄</h3>
      <div className="space-y-3">
        {notes.map((note) => (
          <div
            key={note.id}
            className="rounded-lg border border-slate-100 overflow-hidden"
          >
            {/* Header */}
            <button
              onClick={() => setExpanded(expanded === note.id ? null : note.id)}
              className="w-full flex items-center gap-2 px-4 py-3 hover:bg-slate-50 transition-colors text-left"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${REC_BADGE[note.recommendation] ?? "bg-slate-100 text-slate-500"}`}>
                    {note.recommendation}
                  </span>
                  {note.action && (
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${ACTION_BADGE[note.action] ?? "bg-slate-100 text-slate-500"}`}>
                      {note.action}
                    </span>
                  )}
                  {note.outcome_status && (
                    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${OUTCOME_BADGE[note.outcome_status] ?? "bg-slate-100 text-slate-500 border-slate-200"}`}>
                      {OUTCOME_LABEL[note.outcome_status] ?? note.outcome_status}
                    </span>
                  )}
                  {note.smc_trend && (
                    <span className="text-xs text-slate-400">{note.smc_trend}</span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-slate-400">{timeAgo(note.created_at)}</span>
                  {note.price_at_analysis && (
                    <span className="text-xs text-slate-500">
                      分析時價 <span className="font-medium text-slate-700">${note.price_at_analysis.toFixed(2)}</span>
                    </span>
                  )}
                  {note.actual_return_pct != null && (
                    <span className={`text-xs font-bold ${note.actual_return_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {note.actual_return_pct >= 0 ? "+" : ""}{note.actual_return_pct.toFixed(2)}%
                    </span>
                  )}
                  {note.rr_ratio && (
                    <span className={`text-xs font-medium ${note.rr_ratio >= 2 ? "text-green-600" : "text-yellow-600"}`}>
                      R:R {note.rr_ratio}x
                    </span>
                  )}
                </div>
              </div>
              <span className="text-slate-300 text-sm flex-shrink-0">
                {expanded === note.id ? "▲" : "▼"}
              </span>
            </button>

            {/* Expanded content */}
            {expanded === note.id && (
              <div className="px-4 pb-4 border-t border-slate-100">
                {/* Price snapshot */}
                {(note.entry_price || note.stop_price || note.target_price) && (
                  <div className="grid grid-cols-3 gap-2 mt-3 mb-3">
                    {note.entry_price && (
                      <div className="rounded-lg bg-indigo-50 border border-indigo-100 p-2 text-center">
                        <p className="text-xs text-indigo-400">買入</p>
                        <p className="text-sm font-bold text-indigo-600">${note.entry_price.toFixed(2)}</p>
                      </div>
                    )}
                    {note.stop_price && (
                      <div className="rounded-lg bg-red-50 border border-red-100 p-2 text-center">
                        <p className="text-xs text-red-400">停損</p>
                        <p className="text-sm font-bold text-red-600">${note.stop_price.toFixed(2)}</p>
                      </div>
                    )}
                    {note.target_price && (
                      <div className="rounded-lg bg-green-50 border border-green-100 p-2 text-center">
                        <p className="text-xs text-green-400">目標</p>
                        <p className="text-sm font-bold text-green-600">${note.target_price.toFixed(2)}</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Result summary */}
                {(note.closed_price != null || note.actual_return_pct != null ||
                  (note.outcome_status && note.outcome_status !== "pending")) && (
                  <div className="mt-3 mb-3 rounded-lg bg-slate-50 border border-slate-100 p-3">
                    <p className="text-xs font-semibold text-slate-600 mb-2">交易結果</p>
                    <div className="grid grid-cols-3 gap-2">
                      {note.closed_price != null && (
                        <div className="text-center">
                          <p className="text-xs text-slate-400">結算價</p>
                          <p className="text-sm font-bold text-slate-700">${note.closed_price.toFixed(2)}</p>
                          {note.closed_at && (
                            <p className="text-xs text-slate-400 mt-0.5">{new Date(note.closed_at).toLocaleDateString("zh-TW")}</p>
                          )}
                        </div>
                      )}
                      {note.actual_return_pct != null && (
                        <div className="text-center">
                          <p className="text-xs text-slate-400">報酬率</p>
                          <p className={`text-sm font-bold ${note.actual_return_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                            {note.actual_return_pct >= 0 ? "+" : ""}{note.actual_return_pct.toFixed(2)}%
                          </p>
                        </div>
                      )}
                      {note.outcome_status && (
                        <div className="text-center">
                          <p className="text-xs text-slate-400">狀態</p>
                          <p className={`text-sm font-bold px-2 py-1 rounded ${
                            note.outcome_status === "hit_target" ? "text-green-600 bg-green-50" :
                            note.outcome_status === "hit_stop" ? "text-red-600 bg-red-50" :
                            note.outcome_status === "pending" ? "text-blue-600 bg-blue-50" :
                            "text-slate-600 bg-slate-100"
                          }`}>
                            {OUTCOME_LABEL[note.outcome_status] ?? note.outcome_status}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Scenarios */}
                {note.scenarios && Object.keys(note.scenarios).length > 0 && (
                  <div className="mb-3 space-y-1.5">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">情境分析</p>
                    {Object.entries(note.scenarios).map(([key, val]) => {
                      const s = val as Record<string, unknown>
                      return (
                        <div key={key} className="flex items-center gap-2 bg-slate-50 rounded-lg px-3 py-2">
                          <span className="text-xs font-bold text-indigo-500 w-5">{key}</span>
                          <span className="text-xs text-slate-600">{String(s.condition ?? "")}</span>
                          <span className="text-xs text-slate-400 ml-auto">{String(s.action ?? "")}</span>
                        </div>
                      )
                    })}
                  </div>
                )}

                {/* Full analysis */}
                <div className="mt-2 text-xs leading-relaxed">
                  {renderMarkdown(note.summary)}
                </div>

                <div className="mt-3 text-xs text-slate-300">
                  {new Date(note.created_at).toLocaleString("zh-TW")}
                  <span className="ml-2">{note.analysis_type === "individual" ? "個股分析" : note.analysis_type === "top_pick" ? "推薦分析" : note.analysis_type === "portfolio" ? "持倉健檢" : "觀察評估"}</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * 迷你版：只顯示最後一次 AI 分析的時間 + 推薦
 * 用於 StocksTable 清單頁
 */
export function AiNoteBadge({ note }: { note?: { recommendation: string; action: string | null; created_at: string } }) {
  if (!note) return <span className="text-xs text-slate-300">未分析</span>
  return (
    <div className="text-xs space-y-0.5">
      <div className="flex items-center gap-1">
        <span className={`px-1.5 py-0.5 rounded font-medium ${REC_BADGE[note.recommendation] ?? "bg-slate-100 text-slate-500"}`}>
          {note.recommendation}
        </span>
        {note.action && (
          <span className={`px-1.5 py-0.5 rounded font-medium ${ACTION_BADGE[note.action] ?? "bg-slate-100 text-slate-500"}`}>
            {note.action}
          </span>
        )}
      </div>
      <div className="text-slate-400">{timeAgo(note.created_at)}</div>
    </div>
  )
}
