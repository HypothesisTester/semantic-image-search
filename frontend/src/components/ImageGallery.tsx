import { useState, useEffect } from 'react';
import { collection, query, orderBy, onSnapshot } from 'firebase/firestore';
import { db } from '../config/firebase';
import { useAuth } from '../contexts/AuthContext';
import ImageViewer from './ImageViewer';

interface ImageData {
  id: string;
  url: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  uploadedAt: any;
}

export default function ImageGallery() {
  const { currentUser } = useAuth();
  const [images, setImages] = useState<ImageData[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState<ImageData | null>(null);

  useEffect(() => {
    if (!currentUser) return;

    // Real-time listener for user's images
    const imagesRef = collection(db, 'users', currentUser.uid, 'images');
    const q = query(imagesRef, orderBy('uploadedAt', 'desc'));

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const imageData: ImageData[] = [];
      snapshot.forEach((doc) => {
        imageData.push({
          id: doc.id,
          ...doc.data()
        } as ImageData);
      });
      setImages(imageData);
      setLoading(false);
    });

    return () => unsubscribe();
  }, [currentUser]);

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingText}>Loading your photos...</div>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div style={styles.emptyContainer}>
        <div style={styles.emptyIcon}></div>
        <div style={styles.emptyTitle}>No photos yet</div>
        <div style={styles.emptyText}>
          Click the + Upload button to add your first photos
        </div>
      </div>
    );
  }

  return (
    <>
      <div style={styles.gallery}>
        {images.map((image) => (
          <div 
            key={image.id} 
            style={styles.imageCard}
            onClick={() => setSelectedImage(image)}
          >
            <img 
              src={image.url} 
              alt={image.fileName}
              style={styles.image}
            />
          </div>
        ))}
      </div>

      {selectedImage && (
        <ImageViewer 
          image={selectedImage} 
          onClose={() => setSelectedImage(null)}
        />
      )}
    </>
  );
}

const styles = {
  gallery: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
    gap: '8px',
    padding: '16px',
  },
  imageCard: {
    position: 'relative' as const,
    paddingBottom: '100%',
    backgroundColor: '#282828',
    borderRadius: '8px',
    overflow: 'hidden',
    cursor: 'pointer',
    transition: 'transform 0.2s ease, box-shadow 0.2s ease',
  },
  image: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
  },
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '400px',
  },
  loadingText: {
    color: '#e8eaed',
    fontSize: '16px',
  },
  emptyContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '400px',
    padding: '40px',
  },
  emptyIcon: {
    fontSize: '64px',
    marginBottom: '16px',
  },
  emptyTitle: {
    fontSize: '22px',
    color: '#e8eaed',
    marginBottom: '8px',
    fontWeight: '400' as const,
  },
  emptyText: {
    fontSize: '14px',
    color: '#9aa0a6',
  },
};