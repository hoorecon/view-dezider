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
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  sessionToken: string | null;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setSessionToken: (token: string | null) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  loginWithGoogle: (sessionId: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  sessionToken: null,

  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setLoading: (isLoading) => set({ isLoading }),
  setSessionToken: (sessionToken) => set({ sessionToken }),

  login: async (email, password) => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/login`, {
        email,
        password,
      }, { withCredentials: true });

      const { session_token, ...userData } = response.data;
      await AsyncStorage.setItem('session_token', session_token);
      set({ user: userData, isAuthenticated: true, sessionToken: session_token });
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  },

  register: async (email, password, name) => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/register`, {
        email,
        password,
        name,
      }, { withCredentials: true });

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
      }, { withCredentials: true });

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
        withCredentials: true,
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
        withCredentials: true,
        headers: { Authorization: `Bearer ${token}` },
      });

      set({ user: response.data, isAuthenticated: true, sessionToken: token, isLoading: false });
    } catch (error) {
      await AsyncStorage.removeItem('session_token');
      set({ user: null, isAuthenticated: false, sessionToken: null, isLoading: false });
    }
  },
}));
