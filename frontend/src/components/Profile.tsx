import { useState, useEffect, useRef } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { doc, getDoc, updateDoc } from 'firebase/firestore';
import { updateProfile } from 'firebase/auth';
import { ref, uploadBytes, getDownloadURL, deleteObject } from 'firebase/storage';
import { db, storage } from '../config/firebase';

export default function Profile() {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [displayName, setDisplayName] = useState('');
  const [photoURL, setPhotoURL] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewURL, setPreviewURL] = useState('');
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  // Load user data on mount
  useEffect(() => {
    async function loadUserData() {
      if (!currentUser) return;

      try {
        const userDoc = await getDoc(doc(db, 'users', currentUser.uid));
        if (userDoc.exists()) {
          const userData = userDoc.data();
          setDisplayName(userData.displayName || currentUser.displayName || '');
          setPhotoURL(userData.photoURL || currentUser.photoURL || '');
        } else {
          setDisplayName(currentUser.displayName || '');
          setPhotoURL(currentUser.photoURL || '');
        }
      } catch (err) {
        console.error('Error loading user data:', err);
      }
    }

    loadUserData();
  }, [currentUser]);

    const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type - ONLY JPG and PNG
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png'];
    if (!allowedTypes.includes(file.type)) {
        setError('Please select a valid image file (JPG or PNG only)');
        return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
        setError('File size must be less than 5MB');
        return;
    }

    setSelectedFile(file);
    setError('');

    // Create preview URL
    const reader = new FileReader();
    reader.onloadend = () => {
        setPreviewURL(reader.result as string);
    };
    reader.readAsDataURL(file);
    };

  // Upload profile picture
  const uploadProfilePicture = async (): Promise<string | null> => {
    if (!selectedFile || !currentUser) return null;

    try {
      setUploading(true);

      // Create a reference to the file location
      const fileExtension = selectedFile.name.split('.').pop();
      const fileName = `profile_${currentUser.uid}_${Date.now()}.${fileExtension}`;
      const storageRef = ref(storage, `profile-pictures/${fileName}`);

      // Upload the file
      await uploadBytes(storageRef, selectedFile);

      // Get the download URL
      const downloadURL = await getDownloadURL(storageRef);

      // Delete old profile picture if it exists and is from our storage
      if (photoURL && photoURL.includes('firebase')) {
        try {
          const oldPhotoRef = ref(storage, photoURL);
          await deleteObject(oldPhotoRef);
        } catch (err) {
          // Could not delete old photo (might be external URL)
          console.log('Could not delete old profile picture.');
        }
      }

      return downloadURL;
    } catch (err: any) {
      throw err;
    } finally {
      setUploading(false);
    }
  };

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    
    if (!currentUser) return;

    try {
      setError('');
      setSuccess('');
      setLoading(true);

      let newPhotoURL = photoURL;

      // Upload new profile picture if selected
      if (selectedFile) {
        const uploadedURL = await uploadProfilePicture();
        if (uploadedURL) {
          newPhotoURL = uploadedURL;
        }
      }

      // Update Firebase Auth profile
      await updateProfile(currentUser, {
        displayName: displayName || null,
        photoURL: newPhotoURL || null,
      });

      // Update Firestore document
      await updateDoc(doc(db, 'users', currentUser.uid), {
        displayName: displayName || null,
        photoURL: newPhotoURL || null,
        updatedAt: new Date().toISOString(),
      });

      setSuccess('Profile updated successfully!');

      // Clear selected file and preview
      setSelectedFile(null);
      setPreviewURL('');
      setPhotoURL(newPhotoURL);

      // Reload the page to update navbar
      setTimeout(() => {
        window.location.reload();
      }, 1500);

    } catch (err: any) {
      setError('Failed to update profile: ' + err.message);
    }
    setLoading(false);
  }

  const getInitials = () => {
    if (displayName) {
      return displayName
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase();
    }
    return currentUser?.email?.[0].toUpperCase() || 'U';
  };

  // Determine which image to show
  const displayImage = previewURL || photoURL;

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        <div style={styles.card}>
          <h2 style={styles.title}>Profile Settings</h2>
          
          {/* Profile Picture Preview */}
          <div style={styles.profilePreview}>
            {displayImage ? (
              <img 
                src={displayImage} 
                alt="Profile" 
                style={styles.profileImage}
              />
            ) : (
              <div style={styles.avatarCircle}>
                {getInitials()}
              </div>
            )}
          </div>

            <div style={styles.uploadButtonContainer}>
            <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/jpg,image/png"
                onChange={handleFileSelect}
                style={styles.fileInput}
            />
            <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                style={styles.uploadButton}
            >
                📸 {selectedFile ? 'Change Photo' : 'Upload Photo'}
            </button>
            {selectedFile && (
                <span style={styles.fileName}>{selectedFile.name}</span>
            )}
            </div>

          {success && <div style={styles.success}>{success}</div>}
          {error && <div style={styles.error}>{error}</div>}

          <form onSubmit={handleSubmit} style={styles.form}>
            <div style={styles.formGroup}>
              <label style={styles.label}>Email</label>
              <input
                type="email"
                value={currentUser?.email || ''}
                disabled
                style={{...styles.input, backgroundColor: '#f5f5f5', cursor: 'not-allowed'}}
              />
              <span style={styles.helpText}>Email cannot be changed</span>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Display Name</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Enter your name"
                style={styles.input}
              />
            </div>

            <div style={styles.buttonGroup}>
              <button 
                type="button" 
                onClick={() => navigate('/home')} 
                style={styles.cancelButton}
                disabled={loading || uploading}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                style={styles.saveButton}
                disabled={loading || uploading}
              >
                {uploading ? 'Uploading...' : loading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#202124', // dark background
    paddingTop: '40px'
  },
  content: {
    maxWidth: '600px',
    margin: '0 auto',
    padding: '20px'
  },
  card: {
    backgroundColor: '#292a2d',  // card background used in dropdowns
    padding: '40px',
    borderRadius: '12px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
    border: '1px solid #3c4043'
  },
  title: {
    fontSize: '28px',
    fontWeight: 'bold' as const,
    color: '#e8eaed',      // light text
    marginBottom: '30px',
    textAlign: 'center' as const
  },

  profilePreview: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '20px'
  },
  profileImage: {
    width: '120px',
    height: '120px',
    borderRadius: '50%',
    objectFit: 'cover' as const,
    border: '4px solid #3c4043' // dark border
  },
  avatarCircle: {
    width: '120px',
    height: '120px',
    borderRadius: '50%',
    backgroundColor: '#8ab4f8', // your default avatar color
    color: '#202124',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 'bold' as const,
    fontSize: '48px'
  },

  uploadButtonContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: '8px',
    marginBottom: '30px'
  },
  uploadButton: {
    padding: '10px 24px',
    backgroundColor: '#8ab4f8', // light blue
    color: '#202124',
    border: 'none',
    borderRadius: '6px',
    fontSize: '14px',
    cursor: 'pointer',
    fontWeight: '600' as const,
    transition: 'background-color 0.2s'
  },
  fileInput: {
    display: 'none'
  },
  fileName: {
    fontSize: '12px',
    color: '#9aa0a6'
  },

  success: {
    backgroundColor: '#1e442f',
    color: '#8cffc1',
    padding: '12px',
    borderRadius: '4px',
    marginBottom: '20px',
    fontSize: '14px',
    border: '1px solid #2b6549'
  },
  error: {
    backgroundColor: '#3a1e1e',
    color: '#ffb3b3',
    padding: '12px',
    borderRadius: '4px',
    marginBottom: '20px',
    fontSize: '14px',
    border: '1px solid #7a3a3a'
  },

  form: {
    display: 'flex',
    flexDirection: 'column' as const
  },
  formGroup: {
    marginBottom: '24px'
  },
  label: {
    display: 'block',
    marginBottom: '8px',
    color: '#e8eaed',
    fontSize: '14px',
    fontWeight: '600' as const
  },
  input: {
    width: '100%',
    padding: '12px',
    border: '1px solid #5f6368',
    borderRadius: '6px',
    fontSize: '16px',
    backgroundColor: '#303134',      // dark input bg
    color: '#e8eaed',                 // light text
    boxSizing: 'border-box' as const,
    transition: 'border-color 0.2s'
  },
  helpText: {
    display: 'block',
    marginTop: '6px',
    fontSize: '12px',
    color: '#9aa0a6'
  },

  buttonGroup: {
    display: 'flex',
    gap: '12px',
    marginTop: '10px'
  },
  cancelButton: {
    flex: 1,
    padding: '12px',
    backgroundColor: '#3c4043',
    color: '#e8eaed',
    border: '1px solid #5f6368',
    borderRadius: '6px',
    fontSize: '16px',
    cursor: 'pointer',
    fontWeight: '600' as const,
    transition: 'all 0.2s'
  },
  saveButton: {
    flex: 1,
    padding: '12px',
    backgroundColor: '#8ab4f8',
    color: '#202124',
    border: 'none',
    borderRadius: '6px',
    fontSize: '16px',
    cursor: 'pointer',
    fontWeight: '600' as const,
    transition: 'background-color 0.2s'
  }
};
