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
