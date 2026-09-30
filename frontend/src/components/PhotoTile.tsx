interface PhotoTileProps {
  src: string;
  alt: string;
  onOpen: () => void;
}

// A square photo in a grid. The photo fades in once it has loaded, over a
// placeholder of the same size, so the grid never jumps while scrolling.
export default function PhotoTile({ src, alt, onOpen }: PhotoTileProps) {
  return (
    <button className="tile" onClick={onOpen} aria-label={alt ? `Open ${alt}` : 'Open photo'}>
      <img
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        onLoad={e => (e.currentTarget.dataset.loaded = 'true')}
      />
    </button>
  );
}
