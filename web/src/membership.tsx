import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ClerkProvider, useAuth, useClerk } from "@clerk/clerk-react";
import type { CreditPack, MembershipBootstrap } from "./types";
import { clearMemberToken, setMemberToken } from "./lib/memberToken";

const clerkPublishableKey = (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "").trim();
const billingBaseUrl = (import.meta.env.VITE_BILLING_BASE_URL || "").trim().replace(/\/$/, "");

type BillingProvider = "linepay" | "paypal";

type MembershipContextValue = {
  clerkEnabled: boolean;
  loading: boolean;
  ready: boolean;
  signedIn: boolean;
  canGenerate: boolean;
  error: string | null;
  profile: MembershipBootstrap["profile"] | null;
  tenant: MembershipBootstrap["tenant"] | null;
  subscription: MembershipBootstrap["subscription"] | null;
  walletCredits: number;
  contributorLabel: string;
  packs: CreditPack[];
  refreshMembership: () => Promise<void>;
  startCheckout: (provider: BillingProvider, packKey: string, returnPath?: string) => Promise<void>;
  openSignIn: () => void;
};

const noopAsync = async () => {};

const MembershipContext = createContext<MembershipContextValue>({
  clerkEnabled: false,
  loading: false,
  ready: true,
  signedIn: false,
  canGenerate: false,
  error: "Clerk 未設定",
  profile: null,
  tenant: null,
  subscription: null,
  walletCredits: 0,
  contributorLabel: "",
  packs: [],
  refreshMembership: noopAsync,
  startCheckout: noopAsync,
  openSignIn: () => {},
});

function MembershipRuntime({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const clerk = useClerk();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<MembershipBootstrap | null>(null);

  const refreshMembership = useCallback(async () => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      clearMemberToken();
      setSnapshot(null);
      setError(null);
      setLoading(false);
      return;
    }

    if (!billingBaseUrl) {
      clearMemberToken();
      setSnapshot(null);
      setError("未設定 VITE_BILLING_BASE_URL，無法取得會員與付款狀態。");
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const token = await getToken();
      if (!token) {
        throw new Error("無法取得登入憑證，請重新登入。");
      }
      const response = await fetch(`${billingBaseUrl}/api/auth/bootstrap`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const json = (await response.json().catch(() => ({}))) as
        | MembershipBootstrap
        | { error?: string };
      if (!response.ok) {
        throw new Error("error" in json && json.error ? json.error : "會員初始化失敗");
      }
      setSnapshot(json as MembershipBootstrap);
      setMemberToken((json as MembershipBootstrap).backendToken);
      setError(null);
    } catch (err) {
      clearMemberToken();
      setSnapshot(null);
      setError(err instanceof Error ? err.message : "會員初始化失敗");
    } finally {
      setLoading(false);
    }
  }, [getToken, isLoaded, isSignedIn]);

  useEffect(() => {
    refreshMembership().catch(() => undefined);
  }, [refreshMembership]);

  const startCheckout = useCallback(
    async (provider: BillingProvider, packKey: string, returnPath = window.location.pathname) => {
      if (!billingBaseUrl) {
        throw new Error("未設定 VITE_BILLING_BASE_URL，無法啟動付款。");
      }
      const token = await getToken();
      if (!token) {
        throw new Error("請先登入會員。");
      }
      const response = await fetch(`${billingBaseUrl}/api/billing/checkout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ provider, packKey, returnPath }),
      });
      const json = (await response.json().catch(() => ({}))) as {
        checkoutUrl?: string;
        error?: string;
      };
      if (!response.ok || !json.checkoutUrl) {
        throw new Error(json.error || "建立付款訂單失敗");
      }
      window.location.href = json.checkoutUrl;
    },
    [getToken],
  );

  const value = useMemo<MembershipContextValue>(
    () => ({
      clerkEnabled: true,
      loading,
      ready: isLoaded && !loading,
      signedIn: Boolean(isSignedIn),
      canGenerate: snapshot?.access.canGenerate ?? false,
      error,
      profile: snapshot?.profile ?? null,
      tenant: snapshot?.tenant ?? null,
      subscription: snapshot?.subscription ?? null,
      walletCredits: snapshot?.wallet.creditsBalance ?? 0,
      contributorLabel: snapshot?.access.contributorLabel ?? "",
      packs: snapshot?.packs ?? [],
      refreshMembership,
      startCheckout,
      openSignIn: () => clerk.openSignIn(),
    }),
    [clerk, error, isLoaded, isSignedIn, loading, refreshMembership, snapshot, startCheckout],
  );

  return <MembershipContext.Provider value={value}>{children}</MembershipContext.Provider>;
}

export function MembershipProvider({ children }: { children: ReactNode }) {
  if (!clerkPublishableKey) {
    return (
      <MembershipContext.Provider
        value={{
          clerkEnabled: false,
          loading: false,
          ready: true,
          signedIn: false,
          canGenerate: false,
          error: "未設定 VITE_CLERK_PUBLISHABLE_KEY，會員登入未啟用。",
          profile: null,
          tenant: null,
          subscription: null,
          walletCredits: 0,
          contributorLabel: "",
          packs: [],
          refreshMembership: noopAsync,
          startCheckout: noopAsync,
          openSignIn: () => {},
        }}
      >
        {children}
      </MembershipContext.Provider>
    );
  }

  return (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      <MembershipRuntime>{children}</MembershipRuntime>
    </ClerkProvider>
  );
}

export function useMembership() {
  return useContext(MembershipContext);
}
