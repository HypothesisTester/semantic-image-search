import { existsSync, readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import type { Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// Demo data copied into the site by scripts/bundle-demo-data.mjs, if any.
const bundleFile = new URL('./public/demo-data/bundle.json', import.meta.url)
const bundledThumbnails: string[] = existsSync(bundleFile)
  ? JSON.parse(readFileSync(bundleFile, 'utf8')).thumbnails
  : []

// Start the first page's list and the first screen of photos downloading alongside
// the app's code, instead of after it has loaded and run.
function preloadDemoData(): Plugin {
  return {
    name: 'preload-demo-data',
    transformIndexHtml() {
      if (bundledThumbnails.length === 0) return []
      return [
        { tag: 'link', attrs: { rel: 'preload', href: '/demo-data/first-page.json', as: 'fetch', crossorigin: 'anonymous' }, injectTo: 'head' },
        ...bundledThumbnails.slice(0, 12).map(file => ({
          tag: 'link',
          attrs: { rel: 'preload', href: `/demo-data/thumbnails/${file}`, as: 'image', fetchpriority: 'high' },
          injectTo: 'head' as const,
        })),
      ]
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), preloadDemoData()],
  define: {
    __DEMO_BUNDLED_THUMBNAILS__: JSON.stringify(bundledThumbnails.length),
  },
})
