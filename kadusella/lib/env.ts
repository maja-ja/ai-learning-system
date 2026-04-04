export function requireEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function optionalEnv(name: string, fallback = ""): string {
  return process.env[name]?.trim() || fallback;
}

export function webAppUrl(): string {
  return optionalEnv("WEB_APP_URL", "http://localhost:5173").replace(/\/$/, "");
}

export function billingBaseUrl(): string {
  return optionalEnv("NEXT_PUBLIC_BILLING_BASE_URL", "").replace(/\/$/, "");
}
