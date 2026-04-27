import { Navigate, Route, Routes } from 'react-router-dom'
import { hasToken } from './api/client'
import { Layout } from './components/Layout'
import { DashboardPage }  from './pages/DashboardPage'
import { AssetPage }      from './pages/AssetPage'
import { WatchlistPage }  from './pages/WatchlistPage'
import { PortfolioPage }  from './pages/PortfolioPage'
import { AlertsPage }     from './pages/AlertsPage'
import { LoginPage }      from './pages/LoginPage'
import { SignalsPage }    from './pages/SignalsPage'
import { WhalesPage }     from './pages/WhalesPage'
import { MatrixPage }     from './pages/MatrixPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  return hasToken() ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route path="/" element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index                element={<DashboardPage />} />
        <Route path="asset/:id"     element={<AssetPage />} />
        <Route path="signals"       element={<SignalsPage />} />
        <Route path="whales"        element={<WhalesPage />} />
        <Route path="matrix"        element={<MatrixPage />} />
        <Route path="watchlist"     element={<WatchlistPage />} />
        <Route path="portfolio"     element={<PortfolioPage />} />
        <Route path="alerts"        element={<AlertsPage />} />
        <Route path="*"             element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
