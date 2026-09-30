// When to fetch the in-browser search model ahead of a typed search.
//
// The model is 127 MB, so it is fetched early only where that is cheap:
//   - as soon as someone starts using the search box, on any device;
//   - shortly after the page settles, on a computer (mouse or trackpad) or
//     a connection the browser reports as Wi-Fi or wired, unless the
//     browser asks to save data or reports a slow connection.
// Phones on mobile data therefore only download it once the visitor starts
// typing. Either way the browser caches it, so later visits skip the download.

import { STATIC_DEMO } from '../config/api';

interface NetworkInformation {
  saveData?: boolean;
  effectiveType?: string;
  type?: string;
}

/** Begin loading the model. Does nothing outside the static demo. */
export function preloadSearchModel(): void {
  if (!STATIC_DEMO) return;
  import('./textEncoder').then(m => m.preloadEncoder()).catch(() => {});
}

export function shouldPreloadEagerly(): boolean {
  const connection = (navigator as Navigator & { connection?: NetworkInformation }).connection;
  if (connection?.saveData) return false;
  if (connection?.effectiveType && connection.effectiveType !== '4g') return false;
  if (connection?.type === 'wifi' || connection?.type === 'ethernet') return true;
  if (connection?.type === 'cellular') return false;
  return window.matchMedia('(pointer: fine)').matches;
}

/** After the page has loaded and gone quiet, start the download if it is cheap here. */
export function schedulePreload(delayMs = 1500): () => void {
  if (!STATIC_DEMO || !shouldPreloadEagerly()) return () => {};
  let idleHandle: number | undefined;
  const timer = window.setTimeout(() => {
    if ('requestIdleCallback' in window) idleHandle = window.requestIdleCallback(preloadSearchModel, { timeout: 3000 });
    else preloadSearchModel();
  }, delayMs);
  return () => {
    window.clearTimeout(timer);
    if (idleHandle !== undefined) window.cancelIdleCallback(idleHandle);
  };
}
