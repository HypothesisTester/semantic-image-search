import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom';
import type { JSX } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './components/Login';
import Signup from './components/Signup';
import Home from './components/Home';
import Profile from './components/Profile';
import Result from './components/result';
import Navbar from './components/Navbar';

function PrivateRoute({ children }: { children: JSX.Element }): JSX.Element {
  const { currentUser } = useAuth();
  return currentUser ? children : <Navigate to="/login" />;
}

// This component can see the current URL
function AppContent() {
  const location = useLocation();

  const hideNavbar =
    location.pathname === '/login' || location.pathname === '/signup';

  return (
    <>
      {/* Only show navbar when not on login/signup */}
      {!hideNavbar && <Navbar />}

      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/result" element={<Result />} />
        <Route
          path="/home"
          element={
            <PrivateRoute>
              <Home />
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
        <Route path="/" element={<Navigate to="/home" />} />
      </Routes>
    </>
  );
}

function App(): JSX.Element {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
}

export default App;
