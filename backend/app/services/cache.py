"""Cache TTL em memória para respostas do CoinGecko.

Os jobs e as rotas partilham a mesma instância do processo, por isso uma
chamada ao scanner não re-fetcha se o job já o fez há 2 minutos.

Não é thread-safe para escritas concorrentes complexas, mas para o
padrão "fetch-once-use-many" é suficiente e sem dependências extra.
"""
from __future__ import annotations

import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


# Instâncias partilhadas — importar directamente nos serviços
markets_cache   = TTLCache(ttl_seconds=90)    # top N moedas — 90 s
fear_greed_cache = TTLCache(ttl_seconds=600)  # Fear & Greed — 10 min
