// result.tsx
import { useLocation, useNavigate } from "react-router-dom";
import SearchResultsGallery from "../components/SearchResultsGallery";

interface ResultLocationState {
  query: string;
  userId: string | null;
}

export default function Result() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as ResultLocationState | null;

  const query = state?.query ?? "";
  const userId = state?.userId ?? null;

  const pageStyles = {
    container: {
      minHeight: "100vh",
      backgroundColor: "#202124",
      color: "#e8eaed",
      padding: "16px 24px",
    },
    backButton: {
      marginBottom: "16px",
      padding: "8px 12px",
      borderRadius: "8px",
      border: "1px solid #3c4043",
      backgroundColor: "transparent",
      color: "#e8eaed",
      cursor: "pointer",
      display: "inline-flex",
      alignItems: "center",
      gap: "8px",
      fontSize: "14px",
    },
    heading: {
      fontSize: "24px",
      marginBottom: "8px",
    },
    meta: {
      fontSize: "14px",
      marginBottom: "4px",
      color: "#9aa0a6",
    },
  } as const;

  return (
    <div style={pageStyles.container}>
      <button
        style={pageStyles.backButton}
        onClick={() => navigate("/home")}
      >
        ← Back
      </button>

      <h1 style={pageStyles.heading}>Search Results</h1>
      
      <SearchResultsGallery userId={userId} query={query} />
    </div>
  );
}
