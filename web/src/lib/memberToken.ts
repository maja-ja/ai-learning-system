const MEMBER_TOKEN_KEY = "member_backend_token";

type MemberTokenClaims = {
  profileId?: string;
  tenantId?: string;
};

function decodeBase64Url(value: string): string | null {
  try {
    const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    return atob(padded);
  } catch {
    return null;
  }
}

export function getMemberToken(): string | null {
  return localStorage.getItem(MEMBER_TOKEN_KEY);
}

export function setMemberToken(token: string) {
  localStorage.setItem(MEMBER_TOKEN_KEY, token);
}

export function clearMemberToken() {
  localStorage.removeItem(MEMBER_TOKEN_KEY);
}

export function readMemberTokenClaims(): MemberTokenClaims | null {
  const token = getMemberToken();
  if (!token) return null;
  const dot = token.indexOf(".");
  const body = dot >= 0 ? token.slice(0, dot) : "";
  if (!body) return null;
  const decoded = decodeBase64Url(body);
  if (!decoded) return null;
  try {
    return JSON.parse(decoded) as MemberTokenClaims;
  } catch {
    return null;
  }
}
