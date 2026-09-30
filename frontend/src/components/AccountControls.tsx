import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import ImageUpload from './ImageUpload';

// Upload button and profile menu. A separate component because it needs the
// signed-in user, and the demo build has no sign-in at all.
export default function AccountControls() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  async function handleLogout() {
    try {
      await logout();
      navigate('/login');
    } catch {
      alert('Failed to log out');
    }
  }

  const initials = currentUser?.displayName
    ? currentUser.displayName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : currentUser?.email?.[0].toUpperCase() || 'U';

  return (
    <>
      <ImageUpload onUploadError={error => alert(error)} />

      <div className="menu-anchor">
        <button className="avatar" onClick={() => setOpen(!open)} aria-label="Account menu" aria-expanded={open}>
          {currentUser?.photoURL ? <img className="avatar" src={currentUser.photoURL} alt="" /> : initials}
        </button>

        {open && (
          <>
            <div className="menu-backdrop" onClick={() => setOpen(false)} />
            <div className="menu" role="menu">
              <div className="menu__header">
                <div className="menu__name">{currentUser?.displayName || 'Your account'}</div>
                <div className="menu__email">{currentUser?.email}</div>
              </div>
              <div className="menu__divider" />
              <button
                className="menu__item"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  navigate('/profile');
                }}
              >
                Profile
              </button>
              <button className="menu__item menu__item--danger" role="menuitem" onClick={handleLogout}>
                Log out
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
