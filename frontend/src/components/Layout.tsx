import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { fetchAlerts, fetchMe } from '../api/endpoints'
import { clearToken } from '../api/client'
import type { UserOut } from '../types'
import { SearchPalette } from './SearchPalette'

export function Layout() {
  const nav = useNavigate()
  const [unread,        setUnread]        = useState(0)
  const [user,          setUser]          = useState<UserOut | null>(null)
  const [searchOpen,    setSearchOpen]    = useState(false)

  useEffect(() => {
    fetchAlerts(false).then(a => setUnread(a.length)).catch(() => {})
    fetchMe().then(setUser).catch(() => {})
  }, [])

  // Ctrl+K (ou Cmd+K) abre a palette
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setSearchOpen(s => !s)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
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

        {/* Botão de pesquisa global */}
        <button className="search-trigger" onClick={() => setSearchOpen(true)}>
          <span>🔍 Pesquisar moedas…</span>
          <kbd>Ctrl+K</kbd>
        </button>

        <nav>
          <NavLink to="/" end>
            <span className="nav-icon">⬡</span> Scanner
          </NavLink>
          <NavLink to="/matrix">
            <span className="nav-icon">⚡</span> Matrix
          </NavLink>
          <NavLink to="/swing">
            <span className="nav-icon">📈</span> Swing
          </NavLink>
          <NavLink to="/intraday">
            <span className="nav-icon">⚡</span> Intraday
          </NavLink>
          <NavLink to="/strategy">
            <span className="nav-icon">🎯</span> Strategy
          </NavLink>
          <NavLink to="/risk">
            <span className="nav-icon">🛡️</span> Risk
          </NavLink>
          <NavLink to="/signals">
            <span className="nav-icon">📡</span> Sinais
          </NavLink>
          <NavLink to="/whales">
            <span className="nav-icon">🐳</span> Whales
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

      <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}
