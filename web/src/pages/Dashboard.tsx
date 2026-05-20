import { useAnalytics } from '@/hooks/useApi'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Ticket,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Clock,
  Zap,
  ThumbsUp,
} from 'lucide-react'
import {
  PieChart, Pie, Cell, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'

const COLORS = ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#8b949e']

export function Dashboard() {
  const { data, isLoading } = useAnalytics()

  if (isLoading || !data) {
    return <DashboardSkeleton />
  }

  const stats = data.resolution_stats || {}
  const efficiency = data.efficiency || {}
  const evaluation = data.evaluation || {}
  const categoryDist = data.category_distribution || {}
  const dailyStats = data.daily_stats || []

  const pieData = Object.entries(categoryDist).map(([name, value]) => ({ name, value: value as number }))
  const barData = (dailyStats as any[]).map((d: any) => ({
    date: d.date?.slice(5) || '',
    total: d.total || 0,
    completed: d.completed || 0,
    failed: d.failed || 0,
  }))

  const statCards = [
    { label: '总工单', value: stats.total ?? 0, icon: Ticket, color: 'text-primary' },
    { label: '已完成', value: stats.completed ?? 0, icon: CheckCircle2, color: 'text-success' },
    { label: '失败', value: stats.failed ?? 0, icon: XCircle, color: 'text-destructive' },
    { label: '通过率', value: `${((stats.success_rate ?? 0) * 100).toFixed(0)}%`, icon: TrendingUp, color: 'text-warning' },
    { label: '平均耗时', value: `${(efficiency.avg_duration_seconds ?? 0).toFixed(1)}s`, icon: Clock, color: 'text-primary' },
    { label: '平均工具调用', value: `${(efficiency.avg_tool_calls ?? 0).toFixed(1)}`, icon: Zap, color: 'text-success' },
    { label: '满意度', value: `${((evaluation.satisfaction_rate ?? 0) * 100).toFixed(0)}%`, icon: ThumbsUp, color: 'text-warning' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Dashboard</h2>
        <p className="text-sm text-muted-foreground mt-1">多Agent工单处理系统总览</p>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        {statCards.map((card) => (
          <Card key={card.label} className="bg-card border-border">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{card.label}</p>
                  <p className={`text-2xl font-bold mt-1 ${card.color}`}>{card.value}</p>
                </div>
                <card.icon className={`w-8 h-8 ${card.color} opacity-20`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 图表 */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">分类分布</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" stroke="none">
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 6, fontSize: 12 }}
                    labelStyle={{ color: '#8b949e' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-3 mt-2">
              {pieData.map((item, i) => (
                <div key={item.name} className="flex items-center gap-1.5 text-xs">
                  <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                  <span className="text-muted-foreground">{item.name}</span>
                  <span className="text-foreground font-medium">{item.value}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">每日处理趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
                  <XAxis dataKey="date" stroke="#8b949e" fontSize={11} />
                  <YAxis stroke="#8b949e" fontSize={11} />
                  <Tooltip
                    contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 6, fontSize: 12 }}
                    labelStyle={{ color: '#8b949e' }}
                  />
                  <Bar dataKey="completed" fill="#3fb950" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="failed" fill="#f85149" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-40" />
      <div className="grid grid-cols-4 gap-4">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-lg" />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-72 rounded-lg" />
        <Skeleton className="h-72 rounded-lg" />
      </div>
    </div>
  )
}
