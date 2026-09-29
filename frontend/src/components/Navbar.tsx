import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import ImageUpload from './ImageUpload';
import Search from "./Search";

export default function Navbar() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const [showDropdown, setShowDropdown] = useState(false);

  async function handleLogout() {
    try {
      await logout();
      navigate('/login');
    } catch {
      alert('Failed to log out');
    }
  }


  const getInitials = () => {
    if (currentUser?.displayName) {
      return currentUser.displayName
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase();
    }
    return currentUser?.email?.[0].toUpperCase() || 'U';
  };

  const handleUploadStart = () => {
    // Something I guess
  };

  const handleUploadComplete = () => {
    // Something I guess
  };

  const handleUploadError = (error: string) => {
    // Something I guess
    alert(error);
  };

  return (
    <nav style={styles.navbar}>
      <div style={styles.container}>
        {/* Logo */}
        <div style={styles.leftSection}>
          <div style={styles.logo} onClick={() => navigate('/home')}>
            <img 
              src="/imageintel.png" 
              alt="ImageIntel Logo"
              style={{
                width: "40px",
                height: "40px",
                objectFit: "contain"
              }}
            />

            <span style={styles.logoText}>ImageIntel</span>
          </div>
        </div>

        {/* Search Bar */}
        <div style={styles.centerSection}>
          <Search 
            styles={styles} 
            userId={currentUser?.uid}
          />
        </div>

        {/* Right Section */}
        <div style={styles.rightSection}>
          <ImageUpload 
            onUploadStart={handleUploadStart}
            onUploadComplete={handleUploadComplete}
            onUploadError={handleUploadError}
          />

          {/* Profile Section */}
          <div style={styles.profileSection}>
            <div 
              style={styles.profileButton}
              onClick={() => setShowDropdown(!showDropdown)}
            >
              {currentUser?.photoURL ? (
                <img 
                  src={currentUser.photoURL} 
                  alt="Profile" 
                  style={styles.profileImage}
                />
              ) : (
                <div style={styles.avatarCircle}>
                  {getInitials()}
                </div>
              )}
            </div>

            {showDropdown && (
              <>
                <div 
                  style={styles.overlay} 
                  onClick={() => setShowDropdown(false)}
                />
                <div style={styles.dropdown}>
                  <div style={styles.dropdownHeader}>
                    <div style={styles.userInfo}>
                      <div style={styles.userName}>
                        {currentUser?.displayName || 'User'}
                      </div>
                      <div style={styles.userEmail}>{currentUser?.email}</div>
                    </div>
                  </div>
                  <div style={styles.divider} />
                  <button 
                    style={styles.dropdownItem} 
                    onClick={() => {
                      setShowDropdown(false);
                      navigate('/profile');
                    }}
                  >
                    <span style={styles.dropdownIcon}>👤</span>
                    Profile
                  </button>
                  <div style={styles.divider} />
                  <button 
                    style={{...styles.dropdownItem, color: '#dc3545'}} 
                    onClick={handleLogout}
                  >
                    <span style={styles.dropdownIcon}>🚪</span>
                    Log Out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

const styles = {
  navbar: {
    backgroundColor: '#202124',
    borderBottom: '1px solid #3c4043',
    padding: '0 16px',
    position: 'sticky' as const,
    top: 0,
    zIndex: 1000,
  },
  container: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    height: '64px',
    maxWidth: '100%',
  },
  leftSection: {
    display: 'flex',
    alignItems: 'center',
    minWidth: '200px',
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    cursor: 'pointer',
    gap: '12px',
    padding: '8px 12px',
    borderRadius: '24px',
    transition: 'background-color 0.2s',
  },
  logoIcon: {
    width: '40px',
    height: '40px',
  },
  logoText: {
    fontSize: '22px',
    color: '#e8eaed',
    fontWeight: '400' as const,
  },
  centerSection: {
    flex: 1,
    maxWidth: '720px',
    margin: '0 auto',
  },
  searchForm: {
    width: '100%',
  },
  searchContainer: {
    display: 'flex',
    alignItems: 'center',
    backgroundColor: '#303134',
    borderRadius: '8px',
    padding: '0 16px',
    height: '48px',
    transition: 'background-color 0.2s',
  },
  searchIcon: {
    width: '24px',
    height: '24px',
    marginRight: '12px',
  },
  searchInput: {
    flex: 1,
    border: 'none',
    backgroundColor: 'transparent',
    color: '#e8eaed',
    fontSize: '16px',
    outline: 'none',
  },
  rightSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    minWidth: '200px',
    justifyContent: 'flex-end',
  },
  profileSection: {
    position: 'relative' as const,
  },
  profileButton: {
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
  },
  profileImage: {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    objectFit: 'cover' as const,
  },
  avatarCircle: {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    backgroundColor: '#8ab4f8',
    color: '#202124',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: '500' as const,
    fontSize: '14px',
  },
  overlay: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 999,
  },
  dropdown: {
    position: 'absolute' as const,
    top: '45px',
    right: 0,
    backgroundColor: '#292a2d',
    borderRadius: '8px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
    minWidth: '280px',
    zIndex: 1001,
    overflow: 'hidden',
    border: '1px solid #3c4043',
  },
  dropdownHeader: {
    padding: '16px',
  },
  userInfo: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px',
  },
  userName: {
    fontWeight: '500' as const,
    fontSize: '14px',
    color: '#e8eaed',
  },
  userEmail: {
    fontSize: '12px',
    color: '#9aa0a6',
  },
  divider: {
    height: '1px',
    backgroundColor: '#3c4043',
  },
  dropdownItem: {
    width: '100%',
    padding: '12px 16px',
    border: 'none',
    backgroundColor: 'transparent',
    textAlign: 'left' as const,
    cursor: 'pointer',
    fontSize: '14px',
    color: '#e8eaed',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    transition: 'background-color 0.2s',
  },
  dropdownIcon: {
    fontSize: '16px',
  },
};