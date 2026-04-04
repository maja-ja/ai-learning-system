import { createClerkClient, verifyToken } from "@clerk/backend";
import type { NextRequest } from "next/server";
import { requireEnv } from "@/lib/env";

export type VerifiedMember = {
  clerkUserId: string;
  email: string;
  displayName: string;
  avatarUrl: string;
};

export async function requireVerifiedMember(request: NextRequest): Promise<VerifiedMember> {
  const header = request.headers.get("authorization");
  if (!header?.startsWith("Bearer ")) {
    throw new Error("Missing bearer token");
  }

  const token = header.slice("Bearer ".length).trim();
  const secretKey = requireEnv("CLERK_SECRET_KEY");
  const payload = await verifyToken(token, { secretKey });

  const clerkUserId = payload.sub;
  if (!clerkUserId) {
    throw new Error("Invalid Clerk token subject");
  }

  const clerkClient = createClerkClient({ secretKey });
  const user = await clerkClient.users.getUser(clerkUserId);
  const primaryEmailId = user.primaryEmailAddressId;
  const email =
    user.emailAddresses.find((item) => item.id === primaryEmailId)?.emailAddress ||
    user.emailAddresses[0]?.emailAddress ||
    "";
  const displayName =
    [user.firstName, user.lastName].filter(Boolean).join(" ").trim() ||
    user.username ||
    email ||
    "Member";

  return {
    clerkUserId,
    email,
    displayName,
    avatarUrl: user.imageUrl || "",
  };
}
