import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { DEMO_MODE } from '../config/api';
import { preloadSearchModel } from '../demo/preload';

interface SearchProps {
  /** 'hero' is the large field on the demo's landing page. */
  variant?: 'header' | 'hero';
  autoFocus?: boolean;
}

export default function Search({ variant = 'header', autoFocus = false }: SearchProps) {
  const [params] = useSearchParams();
  const [query, setQuery] = useState(params.get('q') ?? '');
  const navigate = useNavigate();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    // The query lives in the URL, so results can be refreshed, bookmarked and shared.
    navigate(`/result?q=${encodeURIComponent(trimmed)}`);
  };

  const placeholder =
    variant === 'hero' ? 'Describe a photo…' : DEMO_MODE ? 'Search photos' : 'Search your photos';

  return (
    <form onSubmit={submit} role="search" className={`search search--${variant}`}>
      <svg className="search__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="M15.5 15.5 20 20" />
      </svg>
      <input
        className="search__input"
        type="search"
        placeholder={placeholder}
        aria-label="Search your photos"
        maxLength={200}
        autoFocus={autoFocus}
        enterKeyHint="search"
        value={query}
        // Tapping or typing starts the model download; not focus, which the
        // landing page's autofocus would trigger on every visit.
        onPointerDown={preloadSearchModel}
        onChange={e => {
          preloadSearchModel();
          setQuery(e.target.value);
        }}
      />
    </form>
  );
}
