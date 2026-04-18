-- Run this in Supabase SQL editor to create tables + RLS policies.

create table if not exists public.interviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid(),
  meta jsonb not null default '{}'::jsonb,
  score int,
  created_at timestamptz not null default now()
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid(),
  interview_id uuid not null references public.interviews(id) on delete cascade,
  role text not null check (role in ('user','assistant','system')),
  content text not null,
  created_at timestamptz not null default now()
);

alter table public.interviews enable row level security;
alter table public.messages enable row level security;

create policy "interviews_select_own" on public.interviews
for select using (auth.uid() = user_id);

create policy "interviews_insert_own" on public.interviews
for insert with check (auth.uid() = user_id);

drop policy if exists "interviews_update_own" on public.interviews;
create policy "interviews_update_own" on public.interviews
for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "messages_select_own" on public.messages
for select using (auth.uid() = user_id);

create policy "messages_insert_own" on public.messages
for insert with check (auth.uid() = user_id);

create or replace view public.v_daily_message_counts as
select
  date_trunc('day', created_at)::date as day,
  count(*)::int as count
from public.messages
where user_id = auth.uid()
group by 1
order by 1;

create or replace view public.v_daily_avg_score as
select
  date_trunc('day', created_at)::date as day,
  round(avg(score)::numeric, 1) as avg_score,
  count(*)::int as interviews_scored
from public.interviews
where user_id = auth.uid() and score is not null
group by 1
order by 1;

-- Migration helper (if you created tables before adding score column):
alter table public.interviews add column if not exists score int;

