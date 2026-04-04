"use client"

import { useRouter } from "next/navigation"

export function BackButton() {
  const router = useRouter()
  return (
    <button
      onClick={() => router.back()}
      className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-indigo-600 transition-colors mb-1 group"
    >
      <svg className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
      返回
    </button>
  )
}
