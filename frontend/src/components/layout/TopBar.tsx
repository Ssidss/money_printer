"use client"
import { usePathname } from "next/navigation"
import { UserMenu } from "./UserMenu"

export function TopBar() {
  const path = usePathname()
  if (path === "/login") return null

  return (
    <div className="flex items-center justify-end px-6 py-3 border-b border-slate-200 bg-white">
      <UserMenu />
    </div>
  )
}
