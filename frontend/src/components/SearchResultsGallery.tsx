import { useEffect, useState } from "react";

interface SearchResultsGalleryProps {
  userId: string | null;
  query: string;
}

interface SearchResult {
  rank: number;
  score: number;
  url: string;
}

export default function SearchResultsGallery({
  userId,
  query,
}: SearchResultsGalleryProps) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<SearchResult | null>(null);

  useEffect(() => {
    if (!userId || !query) {
      setLoading(false);
      return;
    }

    const fetchResults = async () => {
    try {
        setLoading(true);
        setError(null);

        const response = await fetch("https://semantic-search-backend-628129189292.us-central1.run.app/search", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            userId,      
            text: query,
            k: 5,       
        }),
        });

        if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        setResults(data.results || []);
    } catch (err: any) {
        console.error("Error fetching search results:", err);
        setError(err.message || "Failed to fetch results");
    } finally {
        setLoading(false);
    }
    };


    fetchResults();
  }, [userId, query]);

  if (!userId || !query) {
    return (
      <div style={styles.emptyContainer}>
        <div style={styles.emptyTitle}>Missing search info</div>
        <div style={styles.emptyText}>User ID or search text is empty.</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingText}>Searching your photos...</div>
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
          Try a different search term or upload more photos.
        </div>
      </div>
    );
  }

  return (
    <>
      <div style={styles.gallery}>
        {results.map((image) => (
          <div
            key={image.rank}
            style={styles.imageCard}
            onClick={() => setSelectedImage(image)}
          >
            <img
              src={image.url}
              alt={`Result ${image.rank}`}
              style={styles.image}
            />
          </div>
        ))}
      </div>

      {selectedImage && (
        <div
          style={styles.viewerOverlay}
          onClick={() => setSelectedImage(null)}
        >
          <div
            style={styles.viewerContent}
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={selectedImage.url}
              alt={`Result ${selectedImage.rank}`}
              style={styles.viewerImage}
            />
          </div>
        </div>
      )}
    </>
  );
}

const styles = {
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
    maxWidth: "100%",
    maxHeight: "100%",
    borderRadius: "8px",
  },
};
