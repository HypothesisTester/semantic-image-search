import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { doc, getDoc, setDoc } from 'firebase/firestore';
import { updateProfile } from 'firebase/auth';
import { db } from '../config/firebase';

// Profile pictures used to be uploaded to Firebase Storage, which new
// projects can only use on the paid plan. The picture now comes from the
// sign-in provider (e.g. the Google account photo), and only the display
// name is editable.
export default function Profile() {
  const { currentUser } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadUserData() {
      if (!currentUser) return;
      try {
        const userDoc = await getDoc(doc(db, 'users', currentUser.uid));
        setDisplayName(
          (userDoc.exists() && userDoc.data().displayName) || currentUser.displayName || '',
        );
      } catch (err) {
        console.error('Error loading user data:', err);
        setDisplayName(currentUser.displayName || '');
      }
    }
    loadUserData();
  }, [currentUser]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!currentUser) return;

    try {
      setError('');
      setSuccess('');
      setLoading(true);
      await updateProfile(currentUser, { displayName: displayName || null });
      // merge: works whether or not the profile document exists yet.
      await setDoc(
        doc(db, 'users', currentUser.uid),
        { displayName: displayName || null, updatedAt: new Date().toISOString() },
        { merge: true },
      );
      setSuccess('Profile updated successfully!');
      setTimeout(() => window.location.reload(), 1500); // refresh the navbar's name
    } catch (err) {
      setError('Failed to update profile: ' + (err instanceof Error ? err.message : err));
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

  const photoURL = currentUser?.photoURL;

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        <div style={styles.card}>
          <h2 style={styles.title}>Profile Settings</h2>

          <div style={styles.profilePreview}>
            {photoURL ? (
              <img src={photoURL} alt="Profile" style={styles.profileImage} />
            ) : (
              <div style={styles.avatarCircle}>{getInitials()}</div>
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
                style={{...styles.input, backgroundColor: 'var(--bg)', cursor: 'not-allowed'}}
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
                disabled={loading}
              >
                Cancel
              </button>
              <button type="submit" style={styles.saveButton} disabled={loading}>
                {loading ? 'Saving...' : 'Save Changes'}
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
    backgroundColor: 'var(--bg)', // dark background
    paddingTop: '40px'
  },
  content: {
    maxWidth: '600px',
    margin: '0 auto',
    padding: '20px'
  },
  card: {
    backgroundColor: 'var(--surface)',  // card background used in dropdowns
    padding: '40px',
    borderRadius: '12px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
    border: '1px solid var(--border)'
  },
  title: {
    fontSize: '28px',
    fontWeight: 'bold' as const,
    color: 'var(--text)',      // light text
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
    border: '4px solid var(--border)' // dark border
  },
  avatarCircle: {
    width: '120px',
    height: '120px',
    borderRadius: '50%',
    backgroundColor: 'var(--accent)', // your default avatar color
    color: '#fff',
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
    backgroundColor: 'var(--accent)', // light blue
    color: '#fff',
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
    color: 'var(--text-2)'
  },

  success: {
    backgroundColor: 'rgba(52, 199, 89, 0.14)',
    color: 'var(--success)',
    padding: '12px',
    borderRadius: '4px',
    marginBottom: '20px',
    fontSize: '14px',
    border: '1px solid transparent'
  },
  error: {
    backgroundColor: 'rgba(255, 59, 48, 0.12)',
    color: 'var(--danger)',
    padding: '12px',
    borderRadius: '4px',
    marginBottom: '20px',
    fontSize: '14px',
    border: '1px solid transparent'
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
    color: 'var(--text)',
    fontSize: '14px',
    fontWeight: '600' as const
  },
  input: {
    width: '100%',
    padding: '12px',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    fontSize: '16px',
    backgroundColor: 'var(--surface-2)',      // dark input bg
    color: 'var(--text)',                 // light text
    boxSizing: 'border-box' as const,
    transition: 'border-color 0.2s'
  },
  helpText: {
    display: 'block',
    marginTop: '6px',
    fontSize: '12px',
    color: 'var(--text-2)'
  },

  buttonGroup: {
    display: 'flex',
    gap: '12px',
    marginTop: '10px'
  },
  cancelButton: {
    flex: 1,
    padding: '12px',
    backgroundColor: 'var(--border)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    fontSize: '16px',
    cursor: 'pointer',
    fontWeight: '600' as const,
    transition: 'all 0.2s'
  },
  saveButton: {
    flex: 1,
    padding: '12px',
    backgroundColor: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '16px',
    cursor: 'pointer',
    fontWeight: '600' as const,
    transition: 'background-color 0.2s'
  }
};
