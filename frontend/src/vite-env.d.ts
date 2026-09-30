/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_INDEX_URL?: string;
  readonly VITE_SEARCH_URL?: string;
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
