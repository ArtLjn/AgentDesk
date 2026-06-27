import { useCallback, useEffect, useRef } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { ReviewDecidedEvent, ReviewRequestedEvent, WSMessage } from '@/types'

interface Handlers {
  onReviewRequested?: (event: ReviewRequestedEvent) => void
  onReviewDecided?: (event: ReviewDecidedEvent) => void
}

/**
 * 订阅 /api/ws/monitor 中的 review_requested / review_decided 事件。
 * 其他消息会被忽略。handler 引用变更不影响 WebSocket 连接稳定性。
 */
export function useReviewEvents(handlers: Handlers) {
  const handlersRef = useRef(handlers)
  useEffect(() => {
    handlersRef.current = handlers
  })

  const handleMessage = useCallback((msg: WSMessage) => {
    if (!msg || typeof msg.type !== 'string') return
    const h = handlersRef.current
    if (msg.type === 'review_requested' && h.onReviewRequested) {
      h.onReviewRequested(msg as unknown as ReviewRequestedEvent)
    } else if (msg.type === 'review_decided' && h.onReviewDecided) {
      h.onReviewDecided(msg as unknown as ReviewDecidedEvent)
    }
  }, [])

  return useWebSocket(handleMessage)
}


