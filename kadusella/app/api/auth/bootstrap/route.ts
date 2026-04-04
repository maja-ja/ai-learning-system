import { NextRequest, NextResponse } from "next/server";
import { requireVerifiedMember } from "@/lib/clerk-auth";
import { withCors, preflight } from "@/lib/cors";
import { bootstrapMembership } from "@/lib/membership";
import { createMembershipToken } from "@/lib/membership-token";
import { CREDIT_PACKS } from "@/lib/billing-config";

export const dynamic = "force-dynamic";

export async function OPTIONS(request: NextRequest) {
  return preflight(request);
}

export async function POST(request: NextRequest) {
  try {
    const member = await requireVerifiedMember(request);
    const snapshot = await bootstrapMembership(member);
    const backendToken = createMembershipToken({
      sub: member.clerkUserId,
      profileId: snapshot.profileId,
      tenantId: snapshot.tenantId,
      email: snapshot.email,
      displayName: snapshot.displayName,
      planKey: snapshot.subscription.planKey,
      subscriptionStatus: snapshot.subscription.status,
      creditsBalance: snapshot.creditsBalance,
      canGenerate: snapshot.canGenerate,
    });

    return withCors(
      request,
      NextResponse.json({
        profile: {
          id: snapshot.profileId,
          email: snapshot.email,
          displayName: snapshot.displayName,
        },
        tenant: {
          id: snapshot.tenantId,
        },
        subscription: snapshot.subscription,
        wallet: {
          creditsBalance: snapshot.creditsBalance,
        },
        access: {
          canGenerate: snapshot.canGenerate,
          contributorLabel: snapshot.displayName,
        },
        backendToken,
        packs: CREDIT_PACKS,
      }),
    );
  } catch (error) {
    return withCors(
      request,
      NextResponse.json(
        {
          error: error instanceof Error ? error.message : "Bootstrap failed",
        },
        { status: 401 },
      ),
    );
  }
}
