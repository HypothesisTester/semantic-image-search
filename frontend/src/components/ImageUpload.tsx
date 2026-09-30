import { useState } from 'react';
import type { ChangeEvent } from 'react';
import { doc, setDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../config/firebase';
import { UPLOAD_BATCH_SIZE } from '../config/api';
import { uploadPhotos } from '../api';
import type { UploadResult } from '../api';
import { useAuth } from '../contexts/AuthContext';
import UploadProgress from './UploadProgress';
import type { UploadItem } from './UploadProgress';

interface ImageUploadProps {
  onUploadError?: (error: string) => void;
}

// Formats the indexer can decode. DNG needs the backend's optional rawpy
// dependency; without it the indexer rejects the file with a clear message.
const ALLOWED_EXTENSIONS = [
  '.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.gif', '.bmp', '.tiff', '.tif', '.dng',
];

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

export default function ImageUpload({ onUploadError }: ImageUploadProps) {
  const { currentUser } = useAuth();
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [showProgress, setShowProgress] = useState(false);

  const update = (ids: string[], patch: Partial<UploadItem>) =>
    setUploads(prev => prev.map(u => (ids.includes(u.id) ? { ...u, ...patch } : u)));

  // The gallery reads photo records from Firestore. Each record is keyed by
  // the photo id the indexer returns, which is derived from the photo's
  // content: uploading the same photo again rewrites its record instead of
  // adding a second copy to the gallery.
  const saveRecord = async (uid: string, file: File, result: UploadResult) => {
    await setDoc(doc(db, 'users', uid, 'images', result.id!), {
      url: result.url,
      thumbnailUrl: result.thumbnailUrl,
      fileName: file.name,
      fileSize: file.size,
      fileType: file.type,
      uploadedAt: serverTimestamp(),
    });
  };

  const uploadBatch = async (uid: string, batch: UploadItem[]) => {
    const ids = batch.map(u => u.id);
    update(ids, { status: 'uploading' });
    let results: UploadResult[];
    try {
      results = await uploadPhotos(batch.map(u => u.file));
    } catch (err) {
      update(ids, { status: 'error', error: err instanceof Error ? err.message : String(err) });
      return;
    }
    await Promise.all(
      batch.map(async (item, i) => {
        const result = results[i];
        if (!result?.ok) {
          update([item.id], { status: 'error', error: result?.error ?? 'not processed' });
          return;
        }
        try {
          await saveRecord(uid, item.file, result);
          URL.revokeObjectURL(item.preview);
          // The server's JPEG thumbnail also works for HEIC, which most
          // browsers cannot preview from the original file.
          update([item.id], { status: 'completed', progress: 100, url: result.url, preview: result.thumbnailUrl! });
        } catch (err) {
          update([item.id], {
            status: 'error',
            error: `indexed, but not saved to your gallery: ${err instanceof Error ? err.message : err}`,
          });
        }
      }),
    );
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const input = e.target;
    const files = Array.from(input.files ?? []);
    input.value = ''; // allow choosing the same files again later
    if (files.length === 0) return;

    if (!currentUser) {
      onUploadError?.('You must be logged in to upload images');
      return;
    }

    const isAllowed = (f: File) =>
      ALLOWED_EXTENSIONS.includes('.' + (f.name.split('.').pop() ?? '').toLowerCase());
    const valid = files.filter(isAllowed);
    const invalid = files.filter(f => !isAllowed(f)).map(f => f.name);
    if (invalid.length > 0) {
      onUploadError?.(`Not an image format we support: ${invalid.join(', ')}`);
    }
    if (valid.length === 0) return;

    const items: UploadItem[] = valid.map(file => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`,
      file,
      preview: URL.createObjectURL(file),
      status: 'pending',
      progress: 0,
    }));
    setUploads(items);
    setShowProgress(true);

    // Batches go one after another: each is one request and one CLIP batch
    // on the indexer, so sending them all at once would only queue them there.
    for (const batch of chunk(items, UPLOAD_BATCH_SIZE)) {
      await uploadBatch(currentUser.uid, batch);
    }
  };

  const handleCloseProgress = () => {
    setShowProgress(false);
    uploads.forEach(u => {
      if (u.preview.startsWith('blob:')) URL.revokeObjectURL(u.preview);
    });
    setUploads([]);
  };

  return (
    <>
      <label htmlFor="file-upload" style={styles.uploadButton}>
        <span style={styles.plusIcon}>+</span>
        <span style={styles.uploadText}>Upload</span>
      </label>
      <input
        id="file-upload"
        type="file"
        multiple
        accept={ALLOWED_EXTENSIONS.join(',')}
        onChange={handleFileUpload}
        style={styles.fileInput}
      />

      {showProgress && (
        <UploadProgress 
          uploads={uploads} 
          onClose={handleCloseProgress}
        />
      )}
    </>
  );
}

const styles = {
  uploadButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '0 24px',
    height: '36px',
    backgroundColor: 'transparent',
    color: '#8ab4f8',
    borderRadius: '18px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500' as const,
    transition: 'background-color 0.2s',
    border: '1px solid #5f6368',
    userSelect: 'none' as const,
  },
  plusIcon: {
    fontSize: '20px',
    fontWeight: 'normal' as const,
    lineHeight: '1',
  },
  uploadText: {
    fontSize: '14px',
  },
  fileInput: {
    display: 'none',
  }
};