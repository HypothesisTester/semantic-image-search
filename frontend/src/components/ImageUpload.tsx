import { useState } from 'react';
import type { ChangeEvent } from 'react';
import { ref, uploadBytes, getDownloadURL } from 'firebase/storage';
import { collection, addDoc, serverTimestamp } from 'firebase/firestore';
import { storage, db } from '../config/firebase';
import { useAuth } from '../contexts/AuthContext';
import UploadProgress from './UploadProgress';
import type { UploadItem } from './UploadProgress';

interface ImageUploadProps {
  onUploadStart?: () => void;
  onUploadComplete?: (urls: string[]) => void;
  onUploadError?: (error: string) => void;
}

export default function ImageUpload({ 
  onUploadStart, 
  onUploadComplete, 
  onUploadError 
}: ImageUploadProps) {
  
  const { currentUser } = useAuth();
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [showProgress, setShowProgress] = useState(false);

  // Allowed image formats
  const ALLOWED_FORMATS = [
    'image/jpeg',
    'image/jpg', 
    'image/png',
    'image/heic',
    'image/heif',
    'image/webp',
    'image/gif',
    'image/bmp',
    'image/tiff',
    'image/x-adobe-dng',
    'image/dng'
  ];

  const ALLOWED_EXTENSIONS = [
    '.jpg',
    '.jpeg',
    '.png',
    '.heic',
    '.heif',
    '.webp',
    '.gif',
    '.bmp',
    '.tiff',
    '.tif',
    '.dng'
  ];

  const uploadImageToStorage = async (file: File, uploadId: string): Promise<{ url: string; path: string }> => {
    if (!currentUser) throw new Error('User not authenticated');

    // Update status to uploading
    setUploads(prev => prev.map(u => 
      u.id === uploadId ? { ...u, status: 'uploading' as const } : u
    ));

    const timestamp = Date.now();
    const fileExtension = file.name.split('.').pop();
    // Format: userId-timestamp.extension
    const fileName = `${currentUser.uid}-${timestamp}.${fileExtension}`;
    const storagePath = `user-images/${currentUser.uid}/${fileName}`;
    
    const storageRef = ref(storage, storagePath);

    await uploadBytes(storageRef, file);
    const downloadURL = await getDownloadURL(storageRef);

    return { url: downloadURL, path: storagePath };
  };

  const saveImageToFirestore = async (
    url: string, 
    fileName: string, 
    fileSize: number, 
    fileType: string, 
    storagePath: string
  ) => {
    if (!currentUser) throw new Error('User not authenticated');

    const imageDoc = await addDoc(collection(db, 'users', currentUser.uid, 'images'), {
      url: url,
      storagePath: storagePath,
      fileName: fileName,
      fileSize: fileSize,
      fileType: fileType,
      uploadedAt: serverTimestamp(),
    });

    return imageDoc.id;
  };

  // Function to send data to backend
  const sendToBackend = async (userId: string, photoURLs: string[]) => {
    
    try {

      const response = await fetch('https://semantic-search-backend-628129189292.us-central1.run.app/upload', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userId: userId,
          photoURLs: photoURLs,
        }),
      });

      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      return data;
    } catch (error) {
      throw error;
    }
  };

  const processUpload = async (uploadItem: UploadItem): Promise<string | null> => {
    try {
      // Upload to storage
      const { url: downloadURL, path: storagePath } = await uploadImageToStorage(uploadItem.file, uploadItem.id);

      // Save to Firestore
      await saveImageToFirestore(
        downloadURL, 
        uploadItem.file.name, 
        uploadItem.file.size, 
        uploadItem.file.type,
        storagePath
      );

      // Update status to completed
      setUploads(prev => prev.map(u => 
        u.id === uploadItem.id 
          ? { ...u, status: 'completed' as const, url: downloadURL, progress: 100 } 
          : u
      ));

      
      return downloadURL; // Return the URL

    } catch (error: any) {
      
      // Update status to error
      setUploads(prev => prev.map(u => 
        u.id === uploadItem.id 
          ? { ...u, status: 'error' as const, error: error.message } 
          : u
      ));
      
      return null; // Return null on error
    }
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    
    if (!files || files.length === 0) {
      return;
    }

    if (!currentUser) {
      const errorMsg = 'You must be logged in to upload images';
      if (onUploadError) {
        onUploadError(errorMsg);
      }
      return;
    }

    // Validate files
    const validFiles: File[] = [];
    const invalidFiles: string[] = [];

    Array.from(files).forEach(file => {
      const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
      const isValidType = ALLOWED_FORMATS.includes(file.type);
      const isValidExtension = ALLOWED_EXTENSIONS.includes(fileExtension);

      if (isValidType || isValidExtension) {
        validFiles.push(file);
      } else {
        invalidFiles.push(file.name);
      }
    });

    if (invalidFiles.length > 0) {
      const errorMsg = `Invalid file format: ${invalidFiles.join(', ')}. Please upload images only.`;
      if (onUploadError) {
        onUploadError(errorMsg);
      }
    }

    if (validFiles.length === 0) {
      return;
    }

    // Create upload items with previews
    const newUploads: UploadItem[] = validFiles.map(file => ({
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      file: file,
      preview: URL.createObjectURL(file),
      status: 'pending' as const,
      progress: 0
    }));

    setUploads(newUploads);
    setShowProgress(true);

    if (onUploadStart) {
      onUploadStart();
    }

    // Process all uploads and collect URLs
    const uploadResults = await Promise.all(newUploads.map(upload => processUpload(upload)));

    // Filter out null values (failed uploads)
    const photoURLs = uploadResults.filter((url): url is string => url !== null);


    if (photoURLs.length > 0) {
      
      if (onUploadComplete) {
        onUploadComplete(photoURLs);
      }

      // Send to backend
      if (currentUser) {
        try {
          await sendToBackend(currentUser.uid, photoURLs);
        } catch (error) {
        }
      } else {
        // User not authenticated, should not happen here
      }
    }

    // Reset input
    e.target.value = '';
  };

  const handleCloseProgress = () => {
    setShowProgress(false);
    setUploads([]);
    
    // Clean up object URLs
    uploads.forEach(upload => URL.revokeObjectURL(upload.preview));
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