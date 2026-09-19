create table if not exists public.app_data (key text primary key, value jsonb);
create table if not exists public.admins (id uuid primary key default gen_random_uuid(), username text unique not null, password_hash text not null, created_at timestamptz not null default now());
alter table public.app_data enable row level security;
alter table public.admins enable row level security;
