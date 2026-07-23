import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../features/auth/useAuth'

const navItems = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/filing-sessions', label: 'Filing Sessions', end: false },
]

/** Shared chrome for every authenticated page: a top bar with basic
 * navigation + logout, and the page content below via <Outlet/>. Mobile-
 * first: nav links wrap to a compact row rather than a sidebar, since the
 * primary target is a phone-width viewport (docs/PRODUCT_SCOPE.md). */
export function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b border-gray-200 dark:border-gray-800">
        <div className="mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <nav aria-label="Primary" className="flex flex-wrap gap-4">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `text-sm font-medium ${isActive ? 'text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-300'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            {user && <span className="hidden text-sm text-gray-500 sm:inline">{user.email}</span>}
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
