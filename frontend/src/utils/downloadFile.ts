import { Platform } from 'react-native';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';

function backendBase(): string {
  return (Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL as string)
    || (process.env.EXPO_PUBLIC_BACKEND_URL as string) || '';
}

/**
 * Download an auth-protected file from the backend (path AFTER `/api`).
 * Web → triggers a browser download. Native → saves to cache + opens the share sheet.
 */
export async function downloadAuthedFile(apiPath: string, filename: string, mime: string): Promise<void> {
  const token = await AsyncStorage.getItem('session_token');
  const url = `${backendBase()}/api${apiPath}`;

  if (Platform.OS === 'web') {
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Download failed (${res.status})`);
    const blob = await res.blob();
    const objUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(objUrl);
    return;
  }

  const fileUri = (FileSystem.cacheDirectory || '') + filename;
  const dl = await FileSystem.downloadAsync(url, fileUri, { headers: { Authorization: `Bearer ${token}` } });
  if (dl.status < 200 || dl.status >= 300) throw new Error(`Download failed (${dl.status})`);
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(dl.uri, { mimeType: mime, dialogTitle: filename });
  }
}
