# Correções aplicadas

## Backend

### 1. Compatibilidade `phase` / `stage` na Matrix
- `backend/app/services/stage_detector.py`
- O detector continua a devolver `phase` em PT (`ACUMULACAO`, `MANIPULACAO`, `DISTRIBUICAO`, `CHOP`).
- Agora também devolve `stage` e `stage_label`, usados pelo frontend e por endpoints antigos.
- Isto evita `KeyError: 'stage'` em `/matrix`, `/risk/position-size` e `/strategy`.

### 2. Estatísticas defensivas em `/matrix`
- `backend/app/api/routes/decision_matrix.py`
- Os contadores `accumulating`, `early_markup` e `extended` deixam de aceder diretamente a `r['stage_1d']['stage']`.
- Agora suportam dados novos com `stage` e dados antigos/cached apenas com `phase`.

### 3. Compatibilidade `phase` / `stage` no Swing
- `backend/app/services/swing_detector.py`
- O detector continua a devolver `phase`, mas agora também devolve:
  - `BREAKOUT`
  - `PULLBACK`
  - `MOMENTUM`
  - `REVERSAL`
  - `EXHAUSTION`
  - `NO_SETUP`
- Isto corrige filtros, badges e estatísticas da página Swing.

### 4. Estatísticas e filtros em `/swing`
- `backend/app/api/routes/swing.py`
- O filtro `stage=` e os contadores passaram a usar `swing.stage` em vez de `swing.phase`.

### 5. CORS por variável de ambiente
- `backend/app/main.py`
- O backend passa a usar `settings.allowed_origins_list()` em vez de origins hardcoded.
- Mantém fallbacks locais para desenvolvimento:
  - `localhost:5173`
  - `localhost:5174`
  - `localhost:3000`
  - `127.0.0.1:5173`

### 6. Phase strength com dados reais
- `backend/app/services/decision_matrix.py`
- `backend/app/services/swing_matrix.py`
- `apply_phase_strength()` passa a receber métricas reais do timeframe primário em `result['primary']`.
- Antes, muitas métricas caíam em defaults neutros, podendo gerar força de fase incorreta.

### 7. Proteção contra divisão por zero no Swing
- `backend/app/services/swing_matrix.py`
- O cálculo de stops só é feito se `price > 0`.

## Validação feita

- `python -m compileall app` executado com sucesso no backend.
- Teste rápido aos detectores confirmou que `stage` e `stage_label` são devolvidos corretamente.

## Nota

O build do frontend não foi concluído neste ambiente porque o ZIP não vinha com `node_modules` instalado. O erro foi de dependências ausentes (`react`, `react-router-dom`, etc.), não das alterações efetuadas. Em ambiente local/Render, executar primeiro:

```bash
cd frontend
npm install
npm run build
```
