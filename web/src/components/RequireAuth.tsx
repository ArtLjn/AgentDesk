import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { api, type AuthState } from '@/lib/api'

/**
 * 路由守卫：未登录跳转 /login，已登录渲染 children。
 *
 * 后端 auth_enabled=false 时也会放行（后端 /api/auth/me 返回 auth_enabled=false）。
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState | null>(null)
  const [error, setError] = useState(false)
  const location = useLocation()

  useEffect(() => {
    let alive = true
    api
      .getAuthState()
      .then((s) => alive && setState(s))
      .catch(() => alive && setError(true))
    return () => {
      alive = false
    }
  }, [])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        无法连接服务器
      </div>
    )
  }

  if (!state) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // 鉴权关闭，直接放行
  if (!state.auth_enabled) {
    return <>{children}</>
  }

  if (!state.logged_in) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
