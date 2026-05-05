import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  // NOTE: withCredentials is NOT needed here — auth uses Bearer token via the
  // request interceptor below (AsyncStorage → Authorization header). Setting
  // withCredentials:true forces cross-origin browsers to require a non-wildcard
  // ACAO header which breaks localhost test harnesses against the preview URL.
});

// Add auth token to all requests
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('session_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await AsyncStorage.removeItem('session_token');
    }
    return Promise.reject(error);
  }
);

export default api;
