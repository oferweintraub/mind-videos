-- ──────────────────────────────────────────────────────────────────────
-- Mind Video — Supabase one-time setup
-- ──────────────────────────────────────────────────────────────────────
--
-- Paste this whole file into the Supabase SQL Editor and click "Run".
-- One-time setup; idempotent (safe to re-run if you tweak something).
--
-- What this creates:
--   1. `projects` table — one row per project (cast metadata, segments,
--      title, optional API keys for share-link handoff). Image binaries
--      live in Storage, not in this row.
--   2. `character-images` storage bucket — public-readable bucket for
--      character stills, episode finals, and reference uploads. Each
--      object is keyed by the project_id, so projects are isolated.
--   3. RLS disabled on `projects` for now — security model is
--      unguessable project UUIDs (the URL itself is the bearer token).
--      Same trust model as Excalidraw, jsonbin, etc.
-- ──────────────────────────────────────────────────────────────────────


-- 1. Projects table
create table if not exists public.projects (
  -- Short URL-safe ID. We'll generate this client-side as a 12-char
  -- urlsafe base64 — short enough to fit in a tweet, long enough to be
  -- unguessable (>2^60 entropy).
  id text primary key,

  -- Display fields
  title text not null default '',

  -- Cast: list of {slug, display_name, description, style, voice: {...}}
  -- Image bytes are stored in the storage bucket, not here.
  cast_data jsonb not null default '[]'::jsonb,

  -- Segments: list of {character, text}
  segments_data jsonb not null default '[]'::jsonb,

  -- Wizard step the project was last on (1, 2, or 3)
  step int not null default 1,

  -- Render result (set after a successful render)
  -- {path_in_bucket, elapsed, cost, slug}
  result jsonb,

  -- Optional: original creator's API keys, included when share_keys=true.
  -- This is the "send link with keys" feature — opt-in only.
  share_keys boolean not null default false,
  api_keys jsonb,  -- {fal: "...", elevenlabs: "...", google: "..."}

  -- Audit
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Auto-update `updated_at` on every row update
create or replace function public.set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists projects_set_updated_at on public.projects;
create trigger projects_set_updated_at
before update on public.projects
for each row execute function public.set_updated_at();

-- Enable anonymous access (security comes from unguessable project IDs).
-- We turn RLS OFF — anyone with the publishable key can CRUD any row.
-- That's fine because the *URL* is the access token, not the row's owner.
alter table public.projects disable row level security;


-- 2. Storage bucket for character images, ref uploads, and episode finals
insert into storage.buckets (id, name, public)
values ('character-images', 'character-images', true)
on conflict (id) do nothing;

-- Bucket policies: allow anonymous read + write. Same trust model as
-- the table — security via unguessable object keys (project_id/...).
-- These statements are idempotent.
do $$
begin
  -- Public read
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'mindvideo_public_read'
  ) then
    create policy mindvideo_public_read on storage.objects
      for select using (bucket_id = 'character-images');
  end if;

  -- Anonymous insert
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'mindvideo_public_insert'
  ) then
    create policy mindvideo_public_insert on storage.objects
      for insert with check (bucket_id = 'character-images');
  end if;

  -- Anonymous update (overwrite same object key on re-upload)
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'mindvideo_public_update'
  ) then
    create policy mindvideo_public_update on storage.objects
      for update using (bucket_id = 'character-images');
  end if;

  -- Anonymous delete (so users can remove characters)
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'mindvideo_public_delete'
  ) then
    create policy mindvideo_public_delete on storage.objects
      for delete using (bucket_id = 'character-images');
  end if;
end $$;


-- ──────────────────────────────────────────────────────────────────────
-- Sanity check: try a no-op insert + delete to confirm the table works.
-- (Roll back at end so we don't leave test data.)
-- ──────────────────────────────────────────────────────────────────────
do $$
declare
  test_id text := '__setup_test__';
begin
  insert into public.projects (id, title) values (test_id, 'setup test');
  perform * from public.projects where id = test_id;
  delete from public.projects where id = test_id;
  raise notice 'Mind Video Supabase setup OK ✓';
end $$;
