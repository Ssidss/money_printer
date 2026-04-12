import type { Metadata } from "next"
import "./globals.css"
import { Sidebar } from "@/components/layout/Sidebar"
import { TopBar } from "@/components/layout/TopBar"
import { Providers } from "@/components/layout/Providers"
import { StrategyPanel, StrategyToggle } from "@/components/layout/StrategyPanel"

export const metadata: Metadata = {
  title: "Money Printer",
  description: "股票自動分析系統",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body className="flex min-h-screen">
        <Providers>
          <Sidebar />
          <div className="flex-1 flex flex-col min-h-screen">
            <TopBar />
            <main className="flex-1 p-6 overflow-y-auto">{children}</main>
          </div>
          <StrategyToggle />
          <StrategyPanel />
        </Providers>
      </body>
    </html>
  )
}
