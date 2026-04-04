import type { Metadata } from "next"
import "./globals.css"
import { Sidebar } from "@/components/layout/Sidebar"

export const metadata: Metadata = {
  title: "Money Printer",
  description: "股票自動分析系統",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 p-6 min-h-screen overflow-y-auto">{children}</main>
      </body>
    </html>
  )
}
