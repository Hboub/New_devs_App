import json
import os
from typing import Any, Dict, Optional

import redis.asyncio as redis

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

CACHE_TTL_SECONDS = 300

# Bumping the version means old keys like "revenue:prop-001" (which may hold
# another client's numbers or fake data) are simply never read again.
CACHE_VERSION = "v2"


def _cache_key(
    tenant_id: str, property_id: str, month: Optional[int], year: Optional[int]
) -> str:
    period = f"{year:04d}-{month:02d}" if month is not None else "all"
    # tenant_id comes from the verified login and is always the first segment,
    # so one client's keys can never match another client's.
    return f"revenue:{CACHE_VERSION}:{tenant_id}:{property_id}:{period}"


async def get_revenue_summary(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    """
    # FIX: the key used to be f"revenue:{property_id}". Sunset and Ocean both
    # own a "prop-001", so whichever client loaded it first filled the cache
    # and the other client was served those numbers for the next 5 minutes.
    cache_key = _cache_key(tenant_id, property_id, month, year)

    # Try to get from cache
    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        # Defense in depth: never return an entry that belongs to someone else.
        if data.get("tenant_id") == tenant_id:
            return data

    # Revenue calculation is delegated to the reservation service.
    from app.services.reservations import calculate_total_revenue

    # Raises on errors, so failures are never cached.
    result = await calculate_total_revenue(property_id, tenant_id, month, year)

    await redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))

    return result