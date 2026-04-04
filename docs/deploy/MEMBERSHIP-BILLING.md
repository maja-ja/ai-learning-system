# Membership, Billing, and Paid Generation

This rollout adds paid AI generation backed by `Clerk + Supabase`, with checkout handled by `kadusella/` and generation enforced by `FastAPI`.

## Environment Variables

### `web/`

- `VITE_CLERK_PUBLISHABLE_KEY`
- `VITE_BILLING_BASE_URL`
- `VITE_API_BASE_URL`

### `kadusella/`

- `CLERK_SECRET_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `MEMBERSHIP_TOKEN_SECRET`
- `WEB_APP_URL`
- `NEXT_PUBLIC_BILLING_BASE_URL`

#### Line Pay

- `LINE_PAY_CHANNEL_ID`
- `LINE_PAY_CHANNEL_SECRET`
- `LINE_PAY_ENV=sandbox|live`

#### PayPal

- `PAYPAL_CLIENT_ID`
- `PAYPAL_CLIENT_SECRET`
- `PAYPAL_ENV=sandbox|live`

### `backend/`

- `MEMBERSHIP_TOKEN_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`
- `AI_PROVIDER`

`MEMBERSHIP_TOKEN_SECRET` must match between `kadusella/` and `backend/`.

## Data Flow

1. User signs in from `web/` with Clerk.
2. `web/` calls `kadusella /api/auth/bootstrap`.
3. `kadusella/` ensures `profile`, `tenant`, `subscription`, and wallet state in Supabase.
4. `kadusella/` returns a short-lived membership token for FastAPI.
5. `web/` uses that token when calling `/decode`, `/api/decode/batch`, `/api/decode/suggest-topics`, and `/api/handout/generate`.
6. `backend/` verifies the token and consumes credits through Supabase RPC after successful generation.

## Database Rollout

Apply the new migration before enabling the frontend:

- `kadusella/supabase/migrations/202604010001_membership_billing_wallet.sql`

It adds:

- `billing_orders`
- `credit_ledger`
- provider columns on `subscriptions`
- RPC functions:
  - `current_credit_balance`
  - `has_generation_access`
  - `grant_checkout_credits`
  - `consume_generation_credit`

Then apply the app storage alignment migration:

- `kadusella/supabase/migrations/202604010002_app_storage_alignment.sql`

It adds / aligns:

- `member_storage`
- `click_events`
- segment columns on `aha_events` (`age_band`, `region_code`)
- Postgres helpers:
  - `aha_hook_effectiveness`
  - `predict_click_actions`
- `etymon_entries.status`
- `etymon_entries.source_member_storage_id`

## Database Source Of Truth

Use `Supabase/Postgres` as the system of record for:

- membership and tenant identity
- billing orders and credit ledger
- member storage
- learner contexts
- learning attempts
- aha hooks / aha events
- click tracking

Use `backend/local.db` only as:

- local development fallback
- offline cache for public knowledge export / demo flows
- emergency local backup when Supabase env vars are not configured

## Checkout Paths

- `POST /api/billing/checkout`
- `GET /api/billing/callback/linepay`
- `GET /api/billing/callback/paypal`

Pricing rule: `NT$5 per generation`. Purchase in packs (minimum NT$50 to cover payment processing fees):

| Pack key   | Amount | Generations |
|------------|--------|-------------|
| `pack_50`  | NT$50  | 10          |
| `pack_100` | NT$100 | 20 (recommended) |
| `pack_200` | NT$200 | 40          |

After credits are consumed, the member must purchase another pack. No recurring subscription.

## Contribution Modes

Decode and batch decode now support two output modes:

- `named_contribution`: save into the shared knowledge base
- `private_use`: keep the result in member storage without saving it publicly

## Verification Checklist

- Clerk sign-in works in `web/`
- `POST /api/auth/bootstrap` returns profile, wallet, and `backendToken`
- Line Pay sandbox can create a checkout and return to the app
- PayPal sandbox can create and capture an order
- successful payment increases `credit_ledger`
- successful generation decreases credits through `consume_generation_credit`
- unpaid users cannot trigger generation
- paid users can trigger all locked AI generation buttons

## Recommended Rollout

1. Apply the Supabase migration.
2. Apply the app storage alignment migration.
3. Configure Clerk and payment sandbox credentials.
4. Verify `kadusella/` checkout callbacks on sandbox.
5. Verify `web/` bootstrap and token handoff.
6. Verify `backend/` writes `member_storage`, `aha_events`, and `click_events` to Postgres.
7. Verify `backend/` credit consumption with sandbox payments.
8. Switch providers from sandbox to live after end-to-end verification.
