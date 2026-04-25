"""Fear & Greed Index — Alternative.me API pública."""
import httpx
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get('/fear-greed')
async def fear_greed() -> dict:
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            r = await client.get(f'{settings.fear_greed_url}?limit=1&format=json')
            r.raise_for_status()
            data = r.json()['data'][0]
            return {
                'value': int(data['value']),
                'label': data['value_classification'],  # 'Extreme Fear' … 'Extreme Greed'
                'timestamp': data['timestamp'],
            }
    except Exception:
        return {'value': 50, 'label': 'Neutral', 'timestamp': None}
