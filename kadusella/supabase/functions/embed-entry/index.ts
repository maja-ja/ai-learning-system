import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { embedText768 } from "../_shared/gemini.ts";
import { assertInternalSecret, requireClerkUserId } from "../_shared/auth.ts";
import { serviceClient } from "../_shared/supabase.ts";

function buildCorpus(row: Record<string, unknown>): string {
  const keys = [
    "word",
    "category",
    "roots",
    "breakdown",
    "definition",
    "meaning",
    "native_vibe",
    "example",
    "synonym_nuance",
    "usage_warning",
    "memory_hook",
    "phonetic",
  ];
  return keys.map((k) => `${k}: ${row[k] ?? ""}`).join("\n");
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, { status: 405 });
  }

  let clerkId: string | null = null;
  try {
    clerkId = await requireClerkUserId(req);
  } catch {
    try {
      assertInternalSecret(req);
    } catch {
      return jsonResponse({ error: "Unauthorized" }, { status: 401 });
    }
  }

  const body = (await req.json()) as { entry_id?: string };
  const entryId = body.entry_id?.trim();
  if (!entryId) {
    return jsonResponse({ error: "entry_id required" }, { status: 400 });
  }

  const supabase = serviceClient();
  const { data: row, error: fe } = await supabase
    .from("etymon_entries")
    .select("*")
    .eq("id", entryId)
    .maybeSingle();

  if (fe || !row) {
    return jsonResponse({ error: "Entry not found" }, { status: 404 });
  }

  if (clerkId) {
    const { data: prof } = await supabase
      .from("profiles")
      .select("id")
      .eq("clerk_user_id", clerkId)
      .maybeSingle();
    if (!prof?.id) {
      return jsonResponse({ error: "Profile not provisioned" }, { status: 403 });
    }
    const { data: mem } = await supabase
      .from("tenant_members")
      .select("tenant_id")
      .eq("tenant_id", row.tenant_id as string)
      .eq("profile_id", prof.id)
      .maybeSingle();
    if (!mem) {
      return jsonResponse({ error: "Forbidden" }, { status: 403 });
    }
  }

  const apiKey = Deno.env.get("GEMINI_API_KEY");
  if (!apiKey) {
    return jsonResponse({ error: "GEMINI_API_KEY not configured" }, { status: 500 });
  }

  const text = buildCorpus(row as Record<string, unknown>);
  const vec = await embedText768(apiKey, text);

  const { error: ue } = await supabase
    .from("etymon_entries")
    .update({ embedding: vec })
    .eq("id", entryId);

  if (ue) {
    console.error(ue);
    return jsonResponse({ error: ue.message }, { status: 500 });
  }

  return jsonResponse({ ok: true, entry_id: entryId });
});
