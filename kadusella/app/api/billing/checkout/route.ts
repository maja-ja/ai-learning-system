import { NextRequest, NextResponse } from "next/server";
import { requireVerifiedMember } from "@/lib/clerk-auth";
import { withCors, preflight } from "@/lib/cors";
import { bootstrapMembership } from "@/lib/membership";
import { createCheckoutSession, type BillingProvider } from "@/lib/billing";

export const dynamic = "force-dynamic";

type CheckoutBody = {
  provider?: BillingProvider;
  packKey?: string;
  returnPath?: string;
};

export async function OPTIONS(request: NextRequest) {
  return preflight(request);
}

export async function POST(request: NextRequest) {
  try {
    const member = await requireVerifiedMember(request);
    const membership = await bootstrapMembership(member);
    const body = (await request.json()) as CheckoutBody;
    if (!body.provider || !body.packKey) {
      return withCors(
        request,
        NextResponse.json({ error: "provider and packKey are required" }, { status: 400 }),
      );
    }

    const checkout = await createCheckoutSession({
      provider: body.provider,
      packKey: body.packKey,
      membership,
      requestOrigin: request.nextUrl.origin,
      returnPath: body.returnPath || "/handout",
    });

    return withCors(
      request,
      NextResponse.json({
        checkoutUrl: checkout.checkoutUrl,
        orderId: checkout.orderId,
      }),
    );
  } catch (error) {
    return withCors(
      request,
      NextResponse.json(
        {
          error: error instanceof Error ? error.message : "Checkout failed",
        },
        { status: 400 },
      ),
    );
  }
}
