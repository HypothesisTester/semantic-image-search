import { useEffect, useState } from "react";
import { searchPhotos, ApiError } from "../api";
import type { SearchResult } from "../api";
import { DEMO_MODE, RESULTS_PER_SEARCH } from "../config/api";

interface SearchResultsGalleryProps {
  query: string;
}

// Free Hugging Face Spaces go to sleep when idle, and the first request
// after that waits while the container starts. Past this delay, say so.
const SLOW_AFTER_MS = 3000;

export default function SearchResultsGallery({ query }: SearchResultsGalleryProps) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<SearchResult | null>(null);

  useEffect(() => {
    if (!query) return;
    // The parent remounts this component for each new query (key={query}),
    // so state starts fresh. Aborting on unmount still guarantees a slow old
    // search can never overwrite the results of a newer one.
    const controller = new AbortController();
    const slowTimer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS);

    searchPhotos(query, RESULTS_PER_SEARCH, controller.signal)
      .then(setResults)
      .catch((err) => {
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
      <div style={styles.emptyContainer}>
        <div style={styles.emptyTitle}>Type something to search for</div>
        <div style={styles.emptyText}>For example: “a dog on a beach”.</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingText}>
          {slow && DEMO_MODE
            ? "Waking up the demo server… the first search after a quiet spell can take up to a minute."
            : slow
              ? "Still searching…"
              : DEMO_MODE
                ? "Searching…"
                : "Searching your photos…"}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.emptyContainer}>
        <div style={styles.emptyTitle}>Something went wrong</div>
        <div style={styles.emptyText}>{error}</div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div style={styles.emptyContainer}>
        <div style={styles.emptyIcon}>🔍</div>
        <div style={styles.emptyTitle}>No matching photos</div>
        <div style={styles.emptyText}>
          {DEMO_MODE ? "Try a different description." : "Upload some photos first, or try a different description."}
        </div>
      </div>
    );
  }

  return (
    <>
      <div style={styles.gallery}>
        {results.map((image) => (
          <figure key={image.url} style={styles.figure}>
            <div style={styles.imageCard} onClick={() => setSelectedImage(image)}>
              <img
                src={image.thumbnailUrl}
                alt={image.caption ?? `Result ${image.rank}`}
                loading="lazy"
                style={styles.image}
              />
            </div>
            {image.caption && <figcaption style={styles.caption}>{image.caption}</figcaption>}
          </figure>
        ))}
      </div>

      {selectedImage && (
        <div style={styles.viewerOverlay} onClick={() => setSelectedImage(null)}>
          <div style={styles.viewerContent} onClick={(e) => e.stopPropagation()}>
            <img
              src={selectedImage.url}
              alt={selectedImage.caption ?? `Result ${selectedImage.rank}`}
              style={styles.viewerImage}
            />
            {selectedImage.caption && <div style={styles.viewerCaption}>{selectedImage.caption}</div>}
          </div>
        </div>
      )}
    </>
  );
}

const styles = {
  figure: {
    margin: 0,
  },
  caption: {
    marginTop: "6px",
    fontSize: "13px",
    lineHeight: 1.35,
    color: "#9aa0a6",
  },
  viewerCaption: {
    marginTop: "12px",
    textAlign: "center" as const,
    color: "#e8eaed",
    fontSize: "15px",
  },
  gallery: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
    gap: "8px",
    padding: "16px",
  },
  imageCard: {
    position: "relative" as const,
    paddingBottom: "100%",
    backgroundColor: "#282828",
    borderRadius: "8px",
    overflow: "hidden",
    cursor: "pointer",
    transition: "transform 0.2s ease, boxShadow 0.2s ease",
  },
  image: {
    position: "absolute" as const,
    top: 0,
    left: 0,
    width: "100%",
    height: "100%",
    objectFit: "cover" as const,
  },
  loadingContainer: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "400px",
  },
  loadingText: {
    color: "#e8eaed",
    fontSize: "16px",
  },
  emptyContainer: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    minHeight: "400px",
    padding: "40px",
  },
  emptyIcon: {
    fontSize: "64px",
    marginBottom: "16px",
  },
  emptyTitle: {
    fontSize: "22px",
    color: "#e8eaed",
    marginBottom: "8px",
    fontWeight: "400" as const,
  },
  emptyText: {
    fontSize: "14px",
    color: "#9aa0a6",
    textAlign: "center" as const,
  },
  viewerOverlay: {
    position: "fixed" as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.85)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2000,
  },
  viewerContent: {
    maxWidth: "90vw",
    maxHeight: "90vh",
  },
  viewerImage: {
    display: "block",
    maxWidth: "90vw",
    maxHeight: "80vh",
    borderRadius: "8px",
  },
};
