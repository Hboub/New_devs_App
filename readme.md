# Property Revenue Dashboard — debugging notes

Five bugs were found and fixed. The first one masked the other four, so it had to be fixed before anything else could be confirmed.

## 1. Fake data instead of real totals

Four faults broke the database pool: it built its URL from `settings.supabase_db_*` fields that don't exist here, passed the synchronous `QueuePool` to an async engine, declared `get_session` as `async def` where callers used `async with`, and created a new pool on every request. A `try/except` swallowed all of it and returned a hardcoded `mock_data` dictionary with a 200 response, so invented totals looked like real ones.

**Fix:** connect via `DATABASE_URL` with one shared async pool, and delete the fallback so database failures fail loudly.

## 2. One client seeing another's revenue

The cache key was `revenue:{property_id}`, and both clients own a `prop-001`, so whichever client loaded it first filled the cache for everyone. The property dropdown was a hardcoded list of all five properties, and the revenue query never checked that the property belonged to the caller.

**Fix:** cache keys now carry client, property and period under a `v2` namespace; the dropdown loads from a new tenant-scoped endpoint; a foreign property ID returns 404.

## 3. The browser choosing its own client identity

The revenue card sent an `X-Simulated-Tenant` header, which anyone can edit in DevTools.

**Fix:** removed. The client comes from the verified token only. This still needs the matching server-side fix in `core/auth.py`.

## 4. March counted in UTC

Month boundaries were naive datetimes. A Paris booking at `2024-02-29 23:30 UTC` is March 1 locally, so its 1,250.00 vanished from March, leaving exactly the 1,000.00 / 3 that appeared on screen.

**Fix:** convert each boundary separately with `AT TIME ZONE p.timezone`, so daylight saving is handled too.

## 5. Cents drifting

Three-decimal amounts became floats and were re-rounded in the browser with `Math.round(x * 100) / 100`. In JavaScript, `1.005 * 100` is `100.49999999999999`, so a cent disappears.

**Fix:** sum the exact values in Postgres, round once with `Decimal` and `ROUND_HALF_UP`, and let the card only format.

## Also fixed

A missing tenant no longer falls back to a shared `default_tenant` (now 403). Mixed currencies are rejected rather than added together. Stale responses can no longer overwrite newer ones when switching properties. A hardcoded "+12%" trend badge, calculated from nothing, is gone.

## Files changed

```
backend/app/core/database_pool.py
backend/app/services/reservations.py
backend/app/services/cache.py
backend/app/api/v1/dashboard.py
frontend/src/components/Dashboard.tsx
frontend/src/components/RevenueSummary.tsx
frontend/src/lib/secureApi.ts
```

## Expected results

Computed from `database/seed.sql`. All seeded bookings fall in local March 2024, so February is empty and the March totals match the all-time totals.

| Client | Property | Revenue | Bookings |
| --- | --- | --- | --- |
| Sunset | prop-001 Beach House Alpha | 2,250.00 | 4 |
| Sunset | prop-002 City Apartment Downtown | 4,975.50 | 4 |
| Sunset | prop-003 Country Villa Estate | 6,100.50 | 2 |
| Ocean | prop-001 Mountain Lodge Beta | 0.00 | 0 |
| Ocean | prop-004 Lakeside Cottage | 1,776.50 | 4 |
| Ocean | prop-005 Urban Loft Modern | 3,256.00 | 3 |

## Verify

```bash
docker compose up --build   # or: podman compose up --build
```

Sign in as each client at http://localhost:3000 and check that the totals match the table, that each dropdown lists only that client's three properties, and that Sunset's Beach House shows 2,250.00 in March 2024 and 0.00 in February 2024.

```bash
# separate cache entries per client
docker compose exec redis redis-cli KEYS "revenue:*"

# another client's property is not readable
curl -s -i -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/dashboard/summary?property_id=prop-002"   # 404 as Ocean
```

## Open item

`backend/app/core/auth.py` decides which client a request belongs to and has not been reviewed. Until it is, a hand-crafted request may still be able to claim another client's identity. The schema also enables row-level security without defining any policies, and the app connects as the `postgres` superuser, which bypasses it, so client isolation currently rests entirely on application code.