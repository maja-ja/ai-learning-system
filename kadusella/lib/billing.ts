import crypto from "node:crypto";
import { createSupabaseAdmin } from "@/lib/supabase-admin";
import { getPack, type CreditPack } from "@/lib/billing-config";
import { optionalEnv, requireEnv, webAppUrl } from "@/lib/env";
import type { MembershipSnapshot } from "@/lib/membership";

export type BillingProvider = "linepay" | "paypal";

type BillingOrderRow = {
  id: string;
  tenant_id: string;
  profile_id: string | null;
  provider: BillingProvider;
  provider_order_id: string | null;
  provider_transaction_id: string | null;
  provider_payment_id: string | null;
  pack_key: string;
  amount_minor: number;
  currency: string;
  credits: number;
  status: string;
  checkout_url: string | null;
  metadata: Record<string, unknown> | null;
};

type CheckoutParams = {
  provider: BillingProvider;
  packKey: string;
  membership: MembershipSnapshot;
  requestOrigin: string;
  returnPath: string;
};

function sanitizeReturnPath(input: string): string {
  return input.startsWith("/") ? input : "/handout";
}

function paypalBaseUrl(): string {
  return optionalEnv("PAYPAL_ENV", "sandbox") === "live"
    ? "https://api-m.paypal.com"
    : "https://api-m.sandbox.paypal.com";
}

function linePayBaseUrl(): string {
  return optionalEnv("LINE_PAY_ENV", "sandbox") === "live"
    ? "https://api-pay.line.me"
    : "https://sandbox-api-pay.line.me";
}

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  const text = await response.text();
  const json = text ? (JSON.parse(text) as T) : ({} as T);
  if (!response.ok) {
    throw new Error(text || `HTTP ${response.status}`);
  }
  return json;
}

async function insertOrder(params: CheckoutParams, pack: CreditPack): Promise<BillingOrderRow> {
  const supabase = createSupabaseAdmin();
  const insert = await supabase
    .from("billing_orders")
    .insert({
      tenant_id: params.membership.tenantId,
      profile_id: params.membership.profileId,
      provider: params.provider,
      pack_key: pack.key,
      amount_minor: pack.amountTwd,
      currency: "TWD",
      credits: pack.credits,
      status: "created",
      metadata: {
        return_path: sanitizeReturnPath(params.returnPath),
        plan_key: pack.key,
      },
    })
    .select()
    .single();
  if (insert.error) throw insert.error;
  return insert.data as BillingOrderRow;
}

async function updateOrder(
  orderId: string,
  patch: Record<string, unknown>,
): Promise<BillingOrderRow> {
  const supabase = createSupabaseAdmin();
  const update = await supabase
    .from("billing_orders")
    .update({ ...patch, updated_at: new Date().toISOString() })
    .eq("id", orderId)
    .select()
    .single();
  if (update.error) throw update.error;
  return update.data as BillingOrderRow;
}

async function getOrderById(orderId: string): Promise<BillingOrderRow> {
  const supabase = createSupabaseAdmin();
  const result = await supabase.from("billing_orders").select("*").eq("id", orderId).single();
  if (result.error) throw result.error;
  return result.data as BillingOrderRow;
}

async function getOrderByProviderOrderId(
  provider: BillingProvider,
  providerOrderId: string,
): Promise<BillingOrderRow> {
  const supabase = createSupabaseAdmin();
  const result = await supabase
    .from("billing_orders")
    .select("*")
    .eq("provider", provider)
    .eq("provider_order_id", providerOrderId)
    .single();
  if (result.error) throw result.error;
  return result.data as BillingOrderRow;
}

async function grantCredits(order: BillingOrderRow): Promise<number> {
  const supabase = createSupabaseAdmin();
  const result = await supabase.rpc("grant_checkout_credits", {
    p_tenant_id: order.tenant_id,
    p_profile_id: order.profile_id,
    p_order_id: order.id,
    p_credits: order.credits,
    p_metadata: {
      provider: order.provider,
      pack_key: order.pack_key,
    },
  });
  if (result.error) throw result.error;
  return Number(result.data || 0);
}

async function touchSubscription(order: BillingOrderRow): Promise<void> {
  const supabase = createSupabaseAdmin();
  const current = await supabase
    .from("subscriptions")
    .select("id")
    .eq("tenant_id", order.tenant_id)
    .order("updated_at", { ascending: false })
    .limit(1);
  if (current.error) throw current.error;

  const payload = {
    tenant_id: order.tenant_id,
    plan_key: order.pack_key,
    status: "incomplete",
    current_period_start: new Date().toISOString(),
    current_period_end: new Date().toISOString(),
    metadata: {
      billing_mode: "pay_as_you_go",
      provider: order.provider,
      last_order_id: order.id,
    },
  };

  if ((current.data || []).length > 0) {
    const id = (current.data?.[0] as { id: string }).id;
    const update = await supabase.from("subscriptions").update(payload).eq("id", id);
    if (update.error) throw update.error;
    return;
  }

  const insert = await supabase.from("subscriptions").insert(payload);
  if (insert.error) throw insert.error;
}

async function getPayPalAccessToken(): Promise<string> {
  const clientId = requireEnv("PAYPAL_CLIENT_ID");
  const clientSecret = requireEnv("PAYPAL_CLIENT_SECRET");
  const basic = Buffer.from(`${clientId}:${clientSecret}`, "utf-8").toString("base64");
  const response = await fetch(`${paypalBaseUrl()}/v1/oauth2/token`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });
  const json = (await response.json()) as { access_token?: string; error_description?: string };
  if (!response.ok || !json.access_token) {
    throw new Error(json.error_description || "Unable to obtain PayPal token");
  }
  return json.access_token;
}

async function createPayPalCheckout(
  order: BillingOrderRow,
  pack: CreditPack,
  requestOrigin: string,
): Promise<{ checkoutUrl: string; providerOrderId: string }> {
  const accessToken = await getPayPalAccessToken();
  const returnUrl = `${requestOrigin}/api/billing/callback/paypal?order_id=${order.id}`;
  const cancelUrl = `${webAppUrl()}${sanitizeReturnPath(String(order.metadata?.return_path || "/handout"))}?billing=cancelled`;

  const payload = {
    intent: "CAPTURE",
    purchase_units: [
      {
        custom_id: order.id,
        reference_id: order.id,
        amount: {
          currency_code: "TWD",
          value: pack.amountTwd.toFixed(2),
        },
        description: `${pack.label} ${pack.credits} 次生成`,
      },
    ],
    payment_source: {
      paypal: {
        experience_context: {
          brand_name: "Etymon Decoder",
          locale: "zh-TW",
          user_action: "PAY_NOW",
          return_url: returnUrl,
          cancel_url: cancelUrl,
        },
      },
    },
  };

  const response = await fetchJson<{
    id: string;
    links?: Array<{ href: string; rel: string }>;
  }>(`${paypalBaseUrl()}/v2/checkout/orders`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    },
    body: JSON.stringify(payload),
  });

  const checkoutUrl =
    response.links?.find((item) => item.rel === "payer-action" || item.rel === "approve")?.href ||
    "";
  if (!checkoutUrl) {
    throw new Error("PayPal approval URL missing");
  }
  return { checkoutUrl, providerOrderId: response.id };
}

function signLinePay(path: string, body: string, nonce: string): string {
  const secret = requireEnv("LINE_PAY_CHANNEL_SECRET");
  const raw = `${secret}${path}${body}${nonce}`;
  return crypto.createHmac("sha256", secret).update(raw).digest("base64");
}

async function createLinePayCheckout(
  order: BillingOrderRow,
  pack: CreditPack,
  requestOrigin: string,
): Promise<{ checkoutUrl: string; providerOrderId: string; transactionId: string }> {
  const channelId = requireEnv("LINE_PAY_CHANNEL_ID");
  const path = "/v3/payments/request";
  const nonce = crypto.randomUUID();
  const confirmUrl = `${requestOrigin}/api/billing/callback/linepay?order_id=${order.id}`;
  const cancelUrl = `${webAppUrl()}${sanitizeReturnPath(String(order.metadata?.return_path || "/handout"))}?billing=cancelled`;
  const payload = {
    amount: pack.amountTwd,
    currency: "TWD",
    orderId: order.id,
    packages: [
      {
        id: pack.key,
        amount: pack.amountTwd,
        name: pack.label,
        products: [
          {
            id: pack.key,
            name: `${pack.label} ${pack.credits} 次生成`,
            quantity: 1,
            price: pack.amountTwd,
          },
        ],
      },
    ],
    redirectUrls: {
      confirmUrl,
      cancelUrl,
    },
  };
  const body = JSON.stringify(payload);
  const response = await fetchJson<{
    returnCode: string;
    returnMessage: string;
    info?: {
      transactionId?: string;
      paymentUrl?: { web?: string };
    };
  }>(`${linePayBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-LINE-ChannelId": channelId,
      "X-LINE-Authorization-Nonce": nonce,
      "X-LINE-Authorization": signLinePay(path, body, nonce),
    },
    body,
  });

  if (response.returnCode !== "0000" || !response.info?.paymentUrl?.web || !response.info.transactionId) {
    throw new Error(response.returnMessage || "LINE Pay request failed");
  }

  return {
    checkoutUrl: response.info.paymentUrl.web,
    providerOrderId: order.id,
    transactionId: response.info.transactionId,
  };
}

export async function createCheckoutSession(params: CheckoutParams): Promise<{
  checkoutUrl: string;
  orderId: string;
}> {
  const pack = getPack(params.packKey);
  if (!pack) {
    throw new Error("Unknown credit pack");
  }

  const order = await insertOrder(params, pack);
  if (params.provider === "paypal") {
    const created = await createPayPalCheckout(order, pack, params.requestOrigin);
    await updateOrder(order.id, {
      provider_order_id: created.providerOrderId,
      checkout_url: created.checkoutUrl,
      status: "awaiting_payment",
    });
    return { checkoutUrl: created.checkoutUrl, orderId: order.id };
  }

  const created = await createLinePayCheckout(order, pack, params.requestOrigin);
  await updateOrder(order.id, {
    provider_order_id: created.providerOrderId,
    provider_transaction_id: created.transactionId,
    checkout_url: created.checkoutUrl,
    status: "awaiting_payment",
  });
  return { checkoutUrl: created.checkoutUrl, orderId: order.id };
}

function successRedirect(order: BillingOrderRow): string {
  const returnPath = sanitizeReturnPath(String(order.metadata?.return_path || "/handout"));
  return `${webAppUrl()}${returnPath}?billing=success`;
}

function failureRedirect(order: BillingOrderRow): string {
  const returnPath = sanitizeReturnPath(String(order.metadata?.return_path || "/handout"));
  return `${webAppUrl()}${returnPath}?billing=failed`;
}

export async function finalizePayPalCallback(
  orderId: string,
  providerOrderId: string,
): Promise<string> {
  const order = await getOrderById(orderId);
  const accessToken = await getPayPalAccessToken();

  const capture = await fetchJson<{
    id: string;
    status?: string;
    purchase_units?: Array<{
      payments?: {
        captures?: Array<{ id: string; status?: string }>;
      };
    }>;
  }>(`${paypalBaseUrl()}/v2/checkout/orders/${providerOrderId}/capture`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    },
    body: "{}",
  });

  const captureId = capture.purchase_units?.[0]?.payments?.captures?.[0]?.id || null;
  const completed =
    capture.status === "COMPLETED" ||
    capture.purchase_units?.[0]?.payments?.captures?.[0]?.status === "COMPLETED";
  if (!completed) {
    await updateOrder(order.id, {
      status: "payment_failed",
      provider_payment_id: captureId,
      metadata: { ...(order.metadata || {}), paypal_capture: capture },
    });
    return failureRedirect(order);
  }

  await updateOrder(order.id, {
    status: "paid",
    provider_order_id: providerOrderId,
    provider_payment_id: captureId,
    metadata: { ...(order.metadata || {}), paypal_capture: capture },
  });
  await grantCredits(order);
  await touchSubscription(order);
  return successRedirect(order);
}

export async function finalizeLinePayCallback(orderId: string, transactionId: string): Promise<string> {
  const order = await getOrderById(orderId);
  const path = `/v3/payments/${transactionId}/confirm`;
  const nonce = crypto.randomUUID();
  const body = JSON.stringify({
    amount: order.amount_minor,
    currency: order.currency,
  });
  const response = await fetchJson<{
    returnCode: string;
    returnMessage: string;
    info?: Record<string, unknown>;
  }>(`${linePayBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-LINE-ChannelId": requireEnv("LINE_PAY_CHANNEL_ID"),
      "X-LINE-Authorization-Nonce": nonce,
      "X-LINE-Authorization": signLinePay(path, body, nonce),
    },
    body,
  });

  if (response.returnCode !== "0000") {
    await updateOrder(order.id, {
      status: "payment_failed",
      metadata: { ...(order.metadata || {}), linepay_confirm: response },
    });
    return failureRedirect(order);
  }

  await updateOrder(order.id, {
    status: "paid",
    provider_transaction_id: transactionId,
    metadata: { ...(order.metadata || {}), linepay_confirm: response },
  });
  await grantCredits(order);
  await touchSubscription(order);
  return successRedirect(order);
}

export async function cancelProviderOrder(
  provider: BillingProvider,
  providerOrderId: string,
): Promise<string> {
  const order = await getOrderByProviderOrderId(provider, providerOrderId);
  await updateOrder(order.id, { status: "cancelled" });
  return `${webAppUrl()}${sanitizeReturnPath(String(order.metadata?.return_path || "/handout"))}?billing=cancelled`;
}
