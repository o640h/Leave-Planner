import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/montserrat'

import { App } from './App'
import './styles.css'
import './themes/light.css'

const root = createRoot(document.getElementById('root')!)
root.render(
  <StrictMode>
    <App />
  </StrictMode>,
)
