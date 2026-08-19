import { afterEach, expect, it, vi } from 'vitest'

import { getThemePreference, initialiseTheme, saveThemePreference } from './theme'

afterEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.theme
  delete document.documentElement.dataset.themePreference
  vi.unstubAllGlobals()
})

it('stores and applies an explicit browser theme preference', () => {
  saveThemePreference('light')

  expect(getThemePreference()).toBe('light')
  expect(document.documentElement.dataset.theme).toBe('light')
  expect(document.documentElement.dataset.themePreference).toBe('light')
})

it('resolves the system preference in the browser', () => {
  const addEventListener = vi.fn()
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener }))
  window.localStorage.setItem('leave-planner-theme', 'system')

  initialiseTheme()

  expect(document.documentElement.dataset.theme).toBe('light')
  expect(document.documentElement.dataset.themePreference).toBe('system')
  expect(addEventListener).toHaveBeenCalledWith('change', expect.any(Function))
})
