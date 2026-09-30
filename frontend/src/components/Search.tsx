import { useState } from "react";
import type { FormEvent, ChangeEvent, CSSProperties } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

interface SearchProps {
  styles: Record<string, CSSProperties>;
}

export default function Search({ styles }: SearchProps) {
  const [params] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState(params.get("q") ?? "");
  const navigate = useNavigate();

  const handleSearch = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = searchQuery.trim();
    if (!trimmed) return;
    // The query lives in the URL, so results can be refreshed, bookmarked and shared.
    navigate(`/result?q=${encodeURIComponent(trimmed)}`);
  };

  return (
    <form onSubmit={handleSearch} style={styles.searchForm}>
      <div style={styles.searchContainer}>
        <svg style={styles.searchIcon} viewBox="0 0 24 24">
          <path
            d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"
            fill="#5f6368"
          />
        </svg>

        <input
          type="text"
          placeholder="Search your photos"
          aria-label="Search your photos"
          maxLength={200}
          value={searchQuery}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
          style={styles.searchInput}
        />
      </div>
    </form>
  );
}
