import { useState, useEffect } from 'react';
import { collection, query, orderBy, onSnapshot } from 'firebase/firestore';
import type { Timestamp } from 'firebase/firestore';
import { db } from '../config/firebase';
import { useAuth } from '../contexts/AuthContext';
import ImageViewer from './ImageViewer';
import PhotoTile from './PhotoTile';

interface ImageData {
  id: string;
  url: string;
  thumbnailUrl?: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  uploadedAt: Timestamp | null;
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
      <>
        <div className="section-head">
          <h1 className="section-title">Your photos</h1>
        </div>
        <div className="grid">
          {Array.from({ length: 12 }, (_, i) => <div key={i} className="skeleton" />)}
        </div>
      </>
    );
  }

  if (images.length === 0) {
    return (
      <div className="empty">
        <h1 className="empty__title">No photos yet</h1>
        <p className="empty__text">Use Upload to add your first photos. Then search them by describing what's in them.</p>
      </div>
    );
  }

  return (
    <>
      <div className="section-head">
        <h1 className="section-title">Your photos</h1>
        <span className="section-meta">{images.length.toLocaleString()} {images.length === 1 ? 'photo' : 'photos'}</span>
      </div>
      <div className="grid">
        {images.map(image => (
          <PhotoTile
            key={image.id}
            src={image.thumbnailUrl ?? image.url}
            alt={image.fileName}
            onOpen={() => setSelectedImage(image)}
          />
        ))}
      </div>

      {selectedImage && <ImageViewer image={selectedImage} onClose={() => setSelectedImage(null)} />}
    </>
  );
}
