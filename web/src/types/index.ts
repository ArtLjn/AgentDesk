// 工单相关
export interface Ticket {
  ticket_id: string
  content: string
  user_id?: string
  category: string | null
  priority: string | null
  processing_result: string | null
  references: string[]
  review_score: number | null
  retry_count: number
  status: TicketStatus
  error: string | null
  created_at: string
}

export type TicketStatus = 'received' | 'classifying' | 'processing' | 'reviewing' | 'completed' | 'failed'
export type TicketCategory = 'technical' | 'billing' | 'complaint' | 'inquiry'
export type TicketPriority = 'P0' | 'P1' | 'P2' | 'P3'

export interface TicketCreateRequest {
  content: string
  user_id?: string
}

// Trace 相关
export interface Trace {
  trace_id: string
  ticket_id: string
  status: 'running' | 'completed' | 'failed'
  start_time: number
  end_time: number | null
  duration: number | null
  total_tokens: number
  total_tool_calls: number
  node_count: number
  error: string | null
  ticket_summary?: string | null
  ticket_category?: TicketCategory | null
  ticket_priority?: TicketPriority | null
  ticket_result?: string | null
  ticket_review_score?: number | null
  reference_count?: number
  references?: string[]
}

export interface Span {
  span_id: string
  trace_id: string
  parent_span_id: string | null
  span_type: 'node' | 'react_iter' | 'llm_call' | 'tool_call'
  name: string
  status: 'ok' | 'error' | 'fallback'
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  start_time: number
  end_time: number | null
  duration: number | null
  metadata: Record<string, unknown> | null
  children: Span[]
}

export interface TraceDetail {
  trace_id: string
  ticket_id: string
  status: string
  duration: number | null
  total_tokens: number
  total_tool_calls: number
  node_count: number
  start_time: number
  end_time: number | null
  ticket_summary?: string | null
  ticket_category?: TicketCategory | null
  ticket_priority?: TicketPriority | null
  ticket_result?: string | null
  ticket_review_score?: number | null
  reference_count?: number
  references?: string[]
  spans: Span[]
}

export interface TraceListResponse {
  traces: Trace[]
  count: number
  total: number
  limit: number
  offset: number
}

// 统计相关
export interface ResolutionStats {
  total: number
  completed: number
  failed: number
  avg_retries: number
  success_rate: number
}

export interface Analytics {
  category_distribution: Record<string, number>
  priority_distribution: Record<string, number>
  resolution_stats: ResolutionStats
  daily_stats: DailyStat[]
  efficiency: {
    avg_tokens_per_ticket: number
    avg_duration_seconds: number
    avg_tool_calls: number
  }
  evaluation: {
    total: number
    completed: number
    failed: number
    avg_retries: number
    success_rate: number
    avg_tokens_per_ticket: number
    avg_duration_seconds: number
    avg_tool_calls: number
    avg_review_score: number
    satisfaction_rate: number
    total_feedback: number
  }
}

export interface DailyStat {
  date: string
  total: number
  completed: number
  failed: number
}

// 知识库
export interface KnowledgeUploadRequest {
  title: string
  content: string
  category?: string
}

export interface KnowledgeChunk {
  index: number
  content: string
  point_id: string
}

export interface KnowledgeDocument {
  id: string
  title: string
  category: string
  source?: string
  content: string
  preview: string
  chunk_count: number
  chunks: KnowledgeChunk[]
}

export interface KnowledgeListResponse {
  documents: KnowledgeDocument[]
  count: number
  next_offset: string | null
}

// WebSocket
export interface WSMessage {
  ticket_id: string
  status: string
  message: string
  timestamp: string
  node?: string
  data?: Record<string, unknown>
}

// 系统设置
export interface SystemSettings {
  llm_base_url: string
  llm_api_key: string
  llm_model: string
  max_retries: number
  review_threshold: number
  max_react_iterations: number
  max_messages: number
  max_concurrency: number
}
