import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { HANDOUT_SYSTEM_PROMPT } from "../_shared/prompts.ts";
import { assertInternalSecret, requireClerkUserId } from "../_shared/auth.ts";

const GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta";

async function generateHandout(params: {
  apiKey: string;
  model: string;
  manual?: string;
  instruction?: string;
  imageBase64?: string;
  imageMime?: string;
}): Promise<string> {
  const {
    apiKey,
    model,
    manual,
    instruction,
    imageBase64,
    imageMime = "image/jpeg",
  } = params;

  const url =
    `${GEMINI_BASE}/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;

  const parts: Record<string, unknown>[] = [
    { text: HANDOUT_SYSTEM_PROMPT },
  ];
  if (manual) {
    parts.push({ text: `使用者素材：\n${manual}` });
  }
  if (instruction) {
    parts.push({ text: `排版指示：${instruction}` });
  }
  if (imageBase64) {
    parts.push({
      inline_data: { mime_type: imageMime, data: imageBase64 },
    });
  }

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts }],
      generationConfig: {
        temperature: 0.2,
        topP: 0.95,
        maxOutputTokens: 4096,
      },
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gemini HTTP ${res.status}: ${errText}`);
  }

  const data = (await res.json()) as {
    candidates?: { content?: { parts?: { text?: string }[] } }[];
  };

  let text = data.candidates?.[0]?.content?.parts?.map((p) => p.text ?? "")
    .join("") ?? "";
  text = text.trim().replace(/^```markdown\s*/i, "").replace(/\s*```$/i, "");
  return text.trim();
}

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
    manual_markdown?: string;
    instruction?: string;
    image_base64?: string;
    image_mime?: string;
  };

  const apiKey = Deno.env.get("GEMINI_API_KEY");
  const model = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";
  if (!apiKey) {
    return jsonResponse({ error: "GEMINI_API_KEY not configured" }, { status: 500 });
  }

  try {
    const markdown = await generateHandout({
      apiKey,
      model,
      manual: body.manual_markdown,
      instruction: body.instruction,
      imageBase64: body.image_base64,
      imageMime: body.image_mime,
    });
    return jsonResponse({ ok: true, markdown });
  } catch (e) {
    return jsonResponse({ ok: false, error: String(e) }, { status: 502 });
  }
});
