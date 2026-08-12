import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/montserrat'

import { App } from './App'
import { initialiseTheme } from './settings/theme'
import './styles.css'
import './themes/light.css'

initialiseTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
