"use client"
import { useEffect, useRef, useState } from "react"
import { SSE_URL } from "@/lib/api"

export type ProgressEvent = {
  message: string
  phase: string
  current: number
  total: number
  ticker: string
  pct: number
}

export function useSSE() {
  const [progress, setProgress] = useState<ProgressEvent | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [topPicks, setTopPicks] = useState<unknown[] | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource(SSE_URL)
    esRef.current = es

    es.addEventListener("progress", (e) => {
      const data: ProgressEvent = JSON.parse(e.data)
      setProgress(data)
      setIsRunning(data.phase !== "done" && data.phase !== "error")
    })

    es.addEventListener("analysis_complete", (e) => {
      const data = JSON.parse(e.data)
      setTopPicks(data.top_picks)
      setIsRunning(false)
      setProgress(null)
    })

    es.addEventListener("analysis_error", () => {
      setIsRunning(false)
    })

    return () => es.close()
  }, [])

  return { progress, isRunning, topPicks }
}
