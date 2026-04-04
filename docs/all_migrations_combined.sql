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
-- Aha hook MVP schema (privacy-first: age_band + region_code)
-- Depends on foundation migration that creates tenants/profiles/tenant_members/set_updated_at()

-- ---------------------------------------------------------------------------
-- Core tables
-- ---------------------------------------------------------------------------
create table if not exists public.learner_contexts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid not null references public.profiles (id) on delete cascade,
  age_band text not null check (
    age_band in ('under_13', '13_15', '16_18', '19_22', '23_plus')
  ),
  region_code text not null,
  preferred_language text not null default 'zh-TW',
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, profile_id)
);

create index if not exists learner_contexts_tenant_profile_idx
  on public.learner_contexts (tenant_id, profile_id);


create table if not exists public.aha_hooks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  created_by uuid references public.profiles (id) on delete set null,
  topic_key text not null,
  hook_type text not null check (
    hook_type in ('analogy', 'story', 'visual', 'misconception_fix', 'exam_shortcut')
  ),
  hook_variant_id text not null default 'v1',
  hook_title text not null default '',
  hook_text text not null,
  difficulty_band text not null default 'basic' check (
    difficulty_band in ('basic', 'intermediate', 'advanced')
  ),
  region_tags text[] not null default '{}',
  age_tags text[] not null default '{}',
  is_active boolean not null default true,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, topic_key, hook_type, hook_variant_id)
);

create index if not exists aha_hooks_tenant_topic_active_idx
  on public.aha_hooks (tenant_id, topic_key, is_active);


create table if not exists public.learning_attempts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid not null references public.profiles (id) on delete cascade,
  topic_key text not null,
  source text not null default 'lab' check (
    source in ('lab', 'exam', 'knowledge', 'handout', 'other')
  ),
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  pre_confidence integer check (pre_confidence between 1 and 5),
  post_confidence integer check (post_confidence between 1 and 5),
  aha_score numeric(5, 2) check (aha_score between 0 and 100),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists learning_attempts_tenant_profile_created_idx
  on public.learning_attempts (tenant_id, profile_id, created_at desc);

create index if not exists learning_attempts_tenant_topic_created_idx
  on public.learning_attempts (tenant_id, topic_key, created_at desc);


create table if not exists public.aha_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid not null references public.profiles (id) on delete cascade,
  attempt_id uuid references public.learning_attempts (id) on delete set null,
  event_type text not null check (
    event_type in (
      'confused',
      'hint_shown',
      'aha_reported',
      'question_answered',
      'question_corrected',
      'review_passed'
    )
  ),
  hook_id uuid references public.aha_hooks (id) on delete set null,
  hook_variant_id text,
  topic_key text not null,
  question_id text,
  self_report_delta integer check (self_report_delta between -5 and 5),
  latency_ms integer check (latency_ms >= 0),
  is_correct boolean,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists aha_events_tenant_profile_created_idx
  on public.aha_events (tenant_id, profile_id, created_at desc);

create index if not exists aha_events_tenant_topic_created_idx
  on public.aha_events (tenant_id, topic_key, created_at desc);

create index if not exists aha_events_tenant_variant_created_idx
  on public.aha_events (tenant_id, hook_variant_id, created_at desc);


-- ---------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------
drop trigger if exists learner_contexts_updated_at on public.learner_contexts;
create trigger learner_contexts_updated_at
  before update on public.learner_contexts
  for each row execute function public.set_updated_at();

drop trigger if exists aha_hooks_updated_at on public.aha_hooks;
create trigger aha_hooks_updated_at
  before update on public.aha_hooks
  for each row execute function public.set_updated_at();

drop trigger if exists learning_attempts_updated_at on public.learning_attempts;
create trigger learning_attempts_updated_at
  before update on public.learning_attempts
  for each row execute function public.set_updated_at();


-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.learner_contexts enable row level security;
alter table public.aha_hooks enable row level security;
alter table public.learning_attempts enable row level security;
alter table public.aha_events enable row level security;

create policy learner_contexts_select on public.learner_contexts
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = learner_contexts.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy learner_contexts_insert on public.learner_contexts
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = learner_contexts.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy learner_contexts_update on public.learner_contexts
  for update using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = learner_contexts.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );


create policy aha_hooks_select on public.aha_hooks
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = aha_hooks.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy aha_hooks_insert on public.aha_hooks
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = aha_hooks.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy aha_hooks_update on public.aha_hooks
  for update using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = aha_hooks.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );


create policy learning_attempts_select on public.learning_attempts
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = learning_attempts.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy learning_attempts_insert on public.learning_attempts
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = learning_attempts.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy learning_attempts_update on public.learning_attempts
  for update using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = learning_attempts.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );


create policy aha_events_select on public.aha_events
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = aha_events.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy aha_events_insert on public.aha_events
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = aha_events.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );


-- ---------------------------------------------------------------------------
-- Analytics view (MVP): age_band + region_code + hook_variant effectiveness
-- ---------------------------------------------------------------------------
create or replace view public.aha_hook_effectiveness_view as
with base as (
  select
    date_trunc('day', e.created_at)::date as date,
    e.tenant_id,
    e.topic_key,
    lc.age_band,
    lc.region_code,
    coalesce(h.hook_type, 'unknown') as hook_type,
    coalesce(e.hook_variant_id, h.hook_variant_id, 'unknown') as hook_variant_id,
    e.event_type,
    e.latency_ms,
    e.is_correct,
    e.metadata
  from public.aha_events e
  left join public.learner_contexts lc
    on lc.tenant_id = e.tenant_id and lc.profile_id = e.profile_id
  left join public.aha_hooks h
    on h.id = e.hook_id
)
select
  date,
  tenant_id,
  topic_key,
  coalesce(age_band, 'unknown') as age_band,
  coalesce(region_code, 'unknown') as region_code,
  hook_type,
  hook_variant_id,
  count(*) filter (where event_type = 'hint_shown')::integer as impressions,
  count(*) filter (where event_type = 'aha_reported')::integer as aha_reports,
  avg(case
    when event_type = 'question_answered' and hook_variant_id <> 'unknown'
    then case when is_correct then 1.0 else 0.0 end
  end) as correct_after_hook,
  (
    avg(case
      when event_type = 'question_answered' and hook_variant_id <> 'unknown'
      then case when is_correct then 1.0 else 0.0 end
    end)
    -
    avg(case
      when event_type = 'question_answered' and hook_variant_id = 'unknown'
      then case when is_correct then 1.0 else 0.0 end
    end)
  ) as lift,
  percentile_cont(0.5) within group (order by latency_ms)
    filter (where event_type = 'aha_reported' and latency_ms is not null) as time_to_aha
from base
group by
  date,
  tenant_id,
  topic_key,
  coalesce(age_band, 'unknown'),
  coalesce(region_code, 'unknown'),
  hook_type,
  hook_variant_id;
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
-- App storage alignment: member storage, click tracking, segment-safe analytics
-- Depends on foundation + aha hook MVP + membership billing wallet migrations

create table if not exists public.member_storage (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants (id) on delete cascade,
  profile_id uuid not null references public.profiles (id) on delete cascade,
  feature text not null,
  title text not null default '',
  visibility text not null default 'private' check (
    visibility in ('private', 'shared', 'public')
  ),
  contribution_mode text not null default 'private_use' check (
    contribution_mode in ('private_use', 'named_contribution')
  ),
  input_text text not null default '',
  output_text text not null default '',
  output_json jsonb not null default '{}'::jsonb,
  source_model text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists member_storage_profile_created_idx
  on public.member_storage (profile_id, created_at desc);

create index if not exists member_storage_profile_feature_created_idx
  on public.member_storage (profile_id, feature, created_at desc);

alter table if exists public.etymon_entries
  add column if not exists source_member_storage_id uuid references public.member_storage (id) on delete set null,
  add column if not exists status text not null default 'published';

do $$ begin
  alter table public.etymon_entries
    add constraint etymon_entries_status_check
    check (status in ('draft', 'published', 'archived'));
exception
  when duplicate_object then null;
end $$;

create table if not exists public.click_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants (id) on delete set null,
  profile_id uuid references public.profiles (id) on delete set null,
  session_id text not null,
  page text not null default '',
  action text not null,
  action_label text not null default '',
  seq integer not null check (seq >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists click_events_session_seq_uidx
  on public.click_events (session_id, seq);

create index if not exists click_events_session_created_idx
  on public.click_events (session_id, created_at desc);

create index if not exists click_events_action_created_idx
  on public.click_events (action, created_at desc);

alter table if exists public.aha_events
  add column if not exists age_band text,
  add column if not exists region_code text;

create index if not exists aha_events_tenant_topic_segment_created_idx
  on public.aha_events (tenant_id, topic_key, age_band, region_code, created_at desc);

drop trigger if exists member_storage_updated_at on public.member_storage;
create trigger member_storage_updated_at
  before update on public.member_storage
  for each row execute function public.set_updated_at();

alter table public.member_storage enable row level security;
alter table public.click_events enable row level security;

create policy member_storage_select on public.member_storage
  for select using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = member_storage.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy member_storage_insert on public.member_storage
  for insert with check (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = member_storage.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy member_storage_update on public.member_storage
  for update using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = member_storage.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy member_storage_delete on public.member_storage
  for delete using (
    exists (
      select 1 from public.tenant_members m
      join public.profiles p on p.id = m.profile_id
      where m.tenant_id = member_storage.tenant_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create policy click_events_select on public.click_events
  for select using (
    profile_id is null
    or exists (
      select 1 from public.profiles p
      where p.id = click_events.profile_id
        and p.clerk_user_id = public.current_clerk_subject()
    )
  );

create or replace function public.aha_hook_effectiveness(
  p_tenant_id uuid,
  p_topic_key text,
  p_age_band text default null,
  p_region_code text default null
)
returns table (
  hook_type text,
  hook_variant_id text,
  impressions integer,
  aha_reports integer,
  correct_after_hook double precision,
  lift double precision,
  time_to_aha double precision
)
language sql
stable
security definer
set search_path = public
as $$
  select
    v.hook_type,
    v.hook_variant_id,
    coalesce(sum(v.impressions), 0)::integer as impressions,
    coalesce(sum(v.aha_reports), 0)::integer as aha_reports,
    avg(v.correct_after_hook)::double precision as correct_after_hook,
    avg(v.lift)::double precision as lift,
    avg(v.time_to_aha)::double precision as time_to_aha
  from public.aha_hook_effectiveness_view v
  where v.tenant_id = p_tenant_id
    and v.topic_key = p_topic_key
    and (p_age_band is null or p_age_band = '' or v.age_band = p_age_band)
    and (p_region_code is null or p_region_code = '' or v.region_code = p_region_code)
  group by v.hook_type, v.hook_variant_id;
$$;

create or replace function public.predict_click_actions(
  p_last_action text default null,
  p_limit integer default 5
)
returns table (
  action text,
  label text,
  count bigint,
  prob double precision
)
language sql
stable
security definer
set search_path = public
as $$
  with ranked as (
    select
      source.action,
      source.label,
      source.cnt as count
    from (
      select
        coalesce(e2.action, e1.action) as action,
        coalesce(nullif(e2.action_label, ''), nullif(e1.action_label, ''), coalesce(e2.action, e1.action)) as label,
        count(*) as cnt
      from public.click_events e1
      left join public.click_events e2
        on e1.session_id = e2.session_id
       and e2.seq = e1.seq + 1
      where (
        (coalesce(p_last_action, '') = '' and e1.action <> '')
        or (coalesce(p_last_action, '') <> '' and e1.action = p_last_action and e2.action <> '')
      )
      group by coalesce(e2.action, e1.action), coalesce(nullif(e2.action_label, ''), nullif(e1.action_label, ''), coalesce(e2.action, e1.action))
      order by cnt desc
      limit greatest(coalesce(p_limit, 5), 1)
    ) source
  ),
  totals as (
    select coalesce(sum(count), 0) as total_count from ranked
  )
  select
    r.action,
    r.label,
    r.count,
    case
      when t.total_count <= 0 then 0
      else (r.count::double precision / t.total_count::double precision)
    end as prob
  from ranked r
  cross join totals t
  order by r.count desc, r.action asc;
$$;
