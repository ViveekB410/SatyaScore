import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth'
import { useHealth } from '@/lib/health'
import { cn } from '@/lib/utils'
import { Button } from './ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu'

function StatusPill() {
  const { status, indexSize } = useHealth()
  const dot =
    status === 'online' ? 'bg-flag-yes' : status === 'offline' ? 'bg-flag-no' : 'bg-muted animate-soft-pulse'
  const full =
    status === 'online'
      ? `Online · ${indexSize != null ? indexSize.toLocaleString() : '?'} passages`
      : status === 'offline'
        ? 'Offline'
        : 'Connecting…'
  const short = status === 'online' ? 'Online' : full
  return (
    <span
      className="inline-flex h-7 items-center gap-2 whitespace-nowrap rounded border border-rule bg-card px-2.5 text-[13px] text-muted"
      role="status"
      aria-label={`Analysis server: ${full}`}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', dot)} aria-hidden="true" />
      <span className="hidden sm:inline">{full}</span>
      <span className="sm:hidden">{short}</span>
    </span>
  )
}

function Account() {
  const { user, loading, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  if (loading) return <span className="h-7 w-16" aria-hidden="true" />
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    return (
      <Button asChild variant="outline" size="sm" className="h-7">
        <NavLink to={`/login?next=${next}`}>Sign in</NavLink>
      </Button>
    )
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-7 max-w-[10rem]" aria-label={`Account: ${user.name}`}>
          <span className="truncate">{user.name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>
          <span className="block font-medium text-ink">{user.name}</span>
          <span className="block truncate">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate('/history')}>Your history</DropdownMenuItem>
        <DropdownMenuItem
          onSelect={async () => {
            await signOut()
            toast.success('Signed out')
            navigate('/analyse')
          }}
        >
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'border-b-2 px-1 pb-1 pt-1.5 text-sm transition-colors',
    isActive ? 'border-navy font-medium text-navy' : 'border-transparent text-muted hover:text-navy',
  )

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-rule bg-paper">
        <div className="mx-auto grid max-w-[1040px] grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6 md:grid-cols-[1fr_auto_1fr]">
          <NavLink
            to="/analyse"
            className="col-start-1 row-start-1 justify-self-start font-serif text-[22px] font-semibold tracking-tight text-navy"
          >
            SatyaScore
          </NavLink>
          <nav
            aria-label="Main"
            className="col-span-2 col-start-1 row-start-2 flex gap-6 md:col-span-1 md:col-start-2 md:row-start-1 md:justify-self-center"
          >
            <NavLink to="/analyse" className={navClass}>
              Analyse
            </NavLink>
            <NavLink to="/history" className={navClass}>
              History
            </NavLink>
          </nav>
          <div className="col-start-2 row-start-1 flex items-center gap-2 justify-self-end md:col-start-3">
            <StatusPill />
            <Account />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1040px] flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <Outlet />
      </main>

      <footer className="border-t border-rule">
        <p className="mx-auto max-w-[1040px] px-4 py-5 text-[13px] italic text-muted sm:px-6">
          Research prototype. Verdicts are indicative, not authoritative.
        </p>
      </footer>
    </div>
  )
}
