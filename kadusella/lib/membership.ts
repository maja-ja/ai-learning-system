import crypto from "node:crypto";
import type { SupabaseClient } from "@supabase/supabase-js";
import { createSupabaseAdmin } from "@/lib/supabase-admin";
import type { VerifiedMember } from "@/lib/clerk-auth";

type ProfileRow = {
  id: string;
  clerk_user_id: string;
  email: string | null;
  display_name: string | null;
  avatar_url: string | null;
  default_tenant_id: string | null;
};

type TenantMemberRow = {
  tenant_id: string;
};

type SubscriptionRow = {
  id: string;
  plan_key: string;
  status: string;
  current_period_end: string | null;
};

export type MembershipSnapshot = {
  profileId: string;
  tenantId: string;
  email: string;
  displayName: string;
  subscription: {
    planKey: string;
    status: string;
    currentPeriodEnd: string | null;
  };
  creditsBalance: number;
  canGenerate: boolean;
};

function slugify(input: string): string {
  const normalized = input
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || "member";
}

function activeSubscription(row: SubscriptionRow | null): boolean {
  if (!row) return false;
  if (!["active", "trialing"].includes(row.status)) return false;
  if (!row.current_period_end) return true;
  return Date.parse(row.current_period_end) > Date.now();
}

async function ensureTenantAndProfile(
  supabase: SupabaseClient,
  member: VerifiedMember,
): Promise<{ profile: ProfileRow; tenantId: string }> {
  const profileResult = await supabase
    .from("profiles")
    .select("id, clerk_user_id, email, display_name, avatar_url, default_tenant_id")
    .eq("clerk_user_id", member.clerkUserId)
    .maybeSingle<ProfileRow>();
  if (profileResult.error) throw profileResult.error;

  let profile = profileResult.data;
  let tenantId = profile?.default_tenant_id || null;

  if (!profile) {
    const tenantInsert = await supabase
      .from("tenants")
      .insert({
        name: `${member.displayName} Workspace`,
        slug: `${slugify(member.displayName)}-${member.clerkUserId.slice(-6)}`,
        metadata: { kind: "personal_workspace" },
      })
      .select("id")
      .single<{ id: string }>();
    if (tenantInsert.error) throw tenantInsert.error;
    tenantId = tenantInsert.data.id;

    const profileInsert = await supabase
      .from("profiles")
      .insert({
        clerk_user_id: member.clerkUserId,
        email: member.email || null,
        display_name: member.displayName,
        avatar_url: member.avatarUrl || null,
        default_tenant_id: tenantId,
      })
      .select("id, clerk_user_id, email, display_name, avatar_url, default_tenant_id")
      .single<ProfileRow>();
    if (profileInsert.error) throw profileInsert.error;
    profile = profileInsert.data;

    const tenantMemberInsert = await supabase.from("tenant_members").insert({
      tenant_id: tenantId,
      profile_id: profile.id,
      role: "student",
    });
    if (tenantMemberInsert.error) throw tenantMemberInsert.error;
  } else {
    const profileUpdate = await supabase
      .from("profiles")
      .update({
        email: member.email || profile.email,
        display_name: member.displayName || profile.display_name,
        avatar_url: member.avatarUrl || profile.avatar_url,
      })
      .eq("id", profile.id);
    if (profileUpdate.error) throw profileUpdate.error;

    if (!tenantId) {
      const tenantResult = await supabase
        .from("tenant_members")
        .select("tenant_id")
        .eq("profile_id", profile.id)
        .limit(1)
        .maybeSingle<TenantMemberRow>();
      if (tenantResult.error) throw tenantResult.error;
      tenantId = tenantResult.data?.tenant_id || null;
    }

    if (!tenantId) {
      const tenantInsert = await supabase
        .from("tenants")
        .insert({
          name: `${member.displayName} Workspace`,
          slug: `${slugify(member.displayName)}-${crypto.randomUUID().slice(0, 8)}`,
          metadata: { kind: "personal_workspace_recovered" },
        })
        .select("id")
        .single<{ id: string }>();
      if (tenantInsert.error) throw tenantInsert.error;
      tenantId = tenantInsert.data.id;

      const tenantMemberInsert = await supabase.from("tenant_members").insert({
        tenant_id: tenantId,
        profile_id: profile.id,
        role: "student",
      });
      if (tenantMemberInsert.error) throw tenantMemberInsert.error;

      const tenantBind = await supabase
        .from("profiles")
        .update({ default_tenant_id: tenantId })
        .eq("id", profile.id);
      if (tenantBind.error) throw tenantBind.error;
    }
  }

  if (!tenantId || !profile) {
    throw new Error("Failed to resolve member workspace");
  }

  const defaultSubscription = await supabase
    .from("subscriptions")
    .select("id")
    .eq("tenant_id", tenantId)
    .limit(1);
  if (defaultSubscription.error) throw defaultSubscription.error;
  if ((defaultSubscription.data || []).length === 0) {
    const insertSubscription = await supabase.from("subscriptions").insert({
      tenant_id: tenantId,
      plan_key: "free",
      status: "incomplete",
      metadata: { source: "bootstrap" },
    });
    if (insertSubscription.error) throw insertSubscription.error;
  }

  return { profile, tenantId };
}

async function fetchLatestSubscription(
  supabase: SupabaseClient,
  tenantId: string,
): Promise<SubscriptionRow | null> {
  const result = await supabase
    .from("subscriptions")
    .select("id, plan_key, status, current_period_end")
    .eq("tenant_id", tenantId)
    .order("updated_at", { ascending: false })
    .limit(1);
  if (result.error) throw result.error;
  return ((result.data || [])[0] as SubscriptionRow | undefined) || null;
}

async function fetchCreditsBalance(supabase: SupabaseClient, tenantId: string): Promise<number> {
  const result = await supabase.rpc("current_credit_balance", {
    p_tenant_id: tenantId,
  });
  if (result.error) throw result.error;
  return Number(result.data || 0);
}

export async function bootstrapMembership(member: VerifiedMember): Promise<MembershipSnapshot> {
  const supabase = createSupabaseAdmin();
  const { profile, tenantId } = await ensureTenantAndProfile(supabase, member);
  const subscription = await fetchLatestSubscription(supabase, tenantId);
  const creditsBalance = await fetchCreditsBalance(supabase, tenantId);
  const canGenerate = activeSubscription(subscription) || creditsBalance > 0;

  return {
    profileId: profile.id,
    tenantId,
    email: member.email,
    displayName: member.displayName,
    subscription: {
      planKey: subscription?.plan_key || "free",
      status: subscription?.status || "incomplete",
      currentPeriodEnd: subscription?.current_period_end || null,
    },
    creditsBalance,
    canGenerate,
  };
}
