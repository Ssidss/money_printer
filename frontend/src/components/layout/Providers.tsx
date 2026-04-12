"use client"
import { AuthProvider } from "@/contexts/AuthContext"
import { StrategyProvider } from "@/contexts/StrategyContext"
import type { ReactNode } from "react"

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <StrategyProvider>{children}</StrategyProvider>
    </AuthProvider>
  )
}
