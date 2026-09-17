import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/montserrat'

import { App } from './App'
import './styles.css'
import './themes/light.css'

const root = createRoot(document.getElementById('root')!)
const developmentCatalogueRequested =
  import.meta.env.DEV &&
  (window.location.pathname === '/ui' || window.location.pathname.startsWith('/ui/'))

if (developmentCatalogueRequested) {
  void import('./development/UiCatalogue').then(({ UiCatalogue }) => {
    root.render(
      <StrictMode>
        <UiCatalogue />
      </StrictMode>,
    )
  })
} else {
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
