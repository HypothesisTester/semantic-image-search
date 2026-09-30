import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { STATIC_DEMO } from '../config/api';
import { browseDemo } from '../api';
import type { BrowsePage } from '../api';
import PhotoLightbox from './PhotoLightbox';
import PhotoTile from './PhotoTile';
import Search from './Search';

const PAGE_SIZE = 24;
const SLOW_AFTER_MS = 3000;
// Start loading the next page this far before the end of the grid scrolls into view.
const PRELOAD_MARGIN = '800px 0px';
type Photo = BrowsePage['items'][number];

// Must match backend/demo/export_static.py, which precomputes their vectors.
const EXAMPLES = [
  'a dog catching a frisbee',
  'a plate of food with broccoli',
  'people surfing on big waves',
  'a cat sleeping on a laptop',
  'a red double-decker bus',
  'a snowy mountain with skiers',
];

export default function DemoHome() {
  const navigate = useNavigate();
  const search = (q: string) => navigate(`/result?q=${encodeURIComponent(q)}`);

  const [photos, setPhotos] = useState<Photo[]>([]);
  const [total, setTotal] = useState(0);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Photo | null>(null);
  const loadingOffset = useRef<number | null>(null);
  const sentinel = useRef<HTMLDivElement>(null);

  const loadPage = useCallback((offset: number, signal?: AbortSignal) => {
    if (loadingOffset.current === offset) return;
    loadingOffset.current = offset;
    browseDemo(offset, PAGE_SIZE, signal)
      .then(page => {
        setTotal(page.total);
        // Only append a page that continues the list, so a repeated request can't duplicate photos.
        setPhotos(prev => (prev.length === offset ? [...prev, ...page.items] : prev));
        setError(null);
      })
      .catch(err => {
        if (!signal?.aborted) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (loadingOffset.current === offset) loadingOffset.current = null;
      });
  }, []);

  // First page.
  useEffect(() => {
    const controller = new AbortController();
    const slowTimer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    loadPage(0, controller.signal);
    return () => {
      controller.abort();
      window.clearTimeout(slowTimer);
      loadingOffset.current = null;
    };
  }, [loadPage]);

  // Later pages: load more whenever the end of the grid comes near the screen.
  // The observer is recreated after each page, and reports at once if the end
  // is still near, so a tall screen keeps filling until it has enough.
  const hasMore = photos.length > 0 && photos.length < total;
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasMore || error) return;
    const observer = new IntersectionObserver(
      entries => {
        if (entries.some(e => e.isIntersecting)) loadPage(photos.length);
      },
      { rootMargin: PRELOAD_MARGIN },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, error, photos.length, loadPage]);

  return (
    <main className="page">
      <section className="hero">
        <h1 className="hero__title">Find photos by describing them.</h1>
        <p className="hero__subtitle">
          Type what you're looking for. The search looks at the pictures themselves, not tags or captions.
        </p>
        <div className="hero__search">
          <Search variant="hero" autoFocus />
        </div>
        <div className="chips">
          {EXAMPLES.map(q => (
            <button key={q} className="chip" onClick={() => search(q)}>
              {q}
            </button>
          ))}
        </div>
      </section>

      {slow && photos.length === 0 && !error && !STATIC_DEMO && (
        <p className="notice">Waking up the demo server… this can take up to a minute after a quiet spell.</p>
      )}

      <div className="grid">
        {photos.map(photo => (
          <PhotoTile key={photo.url} src={photo.thumbnailUrl} alt="" onOpen={() => setSelected(photo)} />
        ))}
        {photos.length === 0 && !error && Array.from({ length: PAGE_SIZE }, (_, i) => <div key={i} className="skeleton" />)}
      </div>

      {error ? (
        <div className="notice">
          <p>Couldn't load photos: {error}</p>
          <button className="button" style={{ marginTop: 12 }} onClick={() => loadPage(photos.length)}>
            Try again
          </button>
        </div>
      ) : (
        hasMore && (
          <div className="loading-more" aria-hidden="true">
            <div className="spinner" />
          </div>
        )
      )}
      <div ref={sentinel} className="sentinel" />

      {selected && (
        <PhotoLightbox url={selected.url} alt="" caption={selected.caption} onClose={() => setSelected(null)} />
      )}
    </main>
  );
}
