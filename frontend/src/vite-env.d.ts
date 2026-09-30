/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_INDEX_URL?: string;
  readonly VITE_SEARCH_URL?: string;
  readonly VITE_DEMO_MODE?: string;
  readonly VITE_DEMO_DATA_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** How many of the demo's first thumbnails the site serves itself (0: all from VITE_DEMO_DATA_URL). Set by vite.config.ts. */
declare const __DEMO_BUNDLED_THUMBNAILS__: number;
