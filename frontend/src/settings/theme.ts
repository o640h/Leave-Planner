export type ThemePreference = 'dark' | 'light' | 'system'

const storageKey = 'leave-planner-theme'

function systemTheme(): 'dark' | 'light' {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function getThemePreference(): ThemePreference {
  const saved = window.localStorage.getItem(storageKey)
  return saved === 'dark' || saved === 'system' ? saved : 'light'
}

export function applyTheme(preference: ThemePreference) {
  const resolved = preference === 'system' ? systemTheme() : preference
  document.documentElement.dataset.theme = resolved
  document.documentElement.dataset.themePreference = preference
}

export function saveThemePreference(preference: ThemePreference) {
  window.localStorage.setItem(storageKey, preference)
  applyTheme(preference)
}

export function initialiseTheme() {
  applyTheme(getThemePreference())

  window.matchMedia?.('(prefers-color-scheme: light)').addEventListener('change', () => {
    if (getThemePreference() === 'system') applyTheme('system')
  })
}
