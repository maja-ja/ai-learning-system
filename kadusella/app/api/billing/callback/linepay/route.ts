import { NextRequest, NextResponse } from "next/server";
import { finalizeLinePayCallback } from "@/lib/billing";
import { webAppUrl } from "@/lib/env";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const orderId = request.nextUrl.searchParams.get("order_id") || "";
  const transactionId = request.nextUrl.searchParams.get("transactionId") || "";
  if (!orderId || !transactionId) {
    return NextResponse.redirect(`${webAppUrl()}/handout?billing=failed`);
  }

  try {
    const redirectUrl = await finalizeLinePayCallback(orderId, transactionId);
    return NextResponse.redirect(redirectUrl);
  } catch {
    return NextResponse.redirect(`${webAppUrl()}/handout?billing=failed`);
  }
}
