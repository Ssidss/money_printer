"use client"

import { useEffect, useState, useCallback } from "react"

export interface PipelineProgressEvent {
  type: "progress" | "complete" | "error"
  message: string
  iteration?: number
  win_rate?: number
  converged?: boolean
  status?: string
  error?: string
  validation_report?: Record<string, unknown>
}

export function usePipelineProgress() {
  const [events, setEvents] = useState<PipelineProgressEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    const eventSource = new EventSource(`${BASE}/sse/progress`)

    eventSource.addEventListener("pipeline_progress", (event) => {
      try {
        const data = JSON.parse(event.data)
        setEvents((prev) => [...prev, { type: "progress", ...data }])
      } catch (e) {
        console.error("Failed to parse pipeline_progress event", e)
      }
    })

    eventSource.addEventListener("pipeline_complete", (event) => {
      try {
        const data = JSON.parse(event.data)
        setEvents((prev) => [...prev, { type: "complete", ...data, message: "Pipeline completed" }])
      } catch (e) {
        console.error("Failed to parse pipeline_complete event", e)
      }
    })

    eventSource.addEventListener("pipeline_error", (event) => {
      try {
        const data = JSON.parse(event.data)
        setEvents((prev) => [...prev, { type: "error", ...data, message: `Error: ${data.error}` }])
      } catch (e) {
        console.error("Failed to parse pipeline_error event", e)
      }
    })

    eventSource.onopen = () => {
      setIsConnected(true)
    }

    eventSource.onerror = () => {
      setIsConnected(false)
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [])

  const clearEvents = useCallback(() => {
    setEvents([])
  }, [])

  return { events, isConnected, clearEvents }
}
