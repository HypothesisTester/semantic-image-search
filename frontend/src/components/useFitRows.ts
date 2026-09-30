import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';

// Show only the children of a wrapping flex row that fit in `maxRows` rows,
// hiding the rest whole, so a narrow screen never shows a half-cut item.
// Re-measured whenever the container's width changes.
export function useFitRows(ref: RefObject<HTMLElement | null>, maxRows: number) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    let lastWidth = -1;

    const fit = () => {
      if (el.clientWidth === lastWidth) return;
      lastWidth = el.clientWidth;
      const items = Array.from(el.children) as HTMLElement[];
      items.forEach(item => (item.hidden = false));
      const rowTops = [...new Set(items.map(item => item.offsetTop))].sort((a, b) => a - b);
      const lastRowTop = rowTops[maxRows - 1] ?? Infinity;
      items.forEach(item => (item.hidden = item.offsetTop > lastRowTop));
    };

    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, maxRows]);
}
