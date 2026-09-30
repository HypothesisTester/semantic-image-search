import { useState } from 'react';
import { REPO_URL } from '../config/api';

// Link to the source code, shown with GitHub's official mark. The two logo
// files come from https://github.com/logos and live in public/; if they are
// missing, a plain code icon is shown instead.
export default function GitHubLink() {
  const [logoMissing, setLogoMissing] = useState(false);

  return (
    <a
      href={REPO_URL}
      target="_blank"
      rel="noreferrer"
      className="icon-button"
      aria-label="Source code on GitHub"
      title="Source code on GitHub"
    >
      {logoMissing ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M8.5 7 3.5 12l5 5M15.5 7l5 5-5 5" />
        </svg>
      ) : (
        <picture>
          <source srcSet="/github-mark-white.svg" media="(prefers-color-scheme: dark)" />
          <img src="/github-mark.svg" alt="" className="icon-button__logo" onError={() => setLogoMissing(true)} />
        </picture>
      )}
    </a>
  );
}
