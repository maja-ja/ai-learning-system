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
