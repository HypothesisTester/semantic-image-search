interface PhotoTileProps {
  src: string;
  alt: string;
  onOpen: () => void;
  /** For the first screen of photos: load straight away, ahead of other downloads. */
  priority?: boolean;
}

// A square photo in a grid. The photo fades in once it has loaded, over a
// placeholder of the same size, so the grid never jumps while scrolling.
export default function PhotoTile({ src, alt, onOpen, priority = false }: PhotoTileProps) {
  return (
    <button className="tile" onClick={onOpen} aria-label={alt ? `Open ${alt}` : 'Open photo'}>
      <img
        src={src}
        alt={alt}
        loading={priority ? 'eager' : 'lazy'}
        fetchPriority={priority ? 'high' : 'auto'}
        decoding="async"
        onLoad={e => (e.currentTarget.dataset.loaded = 'true')}
      />
    </button>
  );
}
