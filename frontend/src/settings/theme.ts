export type ThemePreference = 'dark' | 'light' | 'system'

const storageKey = 'leave-planner-theme'

type DesktopThemeApi = {
  get_theme_preference?: () => Promise<ThemePreference | null>
  set_theme?: (preference: ThemePreference, resolvedTheme: 'dark' | 'light') => Promise<void>
}

declare global {
  interface Window {
    pywebview?: { api?: DesktopThemeApi }
  }
}

function systemTheme(): 'dark' | 'light' {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function getThemePreference(): ThemePreference {
  const saved = window.localStorage.getItem(storageKey)
  return saved === 'light' || saved === 'system' ? saved : 'dark'
}

export function applyTheme(preference: ThemePreference) {
  const resolved = preference === 'system' ? systemTheme() : preference
  document.documentElement.dataset.theme = resolved
  document.documentElement.dataset.themePreference = preference
  void window.pywebview?.api?.set_theme?.(preference, resolved)
}

export function saveThemePreference(preference: ThemePreference) {
  window.localStorage.setItem(storageKey, preference)
  applyTheme(preference)
}

export function initialiseTheme() {
  applyTheme(getThemePreference())

  async function syncDesktopPreference() {
    const saved = await window.pywebview?.api?.get_theme_preference?.()
    if (saved === 'dark' || saved === 'light' || saved === 'system') {
      window.localStorage.setItem(storageKey, saved)
      applyTheme(saved)
      return
    }
    applyTheme(getThemePreference())
  }

  if (window.pywebview?.api) void syncDesktopPreference()
  else window.addEventListener('pywebviewready', () => void syncDesktopPreference(), { once: true })

  window.matchMedia?.('(prefers-color-scheme: light)').addEventListener('change', () => {
    if (getThemePreference() === 'system') applyTheme('system')
  })
}
