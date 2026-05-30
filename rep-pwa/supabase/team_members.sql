-- ─────────────────────────────────────────────────────────────────────────────
-- Team members — run this in Supabase SQL Editor after schema.sql
-- Allows an account owner to invite others to share their data.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists public.team_members (
  owner_id     uuid        not null references auth.users(id) on delete cascade,
  member_email text        not null,
  member_id    uuid        references auth.users(id) on delete set null,
  invited_at   timestamptz not null default now(),
  accepted_at  timestamptz,
  primary key (owner_id, member_email)
);

alter table public.team_members enable row level security;

-- Owner can read/write their team list
drop policy if exists "team_owner_all" on public.team_members;
create policy "team_owner_all" on public.team_members
  for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- Member can read their own membership row (so the app can find the owner)
drop policy if exists "team_member_select" on public.team_members;
create policy "team_member_select" on public.team_members
  for select using (auth.uid() = member_id);

-- Member can update their own row to set member_id on first sign-in
drop policy if exists "team_member_claim" on public.team_members;
create policy "team_member_claim" on public.team_members
  for update using (
    member_id is null
    and member_email = (select email from auth.users where id = auth.uid())
  ) with check (auth.uid() = member_id);

-- Allow team members to read/write the owner's user_data row
drop policy if exists "user_data_team_member" on public.user_data;
create policy "user_data_team_member" on public.user_data
  for all using (
    exists (
      select 1 from public.team_members
      where owner_id = user_data.user_id
        and member_id = auth.uid()
        and accepted_at is not null
    )
  ) with check (
    exists (
      select 1 from public.team_members
      where owner_id = user_data.user_id
        and member_id = auth.uid()
        and accepted_at is not null
    )
  );
