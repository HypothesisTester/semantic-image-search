import { useEffect } from 'react';
import type { Timestamp } from 'firebase/firestore';

interface ImageData {
  id: string;
  url: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  uploadedAt: Timestamp | null;
}

interface ImageViewerProps {
  image: ImageData;
  onClose: () => void;
}

export default function ImageViewer({ image, onClose }: ImageViewerProps) {
  // Prevent scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const formatDate = (timestamp: Timestamp | null) => {
    if (!timestamp) return 'Unknown';
    const date = timestamp.toDate();
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  };

  return (
    <div className="lightbox" onClick={onClose} role="dialog" aria-modal="true">
      <button className="lightbox__close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <div className="lightbox__content" onClick={e => e.stopPropagation()}>
        <img className="lightbox__image" src={image.url} alt={image.fileName} />
        <p className="lightbox__caption">{image.fileName}</p>
        <p className="lightbox__note">
          {[image.fileType || null, formatFileSize(image.fileSize), `Uploaded ${formatDate(image.uploadedAt)}`]
            .filter(Boolean)
            .join(' · ')}
        </p>
      </div>
    </div>
  );
}
