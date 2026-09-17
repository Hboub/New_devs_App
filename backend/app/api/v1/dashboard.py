from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.core.auth import authenticate_request as get_current_user
from app.core.database_pool import db_pool
from app.services.cache import get_revenue_summary

router = APIRouter()


def _require_tenant_id(current_user: Any) -> str:
    # FIX: the old code fell back to a shared "default_tenant" when the user had
    # no tenant. A missing tenant must be an error, never a shared bucket.
    if isinstance(current_user, dict):
        tenant_id = current_user.get("tenant_id")
    else:
        tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No client associated with this account")
    return tenant_id


@router.get("/dashboard/properties")
async def get_dashboard_properties(
    current_user: Any = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Only the signed-in client's properties (replaces the frontend's hardcoded list)."""
    tenant_id = _require_tenant_id(current_user)

    await db_pool.initialize()
    async with db_pool.get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, name, timezone FROM properties "
                "WHERE tenant_id = :tenant_id ORDER BY id"
            ),
            {"tenant_id": tenant_id},
        )
        return [dict(row) for row in result.mappings()]


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None, ge=2000, le=2100),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)

    if (month is None) != (year is None):
        raise HTTPException(status_code=422, detail="Provide month and year together")

    revenue_data = await get_revenue_summary(property_id, tenant_id, month, year)

    # The total is already rounded to cents with Decimal in the service, so this
    # float holds an exact 2-decimal value. The frontend should format it, not re-round it.
    return {
        "property_id": revenue_data["property_id"],
        "total_revenue": float(Decimal(revenue_data["total"])),
        "currency": revenue_data["currency"],
        "reservations_count": revenue_data["count"],
    }