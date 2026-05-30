-- ─────────────────────────────────────────────────────────────────────────────
-- REP Hour Log — Supabase schema
-- Run this once in your Supabase project: Dashboard → SQL Editor → New query →
-- paste this whole file → Run.
--
-- Design: one row per user holds their entire dataset as JSONB (logs, recurring
-- tasks, properties, attestation). Row Level Security ensures every user can only
-- read and write their OWN row — even though everyone shares this one table.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists public.user_data (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  logs       jsonb       not null default '[]'::jsonb,
  recur      jsonb       not null default '[]'::jsonb,
  properties jsonb       not null default '[]'::jsonb,
  attest     jsonb       not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- Lock the table down: no access by default.
alter table public.user_data enable row level security;

-- A user may only touch the row whose user_id matches their auth uid.
drop policy if exists "user_data_select_own" on public.user_data;
create policy "user_data_select_own" on public.user_data
  for select using (auth.uid() = user_id);

drop policy if exists "user_data_insert_own" on public.user_data;
create policy "user_data_insert_own" on public.user_data
  for insert with check (auth.uid() = user_id);

drop policy if exists "user_data_update_own" on public.user_data;
create policy "user_data_update_own" on public.user_data
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "user_data_delete_own" on public.user_data;
create policy "user_data_delete_own" on public.user_data
  for delete using (auth.uid() = user_id);

-- Keep updated_at fresh on every write (used for last-write-wins across devices).
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists trg_user_data_touch on public.user_data;
create trigger trg_user_data_touch
  before update on public.user_data
  for each row execute function public.touch_updated_at();
