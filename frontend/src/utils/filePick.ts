import { Platform } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';

export interface PickedFile {
  filename: string;
  base64: string;       // raw base64 (no data: prefix)
  mimeType: string;
  sizeBytes: number;
}

const ACCEPT = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',       // .xlsx
  'application/vnd.ms-excel',                                                // .xls
  'text/plain', 'text/csv',
  'image/jpeg', 'image/png', 'image/webp',
];

function stripDataPrefix(b64: string): string {
  const idx = b64.indexOf('base64,');
  return idx >= 0 ? b64.slice(idx + 'base64,'.length) : b64;
}

/** Cross-platform: open the document picker and return the file as base64. */
export async function pickAndReadFile(): Promise<PickedFile | null> {
  const res = await DocumentPicker.getDocumentAsync({
    type: ACCEPT,
    copyToCacheDirectory: true,
    multiple: false,
  });
  if (res.canceled || !res.assets || res.assets.length === 0) return null;
  const asset = res.assets[0];
  const filename = asset.name || 'upload';
  const mimeType = asset.mimeType || 'application/octet-stream';

  // Web: the asset carries a File object → read via FileReader.
  if (Platform.OS === 'web') {
    const file: File | undefined = (asset as any).file;
    if (file) {
      const base64: string = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(stripDataPrefix(String(reader.result || '')));
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      return { filename, base64, mimeType, sizeBytes: file.size };
    }
    // Fallback: fetch the blob URI.
    const blob = await (await fetch(asset.uri)).blob();
    const base64: string = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(stripDataPrefix(String(reader.result || '')));
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    return { filename, base64, mimeType, sizeBytes: blob.size };
  }

  // Native: read the cached file as base64 via the new expo-file-system File API.
  const base64 = await new File(asset.uri).base64();
  return { filename, base64, mimeType, sizeBytes: asset.size || 0 };
}
