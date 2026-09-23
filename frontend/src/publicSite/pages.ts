export const publicPages = [
  { path: '/about', label: 'About' },
  { path: '/privacy', label: 'Privacy' },
  { path: '/terms', label: 'Terms' },
  { path: '/contact', label: 'Contact' },
] as const

export type PublicPagePath = (typeof publicPages)[number]['path']

export function isPublicPage(path: string): path is PublicPagePath {
  return publicPages.some((page) => page.path === path)
}
