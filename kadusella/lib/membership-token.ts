import crypto from "node:crypto";
import { requireEnv } from "@/lib/env";

export type MembershipTokenPayload = {
  sub: string;
  profileId: string;
  tenantId: string;
  email: string;
  displayName: string;
  planKey: string;
  subscriptionStatus: string;
  creditsBalance: number;
  canGenerate: boolean;
  exp: number;
};

function base64Url(input: string): string {
  return Buffer.from(input, "utf-8").toString("base64url");
}

export function createMembershipToken(
  payload: Omit<MembershipTokenPayload, "exp">,
  expiresInSeconds = 60 * 60,
): string {
  const secret = requireEnv("MEMBERSHIP_TOKEN_SECRET");
  const fullPayload: MembershipTokenPayload = {
    ...payload,
    exp: Math.floor(Date.now() / 1000) + expiresInSeconds,
  };
  const body = base64Url(JSON.stringify(fullPayload));
  const sig = crypto.createHmac("sha256", secret).update(body).digest("base64url");
  return `${body}.${sig}`;
}
