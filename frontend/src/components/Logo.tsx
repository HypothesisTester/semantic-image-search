// The app's mark: a magnifying glass on a rounded tile. Drawn in the text
// colour, so it follows light and dark mode. public/logo.svg is the same
// shape for the browser tab.
export default function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="logo">
      <rect width="32" height="32" rx="8" fill="currentColor" />
      <circle cx="14.5" cy="14.5" r="6" fill="none" stroke="var(--bg)" strokeWidth="2.6" />
      <path d="M19 19l4.5 4.5" stroke="var(--bg)" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}
