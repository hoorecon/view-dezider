import { create } from 'zustand';
import api from '../utils/api';

interface AiWallet {
  balance: number;
  is_admin: boolean;
  unit: string;
  tokens_per_credit: number;
}

interface AiWalletState {
  balance: number;
  tokensPerCredit: number;
  isAdmin: boolean;
  loaded: boolean;
  loading: boolean;
  refresh: () => Promise<void>;
}

export const useAiWalletStore = create<AiWalletState>((set) => ({
  balance: 0,
  tokensPerCredit: 100,
  isAdmin: false,
  loaded: false,
  loading: false,

  refresh: async () => {
    set({ loading: true });
    try {
      const res = await api.get<AiWallet>('/ai-wallet');
      set({
        balance: Number(res.data?.balance ?? 0),
        tokensPerCredit: Number(res.data?.tokens_per_credit ?? 100),
        isAdmin: !!res.data?.is_admin,
        loaded: true,
        loading: false,
      });
    } catch {
      set({ loading: false, loaded: true });
    }
  },
}));
