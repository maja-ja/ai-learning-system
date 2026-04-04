import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { generateText } from "../_shared/gemini.ts";
import { buildRandomTopicsPrompt } from "../_shared/prompts.ts";
import { assertInternalSecret, requireClerkUserId } from "../_shared/auth.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    await requireClerkUserId(req);
  } catch {
    try {
      assertInternalSecret(req);
    } catch {
      return jsonResponse({ error: "Unauthorized" }, { status: 401 });
    }
  }

  const body = (await req.json()) as {
    primary_cat?: string;
    aux_cats?: string[];
    count?: number;
  };

  const primary = (body.primary_cat ?? "").trim();
  const aux = Array.isArray(body.aux_cats) ? body.aux_cats : [];
  const count = Math.min(Math.max(body.count ?? 5, 1), 20);

  if (!primary) {
    return jsonResponse({ error: "primary_cat required" }, { status: 400 });
  }

  const apiKey = Deno.env.get("GEMINI_API_KEY");
  const model = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";
  if (!apiKey) {
    return jsonResponse({ error: "GEMINI_API_KEY not configured" }, { status: 500 });
  }

  const prompt = buildRandomTopicsPrompt(primary, aux, count);
  const text = await generateText({
    apiKey,
    model,
    prompt,
    temperature: 0.9,
    topP: 0.95,
    maxOutputTokens: 512,
  });

  const clean = text.replaceAll("*", "").replaceAll("-", "").trim();
  return jsonResponse({ ok: true, text: clean });
});
