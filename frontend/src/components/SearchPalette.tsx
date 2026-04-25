import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  searchCoins, addToWatchlist, fetchWatchlist, removeFromWatchlist,
} from '../api/endpoints'
import type { SearchResult, WatchlistEntry } from '../types'

interface Props {
  open: boolean
  onClose: () => void
}

export function SearchPalette({ open, onClose }: Props) {
  const nav = useNavigate()
  const [query,    setQuery]    = useState('')
  const [results,  setResults]  = useState<SearchResult[]>([])
  const [loading,  setLoading]  = useState(false)
  const [wl,       setWl]       = useState<WatchlistEntry[]>([])
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // Carregar watchlist ao abrir (para sabermos o que já está lá)
  useEffect(() => {
    if (open) {
      fetchWatchlist().then(setWl).catch(() => {})
      setTimeout(() => inputRef.current?.focus(), 50)
    } else {
      setQuery('')
      setResults([])
      setSelected(0)
    }
  }, [open])

  // Debounce 250ms na pesquisa
  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }
    setLoading(true)
    const t = setTimeout(() => {
      searchCoins(query, 12)
        .then(r => { setResults(r); setSelected(0) })
        .catch(() => setResults([]))
        .finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(t)
  }, [query])

  // Navegação por teclado
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelected(s => Math.min(s + 1, results.length - 1))
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelected(s => Math.max(s - 1, 0))
      }
      if (e.key === 'Enter' && results[selected]) {
        e.preventDefault()
        goTo(results[selected])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, results, selected])

  function goTo(coin: SearchResult) {
    onClose()
    nav(`/asset/${coin.id}`)
  }

  async function toggleWl(coin: SearchResult, ev: React.MouseEvent) {
    ev.stopPropagation()
    const existing = wl.find(e => e.coin_id === coin.id)
    if (existing) {
      await removeFromWatchlist(existing.id)
      setWl(prev => prev.filter(e => e.id !== existing.id))
    } else {
      const entry = await addToWatchlist(coin.id, coin.symbol, coin.name)
      setWl(prev => [...prev, entry])
    }
  }

  if (!open) return null

  const wlIds = new Set(wl.map(e => e.coin_id))

  return (
    <div className="palette-overlay" onClick={onClose}>
      <div className="palette" onClick={e => e.stopPropagation()}>
        <div className="palette-input-wrap">
          <span className="palette-icon">🔍</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Pesquisar moeda... (nome, símbolo, ex: ATOM)"
            className="palette-input"
          />
          <kbd className="palette-kbd">ESC</kbd>
        </div>

        <div className="palette-results">
          {loading && <p className="palette-empty">A pesquisar…</p>}

          {!loading && query && results.length === 0 && (
            <p className="palette-empty">Sem resultados para "{query}"</p>
          )}

          {!loading && !query && (
            <p className="palette-empty">
              Escreve para pesquisar mais de 13.000 moedas.
              Usa <kbd className="palette-kbd">↑↓</kbd> para navegar,
              <kbd className="palette-kbd">⏎</kbd> para abrir.
            </p>
          )}

          {results.map((r, i) => {
            const starred = wlIds.has(r.id)
            return (
              <div
                key={r.id}
                className={`palette-row ${i === selected ? 'selected' : ''}`}
                onClick={() => goTo(r)}
                onMouseEnter={() => setSelected(i)}
              >
                {r.thumb
                  ? <img src={r.thumb} alt={r.symbol} className="palette-thumb" />
                  : <div className="palette-thumb palette-thumb-fallback">{r.symbol[0]}</div>}
                <div className="palette-row-text">
                  <strong>{r.name}</strong>
                  <small>{r.symbol}{r.market_cap_rank ? ` · #${r.market_cap_rank}` : ''}</small>
                </div>
                <button
                  className={`palette-star ${starred ? 'starred' : ''}`}
                  onClick={ev => toggleWl(r, ev)}
                  title={starred ? 'Remover da watchlist' : 'Adicionar à watchlist'}
                >
                  {starred ? '★' : '☆'}
                </button>
              </div>
            )
          })}
        </div>

        <div className="palette-footer">
          <small>Powered by CoinGecko</small>
        </div>
      </div>
    </div>
  )
}
