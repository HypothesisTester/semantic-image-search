import { useEffect } from 'react';

export interface UploadItem {
  id: string;
  file: File;
  preview: string;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  progress: number;
  url?: string;
  error?: string;
}

interface UploadProgressProps {
  uploads: UploadItem[];
  onClose: () => void;
}

export default function UploadProgress({ uploads, onClose }: UploadProgressProps) {
  const totalUploads = uploads.length;
  const completedUploads = uploads.filter(u => u.status === 'completed').length;
  const failedUploads = uploads.filter(u => u.status === 'error').length;
  const allDone = completedUploads + failedUploads === totalUploads;

  // Prevent scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h2 style={styles.title}>
            Uploading Images
          </h2>
          <div style={styles.stats}>
            {completedUploads} of {totalUploads} completed
            {failedUploads > 0 && (
              <span style={styles.errorStat}> · {failedUploads} failed</span>
            )}
          </div>
        </div>

        <div style={styles.progressBar}>
          <div 
            style={{
              ...styles.progressFill,
              width: `${(completedUploads / totalUploads) * 100}%`
            }}
          />
        </div>

        <div style={styles.uploadList}>
          {uploads.map((upload) => (
            <div key={upload.id} style={styles.uploadItem}>
              <div style={styles.imagePreview}>
                <img 
                  src={upload.preview} 
                  alt={upload.file.name}
                  style={{
                    ...styles.previewImage,
                    opacity: upload.status === 'completed' ? 1 : 0.4
                  }}
                />
              </div>

              <div style={styles.uploadInfo}>
                <div style={styles.fileName}>{upload.file.name}</div>
                <div style={styles.fileSize}>
                  {(upload.file.size / 1024 / 1024).toFixed(2)} MB
                </div>
                
                {upload.status === 'pending' && (
                  <div style={styles.statusText}>Waiting...</div>
                )}
                {upload.status === 'uploading' && (
                  <div style={styles.statusText}>Uploading...</div>
                )}
                {upload.status === 'completed' && (
                  <div style={{...styles.statusText, color: '#28a745'}}>
                    Completed ✓
                  </div>
                )}
                {upload.status === 'error' && (
                  <div style={{...styles.statusText, color: '#dc3545'}}>
                    Failed: {upload.error}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div style={styles.footer}>
          <button
            onClick={onClose}
            disabled={!allDone}
            style={{
              ...styles.doneButton,
              opacity: allDone ? 1 : 0.5,
              cursor: allDone ? 'pointer' : 'not-allowed'
            }}
          >
            {allDone ? 'Done' : 'Uploading...'}
          </button>
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
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10000,
    padding: '20px'
  },
  modal: {
    backgroundColor: 'white',
    borderRadius: '12px',
    maxWidth: '600px',
    width: '100%',
    maxHeight: '80vh',
    display: 'flex',
    flexDirection: 'column' as const,
    boxShadow: '0 20px 60px rgba(0,0,0,0.3)'
  },
  header: {
    padding: '24px',
    borderBottom: '1px solid #e0e0e0'
  },
  title: {
    margin: 0,
    fontSize: '24px',
    fontWeight: 'bold' as const,
    color: '#333'
  },
  stats: {
    marginTop: '8px',
    fontSize: '14px',
    color: '#666'
  },
  errorStat: {
    color: '#dc3545'
  },
  progressBar: {
    height: '6px',
    backgroundColor: '#e0e0e0',
    position: 'relative' as const
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#1a73e8',
    transition: 'width 0.3s ease'
  },
  uploadList: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '16px'
  },
  uploadItem: {
    display: 'flex',
    gap: '16px',
    padding: '12px',
    marginBottom: '8px',
    backgroundColor: '#f9f9f9',
    borderRadius: '8px',
    alignItems: 'center'
  },
  imagePreview: {
    position: 'relative' as const,
    width: '80px',
    height: '80px',
    flexShrink: 0,
    borderRadius: '6px',
    overflow: 'hidden',
    backgroundColor: '#e0e0e0'
  },
  previewImage: {
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
    transition: 'opacity 0.3s ease'
  },
  uploadInfo: {
    flex: 1,
    minWidth: 0
  },
  fileName: {
    fontSize: '14px',
    fontWeight: '600' as const,
    color: '#333',
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  },
  fileSize: {
    fontSize: '12px',
    color: '#666',
    marginTop: '4px'
  },
  statusText: {
    fontSize: '12px',
    marginTop: '4px',
    fontWeight: '500' as const
  },
  footer: {
    padding: '16px 24px',
    borderTop: '1px solid #e0e0e0'
  },
  doneButton: {
    width: '100%',
    padding: '12px',
    backgroundColor: '#1a73e8',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    fontSize: '16px',
    fontWeight: 'bold' as const,
    transition: 'opacity 0.2s'
  }
};