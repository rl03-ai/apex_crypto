from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Apex Crypto API'
    debug: bool = True
    secret_key: str = 'change-me-in-production'
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 dias

    database_url: str = 'sqlite:///./apex_crypto.db'
    allowed_origins: List[str] = ['http://localhost:5173', 'http://localhost:5174']

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

    @field_validator('allowed_origins', mode='before')
    @classmethod
    def split_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
