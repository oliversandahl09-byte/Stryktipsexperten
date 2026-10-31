-- Sparade tips för inloggade användare på webbsidan (webb/index.html).
-- Kör en gång i Supabase: SQL Editor → New query, klistra in och Run.
--
-- En rad per användare, spel och omgång. "val" är sidans inställningar och
-- låsta tecken, "kupong" är tecknen per match som systemet blev.

create table if not exists public.tips (
  user_id uuid not null references auth.users (id) on delete cascade default auth.uid(),
  spel text not null check (spel in ('stryktipset', 'europatipset')),
  omgang integer not null,
  val jsonb not null default '{}'::jsonb,
  kupong jsonb not null default '[]'::jsonb,
  rader integer,
  uppdaterad timestamptz not null default now(),
  primary key (user_id, spel, omgang)
);

-- Var och en ser och ändrar bara sina egna tips.
alter table public.tips enable row level security;

drop policy if exists "egna tips läses" on public.tips;
drop policy if exists "egna tips skapas" on public.tips;
drop policy if exists "egna tips ändras" on public.tips;
drop policy if exists "egna tips tas bort" on public.tips;

create policy "egna tips läses" on public.tips
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "egna tips skapas" on public.tips
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "egna tips ändras" on public.tips
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "egna tips tas bort" on public.tips
  for delete to authenticated using ((select auth.uid()) = user_id);
