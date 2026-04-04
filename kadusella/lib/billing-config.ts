export type CreditPack = {
  key: string;
  label: string;
  amountTwd: number;
  credits: number;
  recommended?: boolean;
};

export const CREDIT_PACKS: CreditPack[] = [
  { key: "pack_50",  label: "小包",  amountTwd: 50,  credits: 10 },
  { key: "pack_100", label: "中包",  amountTwd: 100, credits: 20, recommended: true },
  { key: "pack_200", label: "大包",  amountTwd: 200, credits: 40 },
];

export const CREDITS_PER_TWD = 5;

export function getPack(packKey: string): CreditPack | null {
  return CREDIT_PACKS.find((pack) => pack.key === packKey) ?? null;
}
