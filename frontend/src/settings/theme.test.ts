import { afterEach, expect, it, vi } from 'vitest'

import { getThemePreference, initialiseTheme, saveThemePreference } from './theme'

afterEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.theme
  delete document.documentElement.dataset.themePreference
  vi.unstubAllGlobals()
})

it('uses light for a browser without a saved preference', () => {
  initialiseTheme()

  expect(getThemePreference()).toBe('light')
  expect(document.documentElement.dataset.theme).toBe('light')
  expect(document.documentElement.dataset.themePreference).toBe('light')
})

it('stores and applies an explicit browser theme preference', () => {
  saveThemePreference('dark')

  expect(getThemePreference()).toBe('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
  expect(document.documentElement.dataset.themePreference).toBe('dark')
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
