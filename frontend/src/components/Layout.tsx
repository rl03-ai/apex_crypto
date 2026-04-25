import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { fetchAlerts, fetchMe } from '../api/endpoints'
import { clearToken } from '../api/client'
import type { UserOut } from '../types'

export function Layout() {
  const nav = useNavigate()
  const [unread, setUnread] = useState(0)
  const [user,   setUser]   = useState<UserOut | null>(null)

  useEffect(() => {
    fetchAlerts(false).then(a => setUnread(a.length)).catch(() => {})
    fetchMe().then(setUser).catch(() => {})
  }, [])

  function handleLogout() {
    clearToken()
    nav('/login', { replace: true })
  }

  return (
    <div>
      <aside className="sidebar">
        <div className="brand">
          <span className="orb">₿</span>
          <div>
            <strong>Apex Crypto</strong>
            <small>trading dashboard</small>
          </div>
        </div>

        <nav>
          <NavLink to="/" end>
            <span className="nav-icon">⬡</span> Scanner
          </NavLink>
          <NavLink to="/watchlist">
            <span className="nav-icon">★</span> Watchlist
          </NavLink>
          <NavLink to="/portfolio">
            <span className="nav-icon">◈</span> Portfolio
          </NavLink>
          <NavLink to="/alerts">
            <span className="nav-icon">◎</span> Alertas
            {unread > 0 && <span className="badge">{unread}</span>}
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          {user && (
            <div className="user-chip">
              <div className="user-info">
                <strong>{user.name}</strong>
                <small>{user.email}</small>
              </div>
              <button className="logout-btn" onClick={handleLogout} title="Terminar sessão">⏻</button>
            </div>
          )}
          <small style={{ color: '#4d6280' }}>Dados: CoinGecko · DefiLlama</small>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
