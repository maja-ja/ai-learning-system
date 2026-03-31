const GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta";

export async function generateText(params: {
  apiKey: string;
  model: string;
  prompt: string;
  temperature?: number;
  topP?: number;
  maxOutputTokens?: number;
}): Promise<string> {
  const {
    apiKey,
    model,
    prompt,
    temperature = 0.2,
    topP = 0.95,
    maxOutputTokens = 4096,
  } = params;

  const url =
    `${GEMINI_BASE}/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: {
        temperature,
        topP,
        maxOutputTokens,
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

  const text = data.candidates?.[0]?.content?.parts?.map((p) => p.text ?? "")
    .join("") ?? "";
  return text.trim();
}

/** Google text-embedding-004 → 768-d (matches migration default). */
export async function embedText768(
  apiKey: string,
  text: string,
): Promise<number[]> {
  const model = "text-embedding-004";
  const url =
    `${GEMINI_BASE}/models/${model}:embedContent?key=${encodeURIComponent(apiKey)}`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: `models/${model}`,
      content: { parts: [{ text }] },
      outputDimensionality: 768,
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gemini embed HTTP ${res.status}: ${errText}`);
  }

  const data = (await res.json()) as {
    embedding?: { values?: number[] };
  };

  const values = data.embedding?.values;
  if (!values || values.length !== 768) {
    throw new Error("Unexpected embedding shape");
  }
  return values;
}
