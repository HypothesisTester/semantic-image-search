import { useEffect } from 'react';

interface ImageData {
  id: string;
  url: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  uploadedAt: any;
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
      document.body.style.overflow = 'unset';
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

  const formatDate = (timestamp: any) => {
    if (!timestamp) return 'Unknown';
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / 1024 / 1024).toFixed(2) + ' MB';
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.container} onClick={(e) => e.stopPropagation()}>
        {/* Close Button */}
        <button style={styles.closeButton} onClick={onClose}>
          <svg style={styles.closeIcon} viewBox="0 0 24 24">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="#e8eaed"/>
          </svg>
        </button>

        {/* Image Section */}
        <div style={styles.imageSection}>
          <img 
            src={image.url} 
            alt={image.fileName}
            style={styles.image}
          />
        </div>

        {/* Metadata Panel */}
        <div style={styles.metadataPanel}>
          <h2 style={styles.panelTitle}>Details</h2>

          <div style={styles.metadataGroup}>
            <div style={styles.metadataLabel}>File name</div>
            <div style={styles.metadataValue}>{image.fileName}</div>
          </div>

          <div style={styles.divider} />

          <div style={styles.metadataGroup}>
            <div style={styles.metadataLabel}>Type</div>
            <div style={styles.metadataValue}>
              {image.fileType || 'Unknown'}
            </div>
          </div>

          <div style={styles.divider} />

          <div style={styles.metadataGroup}>
            <div style={styles.metadataLabel}>Size</div>
            <div style={styles.metadataValue}>
              {formatFileSize(image.fileSize)}
            </div>
          </div>

          <div style={styles.divider} />

          <div style={styles.metadataGroup}>
            <div style={styles.metadataLabel}>Uploaded</div>
            <div style={styles.metadataValue}>
              {formatDate(image.uploadedAt)}
            </div>
          </div>

          <div style={styles.divider} />
        </div>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.95)',
    zIndex: 10000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px 0',
  },
  container: {
    display: 'flex',
    width: '100%',
    height: 'calc(100vh - 80px)',
    maxWidth: '1400px',
    margin: '0 auto',
    position: 'relative' as const,
    backgroundColor: '#000',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  closeButton: {
    position: 'absolute' as const,
    top: '16px',
    left: '16px',
    width: '48px',
    height: '48px',
    borderRadius: '50%',
    border: 'none',
    backgroundColor: '#3c4043',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10001,
    transition: 'background-color 0.2s',
  },
  closeIcon: {
    width: '24px',
    height: '24px',
  },
  imageSection: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 40px',
  },
  image: {
    maxWidth: '100%',
    maxHeight: '100%',
    objectFit: 'contain' as const,
    borderRadius: '4px',
  },
  metadataPanel: {
    width: '360px',
    backgroundColor: '#292a2d',
    padding: '24px',
    overflowY: 'auto' as const,
    borderLeft: '1px solid #3c4043',
  },
  panelTitle: {
    fontSize: '22px',
    fontWeight: '400' as const,
    color: '#e8eaed',
    marginBottom: '24px',
    marginTop: 0,
  },
  metadataGroup: {
    marginBottom: '16px',
  },
  metadataLabel: {
    fontSize: '12px',
    color: '#9aa0a6',
    marginBottom: '4px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  metadataValue: {
    fontSize: '14px',
    color: '#e8eaed',
    wordBreak: 'break-word' as const,
  },
  divider: {
    height: '1px',
    backgroundColor: '#3c4043',
    margin: '16px 0',
  },
  actionButtons: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '12px',
    marginTop: '24px',
  },
  actionButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    backgroundColor: '#3c4043',
    color: '#8ab4f8',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    textDecoration: 'none',
    transition: 'background-color 0.2s',
  },
  buttonIcon: {
    width: '20px',
    height: '20px',
  },
};