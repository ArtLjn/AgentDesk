import { CheckCircle2, AlertTriangle, Info, XCircle, X } from 'lucide-react'
import { useToastStore, type ToastKind } from '@/lib/toast'
import { cn } from '@/lib/utils'

const kindStyles: Record<ToastKind, { color: string; icon: typeof Info }> = {
  info: { color: 'text-primary', icon: Info },
  success: { color: 'text-success', icon: CheckCircle2 },
  warning: { color: 'text-warning', icon: AlertTriangle },
  error: { color: 'text-destructive', icon: XCircle },
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-[100] flex w-80 flex-col gap-2">
      {toasts.map((t) => {
        const style = kindStyles[t.kind]
        const Icon = style.icon
        return (
          <div
            key={t.id}
            className="rounded-lg border border-border bg-card p-3 shadow-md ring-1 ring-foreground/5"
          >
            <div className="flex items-start gap-2">
              <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', style.color)} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-tight">{t.title}</p>
                {t.description && (
                  <p className="mt-0.5 text-xs text-muted-foreground break-words">{t.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                className="text-muted-foreground hover:text-foreground transition-colors"
                aria-label="关闭"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
