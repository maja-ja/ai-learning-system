import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { generateText } from "../_shared/gemini.ts";
import { parseDecodeJson } from "../_shared/json.ts";
import {
  CORE_FIELDS,
  buildDecodeSystemPrompt,
  buildDecodeUserMessage,
  type CoreField,
} from "../_shared/prompts.ts";
import { assertInternalSecret, requireClerkUserId } from "../_shared/auth.ts";
import { serviceClient } from "../_shared/supabase.ts";

type Body = {
  input_text: string;
  primary_cat: string;
  aux_cats?: string[];
  tenant_id: string;
  /** Required when using x-internal-secret (Next.js server already verified user). */
  profile_id?: string;
  persist?: boolean;
};

function normalizeRow(
  parsed: Record<string, unknown>,
  displayCategory: string,
): Record<CoreField, string> {
  const row = {} as Record<CoreField, string>;
  for (const col of CORE_FIELDS) {
    const v = parsed[col];
    row[col] = v === undefined || v === null ? "無" : String(v);
  }
  row.category = displayCategory;
  return row;
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

  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return jsonResponse({ error: "Invalid JSON" }, { status: 400 });
  }

  const input = (body.input_text ?? "").trim();
  const primary = (body.primary_cat ?? "").trim();
  const aux = Array.isArray(body.aux_cats) ? body.aux_cats : [];
  const tenantId = body.tenant_id?.trim();

  if (!input || !primary || !tenantId) {
    return jsonResponse(
      { error: "input_text, primary_cat, tenant_id required" },
      { status: 400 },
    );
  }

  const apiKey = Deno.env.get("GEMINI_API_KEY");
  const model = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";
  if (!apiKey) {
    return jsonResponse({ error: "GEMINI_API_KEY not configured" }, { status: 500 });
  }

  const supabase = serviceClient();
  let profileId = body.profile_id ?? null;

  if (clerkId) {
    const { data: prof, error: pe } = await supabase
      .from("profiles")
      .select("id")
      .eq("clerk_user_id", clerkId)
      .maybeSingle();
    if (pe || !prof?.id) {
      return jsonResponse({ error: "Profile not provisioned" }, { status: 403 });
    }
    profileId = prof.id as string;
    const { data: mem, error: me } = await supabase
      .from("tenant_members")
      .select("tenant_id")
      .eq("tenant_id", tenantId)
      .eq("profile_id", profileId)
      .maybeSingle();
    if (me || !mem) {
      return jsonResponse({ error: "Forbidden for tenant" }, { status: 403 });
    }
  } else {
    if (!profileId) {
      return jsonResponse(
        { error: "profile_id required for internal calls" },
        { status: 400 },
      );
    }
  }

  const displayCategory = aux.length
    ? `${primary} + ${aux.join(" + ")}`
    : primary;

  const system = buildDecodeSystemPrompt(primary, aux);
  const finalPrompt = `${system}\n\n${buildDecodeUserMessage(input)}`;

  const t0 = performance.now();

  const { data: runRow, error: runInsErr } = await supabase
    .from("decode_runs")
    .insert({
      tenant_id: tenantId,
      profile_id: profileId,
      input_text: input,
      primary_category: primary,
      auxiliary_categories: aux,
      model,
      status: "pending",
      raw_request: { primary, aux, input },
    })
    .select("id")
    .single();

  if (runInsErr || !runRow?.id) {
    console.error(runInsErr);
    return jsonResponse({ error: "Failed to open decode run" }, { status: 500 });
  }

  const runId = runRow.id as string;

  try {
    const raw = await generateText({
      apiKey,
      model,
      prompt: finalPrompt,
      temperature: 0.2,
      topP: 0.95,
      maxOutputTokens: 2048,
    });

    const parsed = parseDecodeJson(raw);
    const row = normalizeRow(parsed, displayCategory);

    let entryId: string | null = null;
    if (body.persist !== false) {
      const payload = {
        tenant_id: tenantId,
        created_by: profileId,
        word: row.word,
        category: row.category,
        roots: row.roots,
        breakdown: row.breakdown,
        definition: row.definition,
        meaning: row.meaning,
        native_vibe: row.native_vibe,
        example: row.example,
        synonym_nuance: row.synonym_nuance,
        usage_warning: row.usage_warning,
        memory_hook: row.memory_hook,
        phonetic: row.phonetic,
        model,
        prompt_version: "decode_prod_v1",
      };

      const { data: hit } = await supabase
        .from("etymon_entries")
        .select("id")
        .eq("tenant_id", tenantId)
        .ilike("word", row.word)
        .maybeSingle();

      if (hit?.id) {
        const { data: updated } = await supabase
          .from("etymon_entries")
          .update(payload)
          .eq("id", hit.id)
          .select("id")
          .single();
        entryId = (updated?.id as string) ?? (hit.id as string);
      } else {
        const { data: inserted } = await supabase
          .from("etymon_entries")
          .insert(payload)
          .select("id")
          .single();
        entryId = (inserted?.id as string) ?? null;
      }
    }

    const latency = Math.round(performance.now() - t0);
    await supabase
      .from("decode_runs")
      .update({
        status: "success",
        latency_ms: latency,
        output_entry_id: entryId,
        raw_response: { text: raw.slice(0, 12000) },
      })
      .eq("id", runId);

    return jsonResponse({ ok: true, data: row, decode_run_id: runId, entry_id: entryId });
  } catch (e) {
    const latency = Math.round(performance.now() - t0);
    await supabase
      .from("decode_runs")
      .update({
        status: "failed",
        latency_ms: latency,
        error_message: String(e).slice(0, 2000),
      })
      .eq("id", runId);

    return jsonResponse(
      { ok: false, error: String(e), decode_run_id: runId },
      { status: 502 },
    );
  }
});
