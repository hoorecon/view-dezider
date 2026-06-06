import { Platform } from 'react-native';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';

/**
 * Google Sheets helpers — connect (OAuth), create a pre-filled assessment
 * sheet in the user's own Drive, and import the filled sheet back.
 * Shared by My Dezider (Step 7) and Pros & Cons assessment steps.
 */

function backendBase(): string {
  return (Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL as string) || (process.env.EXPO_PUBLIC_BACKEND_URL as string) || '';
}

function returnUrl(): string {
  if (Platform.OS === 'web' && typeof window !== 'undefined') return window.location.origin;
  return Linking.createURL('/');
}

export interface SheetsStatus { connected: boolean; email?: string; can_refresh?: boolean }

export async function getSheetsStatus(): Promise<SheetsStatus> {
  const token = await AsyncStorage.getItem('session_token');
  const res = await fetch(`${backendBase()}/api/oauth/sheets/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return { connected: false };
  return await res.json();
}

/** Launch the Google OAuth consent flow; resolves to true once connected. */
export async function connectGoogleSheets(): Promise<boolean> {
  const token = await AsyncStorage.getItem('session_token');
  const ret = returnUrl();
  const loginUrl = `${backendBase()}/api/oauth/sheets/login?token=${encodeURIComponent(token || '')}&return_to=${encodeURIComponent(ret)}`;
  try {
    await WebBrowser.openAuthSessionAsync(loginUrl, ret);
  } catch {
    // ignore — we verify via status below regardless of how the browser closed
  }
  const status = await getSheetsStatus();
  return !!status.connected;
}

export async function disconnectGoogleSheets(): Promise<void> {
  const token = await AsyncStorage.getItem('session_token');
  await fetch(`${backendBase()}/api/oauth/sheets/disconnect`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` },
  });
}

async function postJson(apiPath: string, body?: any): Promise<any> {
  const token = await AsyncStorage.getItem('session_token');
  const res = await fetch(`${backendBase()}/api${apiPath}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body || {}),
  });
  if (res.status === 428) {
    const e: any = new Error('NEEDS_CONNECT');
    e.code = 'NEEDS_CONNECT';
    throw e;
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { const j = await res.json(); msg = j?.detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return await res.json();
}

/**
 * Create a Google Sheet for this analysis/decision. If not connected, runs the
 * OAuth flow first and retries once.
 * `apiPath` is the path AFTER `/api`, e.g. `/pros-cons/<id>/assessment-gsheet`.
 */
export async function createAssessmentGsheet(apiPath: string): Promise<{ url: string; spreadsheet_id: string }> {
  try {
    return await postJson(apiPath);
  } catch (e: any) {
    if (e?.code === 'NEEDS_CONNECT') {
      const ok = await connectGoogleSheets();
      if (!ok) throw new Error('Google account not connected.');
      return await postJson(apiPath);
    }
    throw e;
  }
}

/** Import the filled (linked) Google Sheet. Connects first if needed. */
export async function importAssessmentGsheet(apiPath: string, spreadsheetId?: string): Promise<{ applied: number; rows: number }> {
  const body = spreadsheetId ? { spreadsheet_id: spreadsheetId } : {};
  try {
    return await postJson(apiPath, body);
  } catch (e: any) {
    if (e?.code === 'NEEDS_CONNECT') {
      const ok = await connectGoogleSheets();
      if (!ok) throw new Error('Google account not connected.');
      return await postJson(apiPath, body);
    }
    throw e;
  }
}

export async function openSheetUrl(url: string): Promise<void> {
  if (!url) return;
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    window.open(url, '_blank');
    return;
  }
  await WebBrowser.openBrowserAsync(url);
}
