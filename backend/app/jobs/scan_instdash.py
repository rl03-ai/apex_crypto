"""Job: scan_instdash — análise periódica do universo Binance.

Para cada moeda do scan_universe:
  1. Corre analyse_symbol no LTF (1d) e HTF (1w)
  2. Detecta sinais accionáveis baseados na lógica Pine
  3. Cria entries na tabela Signal com deduplicação

Detectores que geram sinal accionável (conforme Pine alertcondition):

  ENTRADA:
    - LONG VALIDO: setup_quality == 'LONG valido' E score >= 8
    - SHORT VALIDO: setup_quality == 'SHORT valido' E score <= -8
    - SIGNAL BULL: aligned_bull E score >= 6
    - SIGNAL BEAR: aligned_bear E score <= -6
    - CHOCH BULL: estrutura
    - CHOCH BEAR: estrutura
    - SQUEEZE BULL: sq_end E score >= 3
    - SQUEEZE BEAR: sq_end E score <= -3

  SAIDA (gerados sempre que estas condições são detectadas):
    - SCORE FLIP: moeda no portfolio teve score >= +6 nas últimas 7 análises e agora está <= -3
    - CHOCH BEAR EM POSIÇÃO: utilizador tem long e CHoCH bear apareceu
    - SWEEP HIGH + SCORE NEG: distribuição em curso
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.portfolio import Position
from app.models.signal import Signal
from app.models.watchlist import WatchlistEntry
from app.services.binance import coingecko_id_to_binance_symbol, list_active_symbols
from app.services.instdash import analyse_symbol

log = logging.getLogger(__name__)

# Quantas moedas top scanar por execução. Mais = melhor cobertura, mais lento.
TOP_N_SCAN = 100

# Janela de deduplicação para sinais idênticos
DEDUP_HOURS = 12


# ─────────────────────────────────────────────────────────────────────────────

def _scan_universe(db: Session) -> set[str]:
    """Universo a scanar = top Binance + watchlist + portfolio (mapeados para Binance)."""
    universe: set[str] = set()

    # Adicionar coin_ids da watchlist e portfolio
    extras_ids: set[str] = set()
    for w in db.query(WatchlistEntry.coin_id).distinct():
        extras_ids.add(w[0])
    for p in db.query(Position.coin_id).filter(Position.status == 'open').distinct():
        extras_ids.add(p[0])

    for coin_id in extras_ids:
        sym = coingecko_id_to_binance_symbol(coin_id)
        if sym:
            universe.add(sym)

    return universe


async def _scan() -> dict:
    db = SessionLocal()
    stats = {'analysed': 0, 'signals_created': 0, 'errors': 0, 'deduped': 0}

    try:
        # Universo: top Binance por volume + watchlist + portfolio
        active = await list_active_symbols()
        top_symbols = [a['symbol'] for a in active[:TOP_N_SCAN]]
        extras = _scan_universe(db)

        scan_set = list(set(top_symbols) | extras)
        log.info('scan_instdash: a analisar %d moedas (top %d + %d extras)',
                 len(scan_set), TOP_N_SCAN, len(extras))

        for symbol in scan_set:
            try:
                analysis = await analyse_symbol(symbol, interval='1d', htf_interval='1w')
                if not analysis:
                    continue
                stats['analysed'] += 1

                # Detectar sinais a partir da análise
                signals = _detect_signals(analysis)
                for sig in signals:
                    if _create_signal(db, symbol, analysis, sig):
                        stats['signals_created'] += 1
                    else:
                        stats['deduped'] += 1

            except Exception as exc:
                log.warning('scan_instdash: erro em %s: %s', symbol, exc)
                stats['errors'] += 1

        if stats['signals_created'] > 0:
            db.commit()

    except Exception as exc:
        log.exception('scan_instdash: erro crítico — %s', exc)
        stats['errors'] += 1
    finally:
        db.close()

    log.info('scan_instdash: %s', stats)
    return stats


def _detect_signals(a: dict) -> list[dict]:
    """A partir da análise, devolve lista de sinais para criar.

    Cada sinal: {
      'direction': 'long'|'short'|'exit',
      'setup_type': str,          # tipo único (para deduplicação)
      'title': str,                # mostrado na UI
      'description': str,          # detalhes
    }
    """
    signals: list[dict] = []
    score = a['score']
    setup = a['setup_quality']
    bull = a['aligned_bull']
    bear = a['aligned_bear']
    struct = a['structure']

    # ── LONG VALIDO (sinal mais forte) ────────────────────────────────────────
    if setup == 'LONG valido' and score >= 8:
        signals.append({
            'direction': 'long', 'setup_type': 'long_valid',
            'title': f"{a['symbol']} · Setup LONG válido (score {score:+d})",
            'description': (
                f"Confluência completa: tendências alinhadas ({a['ltf_trend']}/{a['htf_trend']}), "
                f"estrutura {_struct_label(struct['struct_bias'])}, sem squeeze, próximo a suporte. "
                f"SL: {a['sl_long']:.4g} · TP: {a['tp_long']:.4g}"
            ),
        })

    # ── SHORT VALIDO ──────────────────────────────────────────────────────────
    if setup == 'SHORT valido' and score <= -8:
        signals.append({
            'direction': 'short', 'setup_type': 'short_valid',
            'title': f"{a['symbol']} · Setup SHORT válido (score {score:+d})",
            'description': (
                f"Confluência completa: tendências alinhadas ({a['ltf_trend']}/{a['htf_trend']}), "
                f"estrutura {_struct_label(struct['struct_bias'])}, próximo a resistência. "
                f"SL: {a['sl_short']:.4g} · TP: {a['tp_short']:.4g}"
            ),
        })

    # ── SIGNAL BULL CONFLUENTE (intermédio) ───────────────────────────────────
    if bull and score >= 6 and score < 8:
        signals.append({
            'direction': 'long', 'setup_type': 'signal_bull',
            'title': f"{a['symbol']} · Sinal BULL confluente (score {score:+d})",
            'description': f"Alinhamento HTF/LTF + score forte. Aguardar entrada em zona.",
        })

    # ── SIGNAL BEAR CONFLUENTE ────────────────────────────────────────────────
    if bear and score <= -6 and score > -8:
        signals.append({
            'direction': 'short', 'setup_type': 'signal_bear',
            'title': f"{a['symbol']} · Sinal BEAR confluente (score {score:+d})",
            'description': f"Alinhamento HTF/LTF + score forte. Aguardar entrada em zona.",
        })

    # ── ESTRUTURA: CHOCH/BOS detectado na última barra ────────────────────────
    if struct.get('choch_bull'):
        signals.append({
            'direction': 'long', 'setup_type': 'choch_bull',
            'title': f"{a['symbol']} · CHoCH Bullish",
            'description': "Mudança de carácter para bull. Estrutura virou.",
        })
    if struct.get('choch_bear'):
        signals.append({
            'direction': 'exit', 'setup_type': 'choch_bear',
            'title': f"{a['symbol']} · CHoCH Bearish — alerta de saída",
            'description': "Mudança de carácter para bear. Considera reduzir longs.",
        })
    if struct.get('bos_bull'):
        signals.append({
            'direction': 'long', 'setup_type': 'bos_bull',
            'title': f"{a['symbol']} · Break of Structure Bull",
            'description': "Continuação bullish confirmada por nova máxima.",
        })
    if struct.get('bos_bear'):
        signals.append({
            'direction': 'exit', 'setup_type': 'bos_bear',
            'title': f"{a['symbol']} · Break of Structure Bear",
            'description': "Continuação bearish. Atenção a longs abertos.",
        })

    # ── SAIDA: Sweep High com score negativo ──────────────────────────────────
    if a['liquidity']['sweep_high'] and score < 0:
        signals.append({
            'direction': 'exit', 'setup_type': 'sweep_high_distribution',
            'title': f"{a['symbol']} · Sweep High + score negativo",
            'description': (
                f"Liquidez varrida em {a['liquidity']['liq_high']:.4g} mas preço voltou abaixo. "
                "Sinal clássico de distribuição."
            ),
        })

    # ── SAIDA: VWAP rejection ─────────────────────────────────────────────────
    if a['vwap_ext_up'] and score < 5:
        signals.append({
            'direction': 'exit', 'setup_type': 'vwap_overextended',
            'title': f"{a['symbol']} · Sobre-extensão VWAP",
            'description': "Preço a >2σ acima do VWAP. Reversão à média provável.",
        })

    return signals


def _struct_label(bias: int) -> str:
    return 'bullish' if bias == 1 else ('bearish' if bias == -1 else 'neutra')


def _create_signal(db: Session, symbol: str, analysis: dict, sig_def: dict) -> bool:
    """Cria signal na DB se não houver duplicado nas últimas DEDUP_HOURS horas.
    Devolve True se criou, False se foi deduplicado."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_HOURS)

    existing = (
        db.query(Signal)
        .filter(
            Signal.symbol == symbol,
            Signal.setup_type == sig_def['setup_type'],
            Signal.detected_at >= cutoff,
        )
        .first()
    )
    if existing:
        return False

    sig = Signal(
        symbol=symbol,
        coin_id=None,  # Mapeamento reverso seria útil mas não crítico
        interval=analysis['interval'],
        direction=sig_def['direction'],
        setup_type=sig_def['setup_type'],
        score=analysis['score'],
        signal_label=analysis['signal'],
        price=analysis['price'],
        sl=analysis.get('sl_long' if sig_def['direction'] == 'long' else 'sl_short'),
        tp=analysis.get('tp_long' if sig_def['direction'] == 'long' else 'tp_short'),
        title=sig_def['title'],
        description=sig_def['description'],
        snapshot=json.dumps({
            'rsi': analysis['rsi'],
            'adx': analysis['adx'],
            'squeeze': analysis['squeeze'],
            'aligned_bull': analysis['aligned_bull'],
            'aligned_bear': analysis['aligned_bear'],
            'factors': analysis['factors'],
        })[:5000],
    )
    db.add(sig)

    # Criar Alert correspondente para todos os utilizadores que têm esta moeda em
    # watchlist ou portfolio (assim aparece no painel de alertas)
    _broadcast_to_users(db, symbol, sig_def, analysis)

    return True


def _broadcast_to_users(db: Session, symbol: str, sig_def: dict, analysis: dict) -> None:
    """Cria Alert nos utilizadores que tenham esta moeda em watchlist ou portfolio."""
    from app.services.binance import binance_symbol_to_base
    base = binance_symbol_to_base(symbol)

    user_ids: set[str] = set()
    # Utilizadores com esta moeda na watchlist (matching por symbol)
    for w in db.query(WatchlistEntry).filter(WatchlistEntry.symbol == base).all():
        user_ids.add(w.user_id)
    # Utilizadores com esta moeda no portfolio
    for p in db.query(Position).filter(Position.symbol == base, Position.status == 'open').all():
        # Buscar user via portfolio
        from app.models.portfolio import Portfolio as P
        portfolio = db.query(P).filter(P.id == p.portfolio_id).first()
        if portfolio:
            user_ids.add(portfolio.user_id)

    severity = 'critical' if sig_def['direction'] == 'exit' else 'warning'

    for uid in user_ids:
        alert = Alert(
            user_id=uid,
            alert_type='signal_' + sig_def['setup_type'],
            severity=severity,
            coin_id=base.lower(),
            title=sig_def['title'],
            message=sig_def['description'],
        )
        db.add(alert)


def run() -> dict:
    """Entry point síncrono para APScheduler."""
    return asyncio.run(_scan())
