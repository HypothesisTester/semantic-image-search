import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// After a new deployment, a page opened before it can ask for code files that
// no longer exist (each deployment renames them). Reload once to get the
// current version, but not in a loop if the files are genuinely missing.
const RELOADED_AT = 'reloaded-for-new-version-at'
window.addEventListener('vite:preloadError', event => {
  let last = 0
  try {
    last = Number(sessionStorage.getItem(RELOADED_AT)) || 0
    sessionStorage.setItem(RELOADED_AT, String(Date.now()))
  } catch {
    return // storage unavailable: can't guard against a reload loop, so show the error instead
  }
  if (Date.now() - last < 10_000) return // just reloaded for this; let the error show
  event.preventDefault()
  window.location.reload()
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
