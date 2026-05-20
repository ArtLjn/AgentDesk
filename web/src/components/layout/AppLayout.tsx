import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@/components/ui/tooltip'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5000,
    },
  },
})

export function AppLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <div className="min-h-screen bg-background">
          <Sidebar />
          <main className="ml-56">
            <div className="p-6 max-w-[1400px] mx-auto">
              <Outlet />
            </div>
          </main>
        </div>
      </TooltipProvider>
    </QueryClientProvider>
  )
}
