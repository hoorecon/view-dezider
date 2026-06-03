import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { Platform } from 'react-native';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface User {
  user_id: string;
  email: string;
  name: string;
  picture?: string;
  auth_method: string;
  org_id?: string;
  org_role?: string;
  role?: string;
  user_type?: string;
  is_admin?: boolean;
  can_view_pii?: boolean;
  gender?: string | null;
  has_custom_picture?: boolean;
  whatsapp_number?: string | null;
  whatsapp_verified?: boolean;
}

interface OrgBranding {
  id: string;
  name: string;
  slug: string;
  org_type?: string;
  logo_url?: string;
  primary_color?: string;
  accent_color?: string;
  tagline?: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  sessionToken: string | null;
  orgBranding: OrgBranding | null;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setSessionToken: (token: string | null) => void;
  setOrgBranding: (branding: OrgBranding | null) => void;
  setSession: (sessionToken: string, userData: any) => Promise<void>;
  login: (email: string, password: string, orgId?: string) => Promise<void>;
  register: (email: string, password: string, name: string, orgId?: string) => Promise<void>;
  loginWithGoogle: (sessionId: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  fetchOrgBranding: (slug: string) => Promise<OrgBranding | null>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  sessionToken: null,
  orgBranding: null,

  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setLoading: (isLoading) => set({ isLoading }),
  setSessionToken: (sessionToken) => set({ sessionToken }),
  setOrgBranding: (orgBranding) => set({ orgBranding }),

  setSession: async (sessionToken: string, userData: any) => {
    await AsyncStorage.setItem('session_token', sessionToken);
    if (userData.org_id) await AsyncStorage.setItem('org_id', userData.org_id);
    set({ user: userData, isAuthenticated: true, sessionToken });
  },

  fetchOrgBranding: async (slug: string) => {
    try {
      const response = await axios.get(`${API_URL}/api/organizations/${slug}`);
      const branding = response.data;
      set({ orgBranding: branding });
      await AsyncStorage.setItem('org_slug', slug);
      return branding;
    } catch (error) {
      return null;
    }
  },

  login: async (email, password, orgId) => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/login`, {
        email,
        password,
        org_id: orgId,
      });

      const { session_token, ...userData } = response.data;
      await AsyncStorage.setItem('session_token', session_token);
      if (orgId) await AsyncStorage.setItem('org_id', orgId);
      set({ user: userData, isAuthenticated: true, sessionToken: session_token });
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  },

  register: async (email, password, name, orgId) => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/register`, {
        email,
        password,
        name,
        org_id: orgId,
      });

      const { session_token, ...userData } = response.data;
      await AsyncStorage.setItem('session_token', session_token);
      set({ user: userData, isAuthenticated: true, sessionToken: session_token });
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Registration failed');
    }
  },

  loginWithGoogle: async (sessionId) => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/google/session`, {
        session_id: sessionId,
      });

      const { session_token, ...userData } = response.data;
      await AsyncStorage.setItem('session_token', session_token);
      set({ user: userData, isAuthenticated: true, sessionToken: session_token });
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Google login failed');
    }
  },

  logout: async () => {
    try {
      const token = await AsyncStorage.getItem('session_token');
      await axios.post(`${API_URL}/api/auth/logout`, {}, {
        
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch (error) {
      console.log('Logout error:', error);
    } finally {
      await AsyncStorage.removeItem('session_token');
      set({ user: null, isAuthenticated: false, sessionToken: null });
    }
  },

  checkAuth: async () => {
    try {
      const token = await AsyncStorage.getItem('session_token');
      if (!token) {
        set({ user: null, isAuthenticated: false, isLoading: false });
        return;
      }

      const response = await axios.get(`${API_URL}/api/auth/me`, {
        
        headers: { Authorization: `Bearer ${token}` },
      });

      set({ user: response.data, isAuthenticated: true, sessionToken: token, isLoading: false });
    } catch (error) {
      await AsyncStorage.removeItem('session_token');
      set({ user: null, isAuthenticated: false, sessionToken: null, isLoading: false });
    }
  },
}));
