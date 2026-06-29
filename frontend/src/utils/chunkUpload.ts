import api from './api';
import { PickedFile } from './filePick';

// Each request carries ~512 KB of base64 text — comfortably below the 1 MB body
// limit that reverse proxies (nginx default) impose, so large files never 413.
const CHUNK_CHARS = 512 * 1024;

/**
 * Upload a picked file to the backend as many small base64 chunks and return the
 * server-side `upload_id`. Pass that id (instead of a giant `file_b64`) to any
 * endpoint that accepts `upload_id`. `onProgress` reports 0..1.
 */
export async function uploadFileChunked(
  picked: PickedFile,
  onProgress?: (fraction: number) => void,
): Promise<string> {
  const { data } = await api.post('/uploads/init', { filename: picked.filename });
  const uploadId: string = data.upload_id;

  const b64 = picked.base64 || '';
  const total = Math.max(1, Math.ceil(b64.length / CHUNK_CHARS));
  for (let i = 0; i < total; i++) {
    const chunk = b64.slice(i * CHUNK_CHARS, (i + 1) * CHUNK_CHARS);
    await api.post('/uploads/chunk', {
      upload_id: uploadId, index: i, total, chunk_b64: chunk,
    }, { timeout: 60000 });
    onProgress?.((i + 1) / total);
  }
  return uploadId;
}
