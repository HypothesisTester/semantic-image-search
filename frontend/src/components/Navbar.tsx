import { useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import ImageUpload from './ImageUpload';
import Search from './Search';
import { DEMO_MODE, REPO_URL } from '../config/api';

export default function Navbar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  // The demo's landing page has its own large search field.
  const showSearch = !(DEMO_MODE && pathname === '/');

  return (
    <header className="header">
      <div className="header__inner">
        <button className="brand" onClick={() => navigate(DEMO_MODE ? '/' : '/home')} aria-label="ImageIntel home">
          <img src="/imageintel.png" alt="" />
          <span>ImageIntel</span>
        </button>
        {DEMO_MODE && <span className="badge">Demo</span>}

        {showSearch ? (
          <div className="header__search">
            {/* Keyed on the query so the field follows back/forward navigation. */}
            <Search key={params.get('q') ?? ''} />
          </div>
        ) : (
          <div className="header__spacer" />
        )}

        <div className="header__actions">
          {DEMO_MODE ? (
            <a href={REPO_URL} target="_blank" rel="noreferrer" className="link-quiet">
              GitHub
            </a>
          ) : (
            <AccountControls />
          )}
        </div>
      </div>
    </header>
  );
}

// Upload button and profile menu. A separate component because it needs the
// signed-in user, and the demo build has no sign-in at all.
function AccountControls() {
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
