import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy, useEffect } from 'react';
import type { JSX } from 'react';
import { DEMO_MODE } from './config/api';
import Result from './components/result';
import Navbar from './components/Navbar';
import DemoHome from './components/DemoHome';
import { schedulePreload } from './demo/preload';

// The signed-in app, in its own chunk: the demo build never loads it.
const FullApp = lazy(() => import('./FullApp'));

// The public demo: no accounts, just search over the COCO images.
function DemoContent() {
  // Fetch the search model in the background where that is cheap (see demo/preload.ts),
  // so a typed search is instant. The first photos load first.
  useEffect(() => schedulePreload(), []);

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

function App(): JSX.Element {
  return (
    <Router>
      {DEMO_MODE ? (
        <DemoContent />
      ) : (
        <Suspense fallback={null}>
          <FullApp />
        </Suspense>
      )}
    </Router>
  );
}

export default App;
