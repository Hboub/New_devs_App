from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import text

from app.core.database_pool import db_pool

CENTS = Decimal("0.01")


def _local_month_bounds(month: int, year: int) -> Tuple[datetime, datetime]:
    """
    Wall-clock boundaries [start, end) for a calendar month, with no timezone.
    The SQL query interprets them in each property's own timezone.
    """
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregates revenue for one property owned by one tenant.

    With month/year, a reservation counts toward the month of its check-in
    in the PROPERTY'S local timezone (e.g. 2024-02-29 23:30 UTC is March 1
    in Paris). Without them, all reservations are included.
    """
    params: Dict[str, Any] = {"property_id": property_id, "tenant_id": tenant_id}

    # FIX (timezone): the old monthly calculation used naive UTC month boundaries,
    # so late-evening bookings in UTC+ zones landed in the previous month.
    # Each boundary is converted separately with AT TIME ZONE, which also
    # handles daylight-saving changes within the month.
    # period_filter is a constant string (no user input), so the f-string is safe.
    period_filter = ""
    if month is not None and year is not None:
        params["start"], params["end"] = _local_month_bounds(month, year)
        period_filter = """
              AND r.check_in_date >= (CAST(:start AS timestamp) AT TIME ZONE p.timezone)
              AND r.check_in_date <  (CAST(:end   AS timestamp) AT TIME ZONE p.timezone)
        """

    # FIX (privacy): start from the properties table filtered by tenant, so a
    # property ID that belongs to another client returns 404 instead of data.
    query = text(
        f"""
        SELECT
            COALESCE(SUM(r.total_amount), 0) AS total_revenue,
            COUNT(r.id)                      AS reservation_count,
            COUNT(DISTINCT r.currency)       AS currency_count,
            MIN(r.currency)                  AS currency
        FROM properties p
        LEFT JOIN reservations r
               ON r.property_id = p.id
              AND r.tenant_id   = p.tenant_id
              {period_filter}
        WHERE p.id = :property_id
          AND p.tenant_id = :tenant_id
        GROUP BY p.id
        """
    )

    # FIX (fake data): one shared pool instead of a new pool per request, and no
    # try/except that returns hardcoded "mock" totals. If the database fails,
    # the request fails loudly and nothing wrong gets cached.
    await db_pool.initialize()
    async with db_pool.get_session() as session:
        result = await session.execute(query, params)
        row = result.one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Property not found")

    if row.currency_count > 1:
        # Adding EUR and USD together would produce a meaningless total.
        raise HTTPException(
            status_code=422,
            detail="Property has reservations in multiple currencies",
        )

    # FIX (cents): sum the exact NUMERIC values in Postgres, then round ONCE,
    # half-up, using Decimal. No float arithmetic touches the money.
    total = Decimal(str(row.total_revenue)).quantize(CENTS, rounding=ROUND_HALF_UP)

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(total),
        "currency": row.currency or "USD",
        "count": row.reservation_count,
    }