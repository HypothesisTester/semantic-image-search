import { useEffect } from "react";

interface PhotoLightboxProps {
  url: string;
  alt: string;
  /** COCO's human-written caption, shown for context in the demo. */
  caption?: string;
  onClose: () => void;
}

// Full-size view of one photo. Closes on Escape or a click outside the photo.
export default function PhotoLightbox({ url, alt, caption, onClose }: PhotoLightboxProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.content} onClick={(e) => e.stopPropagation()}>
        <img src={url} alt={alt} style={styles.image} />
        {caption && (
          <div style={styles.captionBox}>
            <div style={styles.caption}>“{caption}”</div>
            <div style={styles.note}>
              A caption written by a person when the COCO dataset was made. Search never reads it:
              it compares your words with the photo itself.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: "fixed" as const,
    inset: 0,
    backgroundColor: "rgba(0,0,0,0.85)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2000,
    padding: "24px",
  },
  content: {
    maxWidth: "90vw",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
  },
  image: {
    display: "block",
    maxWidth: "90vw",
    maxHeight: "75vh",
    borderRadius: "8px",
  },
  captionBox: {
    maxWidth: "640px",
    marginTop: "14px",
    textAlign: "center" as const,
  },
  caption: {
    color: "#e8eaed",
    fontSize: "16px",
    marginBottom: "6px",
  },
  note: {
    color: "#9aa0a6",
    fontSize: "13px",
    lineHeight: 1.45,
  },
};
