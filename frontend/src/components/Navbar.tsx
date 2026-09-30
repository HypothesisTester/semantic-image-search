import { Suspense, lazy } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import Search from './Search';
import Logo from './Logo';
import GitHubLink from './GitHubLink';
import { DEMO_MODE } from '../config/api';

// Needs the signed-in user, so it lives in the full app's chunk, not the demo's.
const AccountControls = lazy(() => import('./AccountControls'));

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
          <Logo />
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
            <GitHubLink />
          ) : (
            <Suspense fallback={null}>
              <AccountControls />
            </Suspense>
          )}
        </div>
      </div>
    </header>
  );
}
