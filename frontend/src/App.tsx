import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom';
import type { JSX } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { DEMO_MODE } from './config/api';
import Login from './components/Login';
import Signup from './components/Signup';
import Home from './components/Home';
import Profile from './components/Profile';
import Result from './components/result';
import Navbar from './components/Navbar';
import DemoHome from './components/DemoHome';

function PrivateRoute({ children }: { children: JSX.Element }): JSX.Element {
  const { currentUser } = useAuth();
  return currentUser ? children : <Navigate to="/login" />;
}

// The public demo: no accounts, just search over the COCO images.
function DemoContent() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<DemoHome />} />
        <Route path="/result" element={<Result />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </>
  );
}

function AppContent() {
  const location = useLocation();
  const hideNavbar = location.pathname === '/login' || location.pathname === '/signup';

  return (
    <>
      {!hideNavbar && <Navbar />}

      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route
          path="/home"
          element={
            <PrivateRoute>
              <Home />
            </PrivateRoute>
          }
        />
        <Route
          path="/result"
          element={
            <PrivateRoute>
              <Result />
            </PrivateRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <PrivateRoute>
              <Profile />
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/home" />} />
      </Routes>
    </>
  );
}

function App(): JSX.Element {
  return (
    <Router>
      {DEMO_MODE ? (
        <DemoContent />
      ) : (
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      )}
    </Router>
  );
}

export default App;
