export function stripJsonFences(raw: string): string {
  let t = raw.trim();
  t = t.replace(/^```json\s*/i, "").replace(/\s*```$/i, "");
  return t.trim();
}

export function parseDecodeJson(raw: string): Record<string, string> {
  const clean = stripJsonFences(raw);
  try {
    return JSON.parse(clean) as Record<string, string>;
  } catch {
    const fixed = clean.replace(/\n/g, "\\n");
    return JSON.parse(fixed) as Record<string, string>;
  }
}
