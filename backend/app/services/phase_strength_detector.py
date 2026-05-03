"""Phase Strength Detector — Mede saúde da fase + próxima transição.

Cada fase tem "força" (0-100):
  0-33:   Fraca — prestes a mudar
  34-66:  Moderada — estabelecida
  67-100: Forte — confirmada

Também detecta sinais de próxima fase:
  ACCUM → MANIP: Vol burst, squeeze release, RSI cross 55
  MANIP → DIST: RSI>75, funding extremo, dist_ma crescendo
  DIST → CHOP/ACCUM: RSI oversold, vol contração
"""
import logging

log = logging.getLogger(__name__)


class PhaseStrength:
    """Mede força da fase actual + próxima transição."""
    
    @staticmethod
    def calculate_phase_strength(
        phase: str,
        rsi: float,
        vol_burst: bool,
        squeeze_release: bool,
        atr_pct: float,
        change_24h_pct: float,
        price_change_7d_pct: float,
        dist_ma21_pct: float,
        struct_bias: int,
        above_vwap: bool,
        aligned_bull: bool,
        macd_bullish: bool,
    ) -> dict:
        """Calculate phase strength (0-100) + transition signals.
        
        Returns:
            {
                'phase': 'ACUMULACAO' | 'MANIPULACAO' | 'DISTRIBUICAO' | 'CHOP',
                'strength': int (0-100),
                'strength_description': 'Fraca' | 'Moderada' | 'Forte',
                'next_phase': probable next phase,
                'transition_probability': float (0-1),
                'momentum_index': float (-1 a +1, velocity of change),
                'exhaustion_signals': int (count of warning flags),
                'transition_signals': [list of early warnings],
                'time_in_phase': estimated duration,
                'recommendation': action text,
            }
        """
        
        strength = 50  # Base
        signals = []
        momentum = 0
        
        # ════════════════════════════════════════════════════════════════════════
        # ACUMULAÇÃO strength metrics
        # ════════════════════════════════════════════════════════════════════════
        
        if phase == 'ACUMULACAO':
            # Força: estrutura bull estabelecida
            if struct_bias == 1:
                strength += 15
            if above_vwap:
                strength += 10
            if aligned_bull:
                strength += 10
            
            # Momentum: está acelerando ou ainda lateral?
            if vol_burst:
                strength -= 10  # Vol burst = transição para MANIP
                momentum = 0.7
                signals.append('💥 Vol burst — transição para MANIPULAÇÃO iminente')
            elif squeeze_release:
                strength -= 5
                momentum = 0.5
                signals.append('🔓 Squeeze release — setup para aceleração')
            elif atr_pct < 1.5:
                strength += 5
                momentum = -0.3
                signals.append('⚪ Low vol — ainda lateral, acumulação saudável')
            
            # RSI position in phase
            if 40 <= rsi <= 50:
                strength += 5  # Perfeito para acumulação
            elif rsi > 60:
                strength -= 10
                signals.append(f'🔺 RSI {rsi:.0f} alto para acumulação — próxima é MANIP')
                momentum = 0.6
            elif rsi < 35:
                strength -= 5
                signals.append(f'🔻 RSI {rsi:.0f} low — oversold reversal zone')
                momentum = 0.2
            
            # Próxima fase
            next_phase = 'MANIPULACAO' if momentum > 0.5 else 'ACUMULACAO'
            transition_prob = min(0.9, momentum + 0.3) if momentum > 0 else 0.1
        
        # ════════════════════════════════════════════════════════════════════════
        # MANIPULAÇÃO strength metrics
        # ════════════════════════════════════════════════════════════════════════
        
        elif phase == 'MANIPULACAO':
            # Força: trending confirmed
            if vol_burst:
                strength += 15
            if macd_bullish:
                strength += 10
            if aligned_bull:
                strength += 10
            if above_vwap:
                strength += 5
            
            # Momentum: acelerando ou desacelerando?
            if 60 <= rsi <= 75:
                strength += 10
                momentum = 0.4  # Still healthy
                signals.append(f'📈 RSI {rsi:.0f} — trending healthy')
            elif rsi > 78:
                strength -= 20
                momentum = -0.7  # Prepare for distribution
                signals.append(f'⚠️ RSI {rsi:.0f} extremo — distribution coming')
            elif rsi < 55:
                strength -= 15
                momentum = -0.5
                signals.append(f'🔻 RSI {rsi:.0f} falling — momentum lost')
            
            # Distance from MA21 growing = healthy trend
            if dist_ma21_pct > 5:
                strength += 5
                if dist_ma21_pct > 8:
                    strength -= 10
                    signals.append(f'📊 {dist_ma21_pct:.1f}% above MA21 — extended, be careful')
                    momentum = -0.4
            
            # Vol sustainability
            if atr_pct > 6:
                strength -= 10
                signals.append(f'💨 ATR {atr_pct:.1f}% extreme — likely blow-off')
                momentum = -0.6
            
            next_phase = 'DISTRIBUICAO' if momentum < -0.4 else 'MANIPULACAO'
            transition_prob = min(0.9, max(0, -momentum))
        
        # ════════════════════════════════════════════════════════════════════════
        # DISTRIBUIÇÃO strength metrics
        # ════════════════════════════════════════════════════════════════════════
        
        elif phase == 'DISTRIBUICAO':
            # Força: como estabelecida está a distribuição?
            if rsi > 75:
                strength += 20
            if atr_pct > 5 or abs(price_change_7d_pct) > 20:
                strength += 15  # Vol blow-off confirms
            if dist_ma21_pct > 7:
                strength += 10  # Extended confirms
            
            # Momentum: reversal coming?
            exhaustion_count = 0
            if rsi > 80:
                exhaustion_count += 1
            if atr_pct > 8:
                exhaustion_count += 1
            if abs(price_change_7d_pct) > 25:
                exhaustion_count += 1
            
            if exhaustion_count >= 2:
                momentum = -0.8
                signals.append('⛔ Multi-exhaustion — reversal likely')
            else:
                momentum = -0.4
                signals.append('⚠️ Distribuição estabelecida')
            
            next_phase = 'CHOP' if exhaustion_count >= 2 else 'DISTRIBUICAO'
            transition_prob = exhaustion_count / 3.0
        
        # ════════════════════════════════════════════════════════════════════════
        # CHOP strength metrics
        # ════════════════════════════════════════════════════════════════════════
        
        else:  # CHOP
            if 45 <= rsi <= 55:
                strength += 10
            if atr_pct < 2:
                strength += 5
            
            # Next phase prediction
            if struct_bias == 1 and above_vwap:
                next_phase = 'ACUMULACAO'
                transition_prob = 0.4
                momentum = 0.3
                signals.append('🔄 Struct bull + above VWAP — pode entrar ACCUM')
            elif struct_bias == -1:
                next_phase = 'DISTRIBUICAO'
                transition_prob = 0.5
                momentum = -0.3
                signals.append('⛔ Struct bear — pode descer para DIST')
            else:
                next_phase = 'CHOP'
                transition_prob = 0.2
                momentum = 0
                signals.append('⚪ Consolidação pura, wait')
        
        # Cap strength
        strength = max(0, min(100, strength))
        
        # Strength description
        if strength < 33:
            strength_desc = '🔴 Fraca (mudança iminente)'
        elif strength < 67:
            strength_desc = '🟡 Moderada (estabelecida)'
        else:
            strength_desc = '🟢 Forte (confirmada)'
        
        # Time estimate (rough based on strength)
        if strength > 70:
            time_estimate = '2-5 dias ainda'
        elif strength > 40:
            time_estimate = '1-2 dias'
        else:
            time_estimate = 'Horas a 1 dia'
        
        # Recommendation
        if momentum > 0.5:
            rec = '🚀 Aceleração — aumentar posição ou entrar'
        elif momentum < -0.5:
            rec = '⚠️ Desaceleração — reduzir ou sair'
        else:
            rec = '⏸️ Consolidando — manter ou aguardar sinais'
        
        return {
            'phase': phase,
            'strength': strength,
            'strength_description': strength_desc,
            'next_phase': next_phase,
            'transition_probability': round(transition_prob, 2),
            'momentum_index': round(momentum, 2),
            'transition_signals': signals,
            'time_in_phase_estimate': time_estimate,
            'recommendation': rec,
        }


def apply_phase_strength(row: dict) -> dict:
    """Apply phase strength analysis to a row."""
    if not row or 'phase' not in row:
        return row
    
    strength_analysis = PhaseStrength.calculate_phase_strength(
        phase=row.get('phase', 'CHOP'),
        rsi=row.get('primary', {}).get('rsi', 50) if isinstance(row.get('primary'), dict) else row.get('rsi', 50),
        vol_burst=row.get('primary', {}).get('vol_burst', False) if isinstance(row.get('primary'), dict) else row.get('vol_burst', False),
        squeeze_release=row.get('primary', {}).get('squeeze_release', False) if isinstance(row.get('primary'), dict) else row.get('squeeze_release', False),
        atr_pct=row.get('primary', {}).get('atr_pct', 1.5) if isinstance(row.get('primary'), dict) else row.get('atr_pct', 1.5),
        change_24h_pct=row.get('primary', {}).get('change_24h_pct', 0) if isinstance(row.get('primary'), dict) else row.get('change_24h_pct', 0),
        price_change_7d_pct=row.get('primary', {}).get('price_change_7d_pct', 0) if isinstance(row.get('primary'), dict) else row.get('price_change_7d_pct', 0),
        dist_ma21_pct=row.get('primary', {}).get('dist_ma21_pct', 0) if isinstance(row.get('primary'), dict) else row.get('dist_ma21_pct', 0),
        struct_bias=row.get('primary', {}).get('struct_bias', 0) if isinstance(row.get('primary'), dict) else row.get('struct_bias', 0),
        above_vwap=row.get('primary', {}).get('above_vwap', False) if isinstance(row.get('primary'), dict) else row.get('above_vwap', False),
        aligned_bull=row.get('primary', {}).get('aligned_bull', False) if isinstance(row.get('primary'), dict) else row.get('aligned_bull', False),
        macd_bullish=row.get('primary', {}).get('macd_bullish', False) if isinstance(row.get('primary'), dict) else row.get('macd_bullish', False),
    )
    
    row['phase_strength'] = strength_analysis['strength']
    row['phase_health'] = strength_analysis['strength_description']
    row['next_phase'] = strength_analysis['next_phase']
    row['transition_probability'] = strength_analysis['transition_probability']
    row['momentum_index'] = strength_analysis['momentum_index']
    row['transition_signals'] = strength_analysis['transition_signals']
    row['phase_duration_estimate'] = strength_analysis['time_in_phase_estimate']
    row['recommendation'] = strength_analysis['recommendation']
    
    return row
