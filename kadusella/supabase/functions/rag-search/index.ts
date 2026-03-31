import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { embedText768 } from "../_shared/gemini.ts";
import { assertInternalSecret, requireClerkUserId } from "../_shared/auth.ts";
import { serviceClient } from "../_shared/supabase.ts";

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

  const body = (await req.json()) as {
    query: string;
    tenant_id: string;
    match_count?: number;
    profile_id?: string;
  };

  const q = (body.query ?? "").trim();
  const tenantId = body.tenant_id?.trim();
  if (!q || !tenantId) {
    return jsonResponse({ error: "query and tenant_id required" }, { status: 400 });
  }

  const supabase = serviceClient();

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
      .eq("tenant_id", tenantId)
      .eq("profile_id", prof.id)
      .maybeSingle();
    if (!mem) {
      return jsonResponse({ error: "Forbidden for tenant" }, { status: 403 });
    }
  } else if (!body.profile_id) {
    return jsonResponse({ error: "profile_id required for internal calls" }, { status: 400 });
  }

  const apiKey = Deno.env.get("GEMINI_API_KEY");
  if (!apiKey) {
    return jsonResponse({ error: "GEMINI_API_KEY not configured" }, { status: 500 });
  }

  const vec = await embedText768(apiKey, q);
  const matchCount = Math.min(Math.max(body.match_count ?? 8, 1), 50);

  const { data, error } = await supabase.rpc("match_etymon_entries", {
    query_embedding: vec,
    match_count: matchCount,
    p_tenant_id: tenantId,
  });

  if (error) {
    console.error(error);
    return jsonResponse({ error: error.message }, { status: 500 });
  }

  return jsonResponse({ ok: true, results: data ?? [] });
});
