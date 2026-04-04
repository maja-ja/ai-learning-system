import { createClient } from "@supabase/supabase-js";
import { requireEnv } from "@/lib/env";

function assertSupabaseCredentials(urlRaw: string, keyRaw: string): void {
  const url = urlRaw.trim();
  if (!/^https:\/\/.+\..+/.test(url)) {
    throw new Error(
      "Invalid SUPABASE_URL: use the Project URL from Supabase (Settings → API), e.g. https://xxxx.supabase.co",
    );
  }
  const key = keyRaw.trim();
  if (key.length < 32 || /\s/.test(key)) {
    throw new Error(
      "Invalid SUPABASE_SERVICE_ROLE_KEY: paste the service_role secret from Supabase (Settings → API).",
    );
  }
}

export function createSupabaseAdmin() {
  const url = requireEnv("SUPABASE_URL");
  const key = requireEnv("SUPABASE_SERVICE_ROLE_KEY");
  assertSupabaseCredentials(url, key);
  return createClient(
    url,
    key,
    {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
      },
    },
  );
}
