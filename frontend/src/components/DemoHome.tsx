import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { REPO_URL } from '../config/api';
import { browseDemo } from '../api';
import type { BrowsePage } from '../api';
import PhotoLightbox from './PhotoLightbox';

const PAGE_SIZE = 24;
const SLOW_AFTER_MS = 3000;
type Photo = BrowsePage['items'][number];

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
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Photo | null>(null);

  // `loading` starts true for the first page; "Show more" sets it itself.
  const loadPage = (offset: number, signal?: AbortSignal) => {
    const slowTimer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return browseDemo(offset, PAGE_SIZE, signal)
      .then(page => {
        setTotal(page.total);
        setPhotos(prev => (offset === 0 ? page.items : [...prev, ...page.items]));
        setError(null);
      })
      .catch(err => {
        if (!signal?.aborted) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        window.clearTimeout(slowTimer);
        setSlow(false);
        if (!signal?.aborted) setLoading(false);
      });
  };

  useEffect(() => {
    const controller = new AbortController();
    loadPage(0, controller.signal);
    return () => controller.abort();
  }, []);

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        <h1 style={styles.title}>Search photos by describing them</h1>
        <p style={styles.lead}>
          This demo searches 5,000 photos from the COCO val2017 dataset. Type a description in
          the search bar, or try one of these:
        </p>

        <div style={styles.chips}>
          {EXAMPLES.map(q => (
            <button key={q} style={styles.chip} onClick={() => search(q)}>
              {q}
            </button>
          ))}
        </div>

        <div style={styles.sectionTitle}>
          Or browse the collection{total > 0 && ` (${total.toLocaleString()} photos)`}
        </div>
        {error && <div style={styles.notice}>Could not load photos: {error}</div>}
        {slow && photos.length === 0 && (
          <div style={styles.notice}>
            Waking up the demo server… this can take up to a minute after a quiet spell.
          </div>
        )}
        <div style={styles.grid}>
          {photos.map(photo => (
            <div key={photo.url} style={styles.card} onClick={() => setSelected(photo)}>
              <img src={photo.thumbnailUrl} alt="" loading="lazy" style={styles.image} />
            </div>
          ))}
        </div>
        {photos.length > 0 && photos.length < total && (
          <button style={styles.more} disabled={loading} onClick={() => {
              setLoading(true);
              loadPage(photos.length);
            }}>
            {loading ? 'Loading…' : 'Show more'}
          </button>
        )}

        <div style={styles.how}>
          <div style={styles.howTitle}>How it works</div>
          <p style={styles.howText}>
            OpenAI's CLIP model maps photos and text into the same 512-dimensional space, so a
            description and a photo of the same thing end up close together. Every photo was embedded
            once, ahead of time. Each search embeds your text and finds the nearest photos with an
            exact FAISS inner-product search.
          </p>
          <p style={styles.howText}>
            On this dataset the correct photo is in the top 5 for 54.8% of human-written captions
            (Recall@5), in line with published results for this model. The full app adds sign-in and
            per-user photo libraries.
          </p>
          <a href={REPO_URL} target="_blank" rel="noreferrer" style={styles.link}>
            Code, design notes and benchmark on GitHub →
          </a>
        </div>
      </div>

      {selected && (
        <PhotoLightbox
          url={selected.url}
          alt=""
          caption={selected.caption}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

const styles = {
  container: {
    minHeight: 'calc(100vh - 65px)',
    backgroundColor: '#202124',
    color: '#e8eaed',
    padding: '48px 24px',
  },
  content: {
    maxWidth: '1100px',
    margin: '0 auto',
  },
  title: {
    fontSize: '32px',
    fontWeight: '400' as const,
    margin: '0 0 12px',
  },
  lead: {
    fontSize: '16px',
    lineHeight: 1.5,
    color: '#bdc1c6',
    margin: '0 0 24px',
    maxWidth: '760px',
  },
  chips: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: '10px',
    marginBottom: '40px',
  },
  sectionTitle: {
    fontSize: '14px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
    color: '#9aa0a6',
    marginBottom: '12px',
  },
  notice: {
    color: '#bdc1c6',
    fontSize: '15px',
    margin: '12px 0',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
    gap: '8px',
  },
  card: {
    position: 'relative' as const,
    paddingBottom: '100%',
    backgroundColor: '#282828',
    borderRadius: '8px',
    overflow: 'hidden',
    cursor: 'pointer',
  },
  image: {
    position: 'absolute' as const,
    inset: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
  },
  more: {
    display: 'block',
    margin: '16px auto 0',
    backgroundColor: 'transparent',
    color: '#8ab4f8',
    border: '1px solid #5f6368',
    borderRadius: '18px',
    padding: '8px 24px',
    fontSize: '14px',
    cursor: 'pointer',
  },
  chip: {
    backgroundColor: '#303134',
    color: '#e8eaed',
    border: '1px solid #5f6368',
    borderRadius: '18px',
    padding: '8px 16px',
    fontSize: '14px',
    cursor: 'pointer',
  },
  how: {
    borderTop: '1px solid #3c4043',
    paddingTop: '24px',
    marginTop: '40px',
    maxWidth: '760px',
  },
  howTitle: {
    fontSize: '14px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
    color: '#9aa0a6',
    marginBottom: '12px',
  },
  howText: {
    fontSize: '15px',
    lineHeight: 1.6,
    color: '#bdc1c6',
    margin: '0 0 12px',
  },
  link: {
    color: '#8ab4f8',
    textDecoration: 'none',
    fontSize: '15px',
  },
};
