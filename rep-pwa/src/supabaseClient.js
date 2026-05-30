import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY;

// hasSupabase is false until env vars are filled in. The app falls back to
// local-only mode (localStorage) so it still works before cloud is configured.
export const hasSupabase = Boolean(url && anon);

export const supabase = hasSupabase
  ? createClient(url, anon, {
      // detectSessionInUrl:false — a session token in the URL must NOT log anyone
      // in. Leaving it true meant copying your address-bar URL handed your whole
      // session to whoever you sent it to. Sign-in is via email+password only.
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    })
  : null;
