export type KnowledgeRow = {
  word?: string;
  category?: string;
  roots?: string;
  breakdown?: string;
  definition?: string;
  meaning?: string;
  native_vibe?: string;
  example?: string;
  synonym_nuance?: string;
  usage_warning?: string;
  memory_hook?: string;
  phonetic?: string;
};

export type RootWord = { w: string; zh: string };

export type RootEntry = {
  id: string;
  root: string;
  variants?: string[];
  origin: string;
  meaning: string;
  note?: string;
  words?: RootWord[];
};

export type ExamSubject = {
  name: string;
  chapters: { name: string; units: { name: string }[] }[];
};

export type ExamSearchHit = {
  subject: string;
  chapter: string;
  unit: string;
  snippet: string;
};

export type ContributionMode = "named_contribution" | "private_use";

export type CreditPack = {
  key: string;
  label: string;
  amountTwd: number;
  credits: number;
  recommended?: boolean;
};

export type MembershipBootstrap = {
  profile: {
    id: string;
    email: string;
    displayName: string;
  };
  tenant: {
    id: string;
  };
  subscription: {
    planKey: string;
    status: string;
    currentPeriodEnd: string | null;
  };
  wallet: {
    creditsBalance: number;
  };
  access: {
    canGenerate: boolean;
    contributorLabel: string;
  };
  backendToken: string;
  packs: CreditPack[];
};
