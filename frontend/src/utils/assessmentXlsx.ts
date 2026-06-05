import { Platform } from 'react-native';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import * as DocumentPicker from 'expo-document-picker';

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

function backendBase(): string {
  return (Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL as string) || (process.env.EXPO_PUBLIC_BACKEND_URL as string) || '';
}

/**
 * Download an assessment .xlsx template from the backend (auth-protected).
 * Web → triggers a browser download. Native → saves to cache + opens the share sheet.
 * `apiPath` is the path AFTER `/api`, e.g. `/pros-cons/<id>/assessment-template`.
 */
export async function downloadAssessmentTemplate(apiPath: string, filename = 'assessment.xlsx'): Promise<void> {
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

  // Native — download with auth header, then share.
  const fileUri = (FileSystem.cacheDirectory || '') + filename;
  const dl = await FileSystem.downloadAsync(url, fileUri, { headers: { Authorization: `Bearer ${token}` } });
  if (dl.status < 200 || dl.status >= 300) throw new Error(`Download failed (${dl.status})`);
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(dl.uri, { mimeType: XLSX_MIME, dialogTitle: 'Assessment template' });
  }
}

/**
 * Let the user pick a filled .xlsx and upload it to the backend.
 * Returns the parsed JSON ({ applied, rows }) or null if cancelled.
 * `apiPath` is the path AFTER `/api`, e.g. `/pros-cons/<id>/assessment-import`.
 */
export async function importAssessmentTemplate(apiPath: string): Promise<{ applied: number; rows: number } | null> {
  const pick = await DocumentPicker.getDocumentAsync({
    type: [XLSX_MIME, 'application/vnd.ms-excel', '*/*'],
    copyToCacheDirectory: true,
    multiple: false,
  });
  if (pick.canceled || !pick.assets || pick.assets.length === 0) return null;
  const asset = pick.assets[0];

  const token = await AsyncStorage.getItem('session_token');
  const url = `${backendBase()}/api${apiPath}`;
  const form = new FormData();

  if (Platform.OS === 'web') {
    // On web the picked asset exposes a File object.
    const f: any = (asset as any).file || (await (await fetch(asset.uri)).blob());
    form.append('file', f, asset.name || 'assessment.xlsx');
  } else {
    form.append('file', {
      uri: asset.uri,
      name: asset.name || 'assessment.xlsx',
      type: asset.mimeType || XLSX_MIME,
    } as any);
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    let msg = `Import failed (${res.status})`;
    try {
      const j = await res.json();
      msg = j?.detail || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return await res.json();
}
