import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY;

// hasSupabase is false until env vars are filled in. The app falls back to
// local-only mode (localStorage) so it still works before cloud is configured.
export const hasSupabase = Boolean(url && anon);

export const supabase = hasSupabase
  ? createClient(url, anon, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;
