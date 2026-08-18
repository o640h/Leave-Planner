export type DesktopSaveResult = 'saved' | 'cancelled'

type DesktopApi = {
  get_theme_preference?: () => Promise<'dark' | 'light' | 'system' | null>
  set_theme?: (
    preference: 'dark' | 'light' | 'system',
    resolvedTheme: 'dark' | 'light',
  ) => Promise<void>
  save_pdf?: (defaultFilename: string, encodedPdf: string) => Promise<DesktopSaveResult>
}

declare global {
  interface Window {
    pywebview?: { api?: DesktopApi }
  }
}

function encodedBlob(blob: Blob): Promise<string> {
  return blob.arrayBuffer().then((buffer) => {
    const bytes = new Uint8Array(buffer)
    let binary = ''
    for (let offset = 0; offset < bytes.length; offset += 32_768) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 32_768))
    }
    return window.btoa(binary)
  })
}

export async function savePdf(defaultFilename: string, blob: Blob): Promise<DesktopSaveResult> {
  const save = window.pywebview?.api?.save_pdf
  if (!save) throw new Error('PDF export is available in the installed desktop application.')
  return save(defaultFilename, await encodedBlob(blob))
}
