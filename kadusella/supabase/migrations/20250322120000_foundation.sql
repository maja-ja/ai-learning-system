-- Kadusella foundation: multi-tenant, pgvector, subscriptions, decode telemetry
-- Run after: Supabase project created. Adjust vector dimensions if you use a different embedder.

-- Extensions
create extension if not exists "pgcrypto";
create extension if not exists "vector";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
do $$ begin
  create type public.tenant_role as enum (
    'student',
    'teacher',
    'institution_admin',
    'platform_admin'
  );
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type public.decode_run_status as enum (
    'pending',
    'success',
    'failed'
  );
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type public.subscription_status as enum (
    'incomplete',
    'trialing',
    'active',
    'past_due',
    'canceled',
    'unpaid'
  );
exception
  when duplicate_object then null;
end $$;

-- ---------------------------------------------------------------------------
-- Identity helpers (Clerk subject = JWT "sub", via Supabase third-party JWT or custom claim)
-- ---------------------------------------------------------------------------
create or replace function public.current_clerk_subject()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select nullif((auth.jwt() ->> 'sub'), '');
$$;

comment on function public.current_clerk_subject() is
  'Returns Clerk user id from JWT sub when using Clerk-issued tokens with Supabase.';

create or replace function public.current_profile_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select p.id
  from public.profiles p
  where p.clerk_user_id = public.current_clerk_subject()
  limit 1;
$$;

-- ---------------------------------------------------------------------------
-- Tenants & membership
-- ---------------------------------------------------------------------------
create table if not exists public.tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text unique,
  clerk_org_id text unique,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.profiles (
  id uuid primary key default gen_random_uuid(),
  clerk_user_id text not null unique,
  email text,
  display_name text,
  avatar_url text,
  default_tenant_id uuid references public.tenants (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.tenant_members (
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid not null references public.profiles (id) on delete cascade,
  role public.tenant_role not null default 'student',
  created_at timestamptz not null default now(),
  primary key (tenant_id, profile_id)
);

create index if not exists tenant_members_profile_idx
  on public.tenant_members (profile_id);

-- ---------------------------------------------------------------------------
-- Etymon / decode corpus (12 core fields aligned with your Streamlit schema)
-- embedding: default 768-d for Google text-embedding-004; change migration if using OpenAI 1536-d
-- ---------------------------------------------------------------------------
create table if not exists public.etymon_entries (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  created_by uuid references public.profiles (id) on delete set null,
  word text not null,
  category text not null default '',
  roots text not null default '',
  breakdown text not null default '',
  definition text not null default '',
  meaning text not null default '',
  native_vibe text not null default '',
  example text not null default '',
  synonym_nuance text not null default '',
  usage_warning text not null default '',
  memory_hook text not null default '',
  phonetic text not null default '',
  model text,
  prompt_version text,
  content_tsv tsvector generated always as (
    to_tsvector(
      'simple',
      coalesce(word, '') || ' ' ||
      coalesce(category, '') || ' ' ||
      coalesce(definition, '') || ' ' ||
      coalesce(meaning, '') || ' ' ||
      coalesce(breakdown, '')
    )
  ) stored,
  embedding vector(768),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint etymon_word_nonempty check (length(trim(word)) > 0)
);

create unique index if not exists etymon_entries_tenant_word_lower
  on public.etymon_entries (tenant_id, lower(trim(word)));

create index if not exists etymon_entries_tenant_idx on public.etymon_entries (tenant_id);
create index if not exists etymon_entries_content_tsv_idx
  on public.etymon_entries using gin (content_tsv);

-- Approximate NN index (requires sufficient rows for ivfflat; replace with hnsw if enabled on your project)
create index if not exists etymon_entries_embedding_ivfflat
  on public.etymon_entries using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- ---------------------------------------------------------------------------
-- Decode runs (telemetry + audit)
-- ---------------------------------------------------------------------------
create table if not exists public.decode_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid references public.profiles (id) on delete set null,
  input_text text not null,
  primary_category text not null default '',
  auxiliary_categories text[] not null default '{}',
  model text,
  status public.decode_run_status not null default 'pending',
  error_message text,
  latency_ms integer,
  output_entry_id uuid references public.etymon_entries (id) on delete set null,
  raw_request jsonb,
  raw_response jsonb,
  created_at timestamptz not null default now()
);

create index if not exists decode_runs_tenant_created_idx
  on public.decode_runs (tenant_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Subscriptions (Stripe-shaped; you own billing webhooks in Next.js)
-- ---------------------------------------------------------------------------
create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  stripe_customer_id text,
  stripe_subscription_id text unique,
  plan_key text not null default 'free',
  status public.subscription_status not null default 'incomplete',
  trial_ends_at timestamptz,
  current_period_start timestamptz,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists subscriptions_tenant_idx on public.subscriptions (tenant_id);

create table if not exists public.subscription_events (
  id bigserial primary key,
  tenant_id uuid references public.tenants (id) on delete set null,
  stripe_event_id text unique,
  type text not null,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Usage / quota counters
-- ---------------------------------------------------------------------------
create table if not exists public.usage_events (
  id bigserial primary key,
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid references public.profiles (id) on delete set null,
  event_type text not null,
  units integer not null default 1,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists usage_events_tenant_created_idx
  on public.usage_events (tenant_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Feedback (replaces ad-hoc Sheet reporting)
-- ---------------------------------------------------------------------------
create table if not exists public.feedback_reports (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid references public.profiles (id) on delete set null,
  entry_id uuid references public.etymon_entries (id) on delete set null,
  status text not null default 'pending',
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- RAG chunks (optional finer-grained retrieval than whole-entry embedding)
-- ---------------------------------------------------------------------------
create table if not exists public.knowledge_chunks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  entry_id uuid references public.etymon_entries (id) on delete cascade,
  chunk_index integer not null default 0,
  content text not null,
  embedding vector(768),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists knowledge_chunks_tenant_idx on public.knowledge_chunks (tenant_id);
create index if not exists knowledge_chunks_embedding_ivfflat
  on public.knowledge_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- ---------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists tenants_updated_at on public.tenants;
create trigger tenants_updated_at
  before update on public.tenants
  for each row execute function public.set_updated_at();

drop trigger if exists profiles_updated_at on public.profiles;
create trigger profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

drop trigger if exists etymon_entries_updated_at on public.etymon_entries;
create trigger etymon_entries_updated_at
  before update on public.etymon_entries
  for each row execute function public.set_updated_at();

drop trigger if exists subscriptions_updated_at on public.subscriptions;
create trigger subscriptions_updated_at
  before update on public.subscriptions
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.tenants enable row level security;
alter table public.profiles enable row level security;
alter table public.tenant_members enable row level security;
alter table public.etymon_entries enable row level security;
alter table public.decode_runs enable row level security;
alter table public.subscriptions enable row level security;
alter table public.subscription_events enable row level security;
alter table public.usage_events enable row level security;
alter table public.feedback_reports enable row level security;
alter table public.knowledge_chunks enable row level security;

-- Profiles: user can read/update own row
create policy profiles_select_self on public.profiles
  for select using (clerk_user_id = public.current_clerk_subject());

create policy profiles_update_self on public.profiles
  for update using (clerk_user_id = public.current_clerk_subject());

create policy profiles_insert_self on public.profiles
  for insert with check (clerk_user_id = public.current_clerk_subject());

-- Tenants: visible if member
create policy tenants_select_member on public.tenants
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = tenants.id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

-- Tenant members: members of same tenant
create policy tenant_members_select on public.tenant_members
  for select using (
    exists (
      select 1 from public.tenant_members m2
      join public.profiles p on p.id = m2.profile_id
      where m2.tenant_id = tenant_members.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

-- Etymon entries: same-tenant members
create policy etymon_select on public.etymon_entries
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = etymon_entries.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy etymon_insert on public.etymon_entries
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = etymon_entries.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy etymon_update on public.etymon_entries
  for update using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = etymon_entries.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy etymon_delete on public.etymon_entries
  for delete using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = etymon_entries.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

-- Decode runs
create policy decode_runs_select on public.decode_runs
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = decode_runs.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy decode_runs_insert on public.decode_runs
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = decode_runs.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

-- Subscriptions: tenant members
create policy subscriptions_select on public.subscriptions
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = subscriptions.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

-- Usage & feedback
create policy usage_select on public.usage_events
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = usage_events.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy usage_insert on public.usage_events
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = usage_events.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy feedback_select on public.feedback_reports
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = feedback_reports.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy feedback_insert on public.feedback_reports
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on m.profile_id = p.id
      where m.tenant_id = feedback_reports.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

-- Knowledge chunks
create policy chunks_select on public.knowledge_chunks
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = knowledge_chunks.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy chunks_mutate on public.knowledge_chunks
  for all using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = knowledge_chunks.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

-- Subscription events: typically server-only; deny default client access
create policy subscription_events_deny on public.subscription_events
  for select using (false);

-- ---------------------------------------------------------------------------
-- Vector similarity (cosine distance operator <=>); RLS applies as invoker
-- ---------------------------------------------------------------------------
create or replace function public.match_etymon_entries (
  query_embedding vector(768),
  match_count integer default 8,
  p_tenant_id uuid default null
)
returns setof public.etymon_entries
language sql
stable
security invoker
set search_path = public
as $$
  select *
  from public.etymon_entries e
  where e.embedding is not null
    and (p_tenant_id is null or e.tenant_id = p_tenant_id)
  order by e.embedding <=> query_embedding
  limit least(greatest(match_count, 1), 50);
$$;

grant execute on function public.match_etymon_entries (vector, integer, uuid) to authenticated;
grant execute on function public.match_etymon_entries (vector, integer, uuid) to service_role;
