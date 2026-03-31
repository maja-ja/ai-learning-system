# Human Intervention Runbook

This runbook prepares manual maintenance workflows for the Aha pipeline and future advanced DB integration.

## 1) Enable maintenance access

Set environment variables on API server:

```bash
export MAINTENANCE_TOKEN="replace-with-long-random-token"
export DB_BACKEND="supabase"
# Optional future mode switch preparation
export POSTGRES_DSN="postgresql://user:pass@host:5432/dbname"
```

Without `MAINTENANCE_TOKEN`, all maintenance endpoints return `503` and stay disabled by design.

## 2) Secure endpoint checklist

- Only call maintenance endpoints over HTTPS.
- Keep `MAINTENANCE_TOKEN` in secret manager, not in repo.
- Rotate token after incident handling.
- Restrict access by firewall or reverse-proxy allowlist when possible.

## 3) Database readiness checks

Check runtime status:

```bash
curl -H "Authorization: Bearer $MAINTENANCE_TOKEN" \
  http://127.0.0.1:8000/api/admin/db/status
```

Expected response includes:

- `backend_mode`
- `supabase_ok`
- `postgres_dsn_configured`
- per-table row counts for Aha tables

## 4) Manual repair: backfill missing `hook_variant_id`

Dry run:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/aha/events/backfill-variant \
  -H "Authorization: Bearer $MAINTENANCE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"<tenant-uuid>","limit":500,"dry_run":true}'
```

Execute:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/aha/events/backfill-variant \
  -H "Authorization: Bearer $MAINTENANCE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"<tenant-uuid>","limit":500,"dry_run":false}'
```

Safety notes:

- Start with `dry_run=true`.
- Scope by `tenant_id` during incidents.
- Re-run analytics queries after backfill.

## 5) Incident pattern: recommendation quality drops

1. Run `/api/admin/db/status` and ensure `supabase_ok=true`.
2. Check if missing `hook_variant_id` increased.
3. Dry-run and execute backfill if needed.
4. Compare `aha_hook_effectiveness_view` before/after.
5. If still degraded, temporarily pin recommendation to `is_active=true` hooks with highest historic `aha_rate`.

## 6) Advanced DB migration preparation

Current write adapter is `supabase-rest`. For advanced Postgres path:

- Keep API contract unchanged.
- Implement `postgres` adapter behind `DB_BACKEND=postgres`.
- Run dual-write shadow phase (supabase + postgres) before cutover.
- Add reconciliation job for row-count and checksum parity.
