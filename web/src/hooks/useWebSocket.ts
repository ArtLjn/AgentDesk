import { useEffect, useRef, useCallback } from 'react'
import type { WSMessage } from '@/types'

export function useWebSocket(onMessage?: (msg: WSMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.host}/api/ws/monitor`)

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        onMessage?.(msg)
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      wsRef.current = null
    }

    ws.onerror = () => ws.close()
    wsRef.current = ws
  }, [onMessage])

  useEffect(() => {
    connect()

    reconnectTimer.current = setInterval(() => {
      if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
        connect()
      }
    }, 5000)

    return () => {
      if (reconnectTimer.current) clearInterval(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { reconnect: connect }
}
