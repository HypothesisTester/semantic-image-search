import { useSearchParams } from 'react-router-dom';
import SearchResultsGallery from './SearchResultsGallery';

export default function Result() {
  const [params] = useSearchParams();
  const query = (params.get('q') ?? '').trim();

  return (
    <main className="page">
      {/* Remounted per query, so each search starts from a clean state. */}
      <SearchResultsGallery key={query} query={query} />
    </main>
  );
}
