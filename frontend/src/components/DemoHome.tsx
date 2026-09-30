import { useNavigate } from 'react-router-dom';
import { REPO_URL } from '../config/api';

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
    maxWidth: '760px',
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
  },
  chips: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: '10px',
    marginBottom: '48px',
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
