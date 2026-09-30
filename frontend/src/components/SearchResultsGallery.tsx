import { useEffect, useState } from 'react';
import { searchPhotos, ApiError } from '../api';
import type { SearchResult } from '../api';
import { DEMO_MODE, RESULTS_PER_SEARCH, STATIC_DEMO } from '../config/api';
import type { ModelProgress } from '../demo/textEncoder';
import PhotoLightbox from './PhotoLightbox';
import PhotoTile from './PhotoTile';

interface SearchResultsGalleryProps {
  query: string;
}

// A server that has been idle can take a while to answer the first request
// (a free host starting its container). Past this delay, say so.
const SLOW_AFTER_MS = 3000;

export default function SearchResultsGallery({ query }: SearchResultsGalleryProps) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [model, setModel] = useState<ModelProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SearchResult | null>(null);

  useEffect(() => {
    if (!query) return;
    // The parent remounts this component for each new query (key={query}),
    // so state starts fresh. Aborting on unmount still guarantees a slow old
    // search can never overwrite the results of a newer one.
    const controller = new AbortController();
    const slowTimer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS);

    searchPhotos(query, RESULTS_PER_SEARCH, controller.signal, p => {
      if (!controller.signal.aborted) setModel(p);
    })
      .then(setResults)
      .catch(err => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError || err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        window.clearTimeout(slowTimer);
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => {
      controller.abort();
      window.clearTimeout(slowTimer);
    };
  }, [query]);

  if (!query) {
    return (
      <div className="empty">
        <h1 className="empty__title">Search for a photo</h1>
        <p className="empty__text">Describe what you're looking for, like “a dog on a beach”.</p>
      </div>
    );
  }

  let body;
  let meta = '';
  if (loading) {
    const downloading = model && model.loadedMB < model.totalMB;
    meta = model ? 'Getting the search model ready…' : 'Searching…';
    body = (
      <>
        {model && (
          <div className="progress" role="status">
            <p className="muted">
              {downloading
                ? `Downloading the search model: ${model.loadedMB.toFixed(0)} of ${model.totalMB.toFixed(0)} MB`
                : 'Starting the search model…'}
            </p>
            <p className="section-meta">Only the first time. Your browser keeps it for next time.</p>
            <div className="progress__track">
              <div className="progress__bar" style={{ width: `${Math.min(100, (100 * model.loadedMB) / model.totalMB)}%` }} />
            </div>
          </div>
        )}
        {!model && slow && !STATIC_DEMO && (
          <p className="notice">
            {DEMO_MODE
              ? 'Waking up the demo server… the first search after a quiet spell can take up to a minute.'
              : 'Still searching…'}
          </p>
        )}
        <div className="grid grid--large">
          {Array.from({ length: RESULTS_PER_SEARCH }, (_, i) => (
            <div key={i} className="skeleton" />
          ))}
        </div>
      </>
    );
  } else if (error) {
    body = (
      <div className="empty">
        <h2 className="empty__title">Something went wrong</h2>
        <p className="empty__text">{error}</p>
      </div>
    );
  } else if (results.length === 0) {
    body = (
      <div className="empty">
        <h2 className="empty__title">No matching photos</h2>
        <p className="empty__text">
          {DEMO_MODE ? 'Try a different description.' : 'Upload some photos first, or try a different description.'}
        </p>
      </div>
    );
  } else {
    meta = `Top ${results.length} matches`;
    body = (
      <div className="grid grid--large">
        {results.map(r => (
          <PhotoTile key={r.url} src={r.thumbnailUrl} alt={`Result ${r.rank}`} onOpen={() => setSelected(r)} />
        ))}
      </div>
    );
  }

  return (
    <>
      <div className="results-head">
        <h1 className="results-title">“{query}”</h1>
        {meta && <p className="section-meta">{meta}</p>}
      </div>
      {body}
      {selected && (
        <PhotoLightbox
          url={selected.url}
          alt={`Result ${selected.rank}`}
          caption={selected.caption}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
