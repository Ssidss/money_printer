"use client"
import { useAuth } from "@/contexts/AuthContext"
import { useRouter } from "next/navigation"
import Link from "next/link"

export function UserMenu() {
  const { user, logout, loading } = useAuth()
  const router = useRouter()

  if (loading) return null

  if (!user) {
    return (
      <Link
        href="/login"
        className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors"
      >
        登入
      </Link>
    )
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-sm font-bold">
          {user.display_name[0]}
        </div>
        <span className="text-sm font-medium text-slate-700">{user.display_name}</span>
      </div>
      <button
        onClick={() => { logout(); router.push("/login") }}
        className="text-xs text-slate-400 hover:text-red-500 transition-colors"
      >
        登出
      </button>
    </div>
  )
}
