import { useEffect } from 'react';

interface PhotoLightboxProps {
  url: string;
  alt: string;
  /** COCO's human-written caption, shown for context in the demo. */
  caption?: string;
  onClose: () => void;
}

// Full-size view of one photo. Closes on Escape, the close button, or a click outside the photo.
export default function PhotoLightbox({ url, alt, caption, onClose }: PhotoLightboxProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div className="lightbox" onClick={onClose} role="dialog" aria-modal="true">
      <button className="lightbox__close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <div className="lightbox__content" onClick={e => e.stopPropagation()}>
        <img className="lightbox__image" src={url} alt={alt} />
        {caption && (
          <>
            <p className="lightbox__caption">“{caption}”</p>
            <p className="lightbox__note">
              A caption written by a person when the COCO dataset was made. Search never reads it: it compares
              your words with the photo itself.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
