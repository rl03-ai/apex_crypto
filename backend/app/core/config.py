from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Apex Crypto API'
    debug: bool = True
    secret_key: str = 'change-me-in-production'
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 dias

    database_url: str = 'sqlite:///./apex_crypto.db'

    # Mantemos como string para evitar o JSON-parsing automático do pydantic-settings.
    # O split CSV é feito em allowed_origins_list().
    allowed_origins: str = 'http://localhost:5173,http://localhost:5174'

    # CoinGecko
    coingecko_base_url: str = 'https://api.coingecko.com/api/v3'
    coingecko_api_key: str = ''

    # DefiLlama
    defillama_base_url: str = 'https://api.llama.fi'

    # Fear & Greed
    fear_greed_url: str = 'https://api.alternative.me/fng/'

    # Scheduler
    scheduler_enabled: bool = True
    alert_check_interval_minutes: int = 10
    portfolio_update_interval_minutes: int = 15

    def allowed_origins_list(self) -> List[str]:
        """Devolve allowed_origins como lista, suportando CSV ou JSON array."""
        v = (self.allowed_origins or '').strip()
        if not v:
            return []
        # Suporta tanto formato JSON `["a","b"]` como CSV `a,b`
        if v.startswith('['):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except json.JSONDecodeError:
                pass
        return [x.strip() for x in v.split(',') if x.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
