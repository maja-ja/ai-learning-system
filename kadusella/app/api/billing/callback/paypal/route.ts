import { NextRequest, NextResponse } from "next/server";
import { finalizePayPalCallback } from "@/lib/billing";
import { webAppUrl } from "@/lib/env";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const orderId = request.nextUrl.searchParams.get("order_id") || "";
  const providerOrderId = request.nextUrl.searchParams.get("token") || "";
  if (!orderId || !providerOrderId) {
    return NextResponse.redirect(`${webAppUrl()}/handout?billing=failed`);
  }

  try {
    const redirectUrl = await finalizePayPalCallback(orderId, providerOrderId);
    return NextResponse.redirect(redirectUrl);
  } catch {
    return NextResponse.redirect(`${webAppUrl()}/handout?billing=failed`);
  }
}
