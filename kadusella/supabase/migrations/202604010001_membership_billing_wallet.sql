-- Membership billing wallet: provider-agnostic orders + credit ledger + RPC helpers

do $$ begin
  create type public.billing_provider as enum ('linepay', 'paypal');
exception
  when duplicate_object then null;
end $$;

alter table if exists public.subscriptions
  add column if not exists provider public.billing_provider,
  add column if not exists provider_customer_id text,
  add column if not exists provider_subscription_id text,
  add column if not exists last_order_id uuid,
  add column if not exists last_payment_at timestamptz;

create table if not exists public.billing_orders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid references public.profiles (id) on delete set null,
  provider public.billing_provider not null,
  provider_order_id text,
  provider_transaction_id text,
  provider_payment_id text,
  pack_key text not null,
  amount_minor integer not null,
  currency text not null default 'TWD',
  credits integer not null default 0,
  status text not null default 'created',
  checkout_url text,
  approval_token text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists billing_orders_provider_order_uidx
  on public.billing_orders (provider, provider_order_id)
  where provider_order_id is not null;

create index if not exists billing_orders_tenant_created_idx
  on public.billing_orders (tenant_id, created_at desc);

create table if not exists public.credit_ledger (
  id bigserial primary key,
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid references public.profiles (id) on delete set null,
  order_id uuid references public.billing_orders (id) on delete set null,
  request_id text,
  delta_credits integer not null,
  reason text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create unique index if not exists credit_ledger_request_uidx
  on public.credit_ledger (request_id)
  where request_id is not null;

create unique index if not exists credit_ledger_order_checkout_uidx
  on public.credit_ledger (order_id)
  where order_id is not null and reason = 'checkout_grant';

create index if not exists credit_ledger_tenant_created_idx
  on public.credit_ledger (tenant_id, created_at desc);

create or replace function public.current_credit_balance(p_tenant_id uuid)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(sum(delta_credits), 0)::integer
  from public.credit_ledger
  where tenant_id = p_tenant_id;
$$;

create or replace function public.has_generation_access(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select
    (
      exists (
        select 1
        from public.subscriptions s
        where s.tenant_id = p_tenant_id
          and s.status in ('active', 'trialing')
          and (
            s.current_period_end is null
            or s.current_period_end > now()
          )
      )
      or public.current_credit_balance(p_tenant_id) > 0
    );
$$;

create or replace function public.grant_checkout_credits(
  p_tenant_id uuid,
  p_profile_id uuid,
  p_order_id uuid,
  p_credits integer,
  p_metadata jsonb default '{}'::jsonb
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  existing_balance integer;
begin
  if exists (
    select 1
    from public.credit_ledger
    where order_id = p_order_id
      and reason = 'checkout_grant'
  ) then
    return public.current_credit_balance(p_tenant_id);
  end if;

  insert into public.credit_ledger (
    tenant_id,
    profile_id,
    order_id,
    delta_credits,
    reason,
    metadata
  )
  values (
    p_tenant_id,
    p_profile_id,
    p_order_id,
    greatest(p_credits, 0),
    'checkout_grant',
    coalesce(p_metadata, '{}'::jsonb)
  );

  update public.billing_orders
  set status = 'paid',
      updated_at = now()
  where id = p_order_id;

  update public.subscriptions
  set last_order_id = p_order_id,
      last_payment_at = now(),
      updated_at = now()
  where tenant_id = p_tenant_id
    and id in (
      select id
      from public.subscriptions
      where tenant_id = p_tenant_id
      order by updated_at desc
      limit 1
    );

  existing_balance := public.current_credit_balance(p_tenant_id);
  return existing_balance;
end;
$$;

create or replace function public.consume_generation_credit(
  p_tenant_id uuid,
  p_profile_id uuid,
  p_request_id text,
  p_units integer default 1,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  normalized_units integer := greatest(coalesce(p_units, 1), 1);
  balance integer := public.current_credit_balance(p_tenant_id);
  existing jsonb;
begin
  if p_request_id is not null then
    select jsonb_build_object(
      'ok', true,
      'remaining', balance,
      'mode', 'idempotent'
    )
    into existing
    from public.credit_ledger
    where request_id = p_request_id
    limit 1;

    if existing is not null then
      return existing;
    end if;
  end if;

  if exists (
    select 1
    from public.subscriptions s
    where s.tenant_id = p_tenant_id
      and s.status in ('active', 'trialing')
      and (
        s.current_period_end is null
        or s.current_period_end > now()
      )
  ) then
    insert into public.usage_events (
      tenant_id,
      profile_id,
      event_type,
      units,
      metadata
    )
    values (
      p_tenant_id,
      p_profile_id,
      'generation_request',
      normalized_units,
      coalesce(p_metadata, '{}'::jsonb)
    );

    return jsonb_build_object(
      'ok', true,
      'remaining', balance,
      'mode', 'subscription'
    );
  end if;

  if balance < normalized_units then
    return jsonb_build_object(
      'ok', false,
      'remaining', balance,
      'mode', 'credits'
    );
  end if;

  insert into public.credit_ledger (
    tenant_id,
    profile_id,
    request_id,
    delta_credits,
    reason,
    metadata
  )
  values (
    p_tenant_id,
    p_profile_id,
    p_request_id,
    normalized_units * -1,
    'generation_consume',
    coalesce(p_metadata, '{}'::jsonb)
  );

  insert into public.usage_events (
    tenant_id,
    profile_id,
    event_type,
    units,
    metadata
  )
  values (
    p_tenant_id,
    p_profile_id,
    'generation_request',
    normalized_units,
    coalesce(p_metadata, '{}'::jsonb)
  );

  balance := public.current_credit_balance(p_tenant_id);
  return jsonb_build_object(
    'ok', true,
    'remaining', balance,
    'mode', 'credits'
  );
end;
$$;
