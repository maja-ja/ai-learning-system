const GEMINI_KEY = "etymon_user_gemini_key";

export function getUserGeminiKey(): string {
  try {
    return localStorage.getItem(GEMINI_KEY) || "";
  } catch {
    return "";
  }
}

export function setUserGeminiKey(key: string): void {
  try {
    if (key.trim()) {
      localStorage.setItem(GEMINI_KEY, key.trim());
    } else {
      localStorage.removeItem(GEMINI_KEY);
    }
  } catch {
    /* noop */
  }
}

export function hasUserGeminiKey(): boolean {
  return getUserGeminiKey().length > 0;
}
