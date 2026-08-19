export function downloadFile(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.hidden = true
  document.body.append(link)

  try {
    link.click()
  } finally {
    link.remove()
    URL.revokeObjectURL(objectUrl)
  }
}
