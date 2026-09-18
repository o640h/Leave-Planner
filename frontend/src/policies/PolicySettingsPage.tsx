import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { downloadFile } from '../system/download'
import { getPolicyDocumentPdf, getPolicyDocuments } from './api'
import type { PolicyDocument } from './types'

function displayEffectiveDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-GB', {
    month: 'long',
    year: 'numeric',
  })
}

type PolicySettingsPageProps = {
  initialDocuments?: PolicyDocument[]
}

export function PolicySettingsPage({ initialDocuments }: PolicySettingsPageProps = {}) {
  const [documents, setDocuments] = useState<PolicyDocument[] | null>(initialDocuments ?? null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (initialDocuments) return
    let active = true

    getPolicyDocuments()
      .then((result) => {
        if (active) setDocuments(result)
      })
      .catch((reason: unknown) => {
        if (active) setError(operatorErrorMessage(reason))
      })

    return () => {
      active = false
    }
  }, [initialDocuments])

  async function download(document: PolicyDocument) {
    setDownloadingId(document.document_id)
    setError(null)
    try {
      const file = await getPolicyDocumentPdf(document.document_id)
      downloadFile(file.blob, file.filename ?? document.filename)
    } catch (reason) {
      setError(operatorErrorMessage(reason))
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <section className="settings-section policy-settings" aria-labelledby="policy-settings-title">
      <header className="settings-content-heading">
        <span className="section-label">Reference Library</span>
        <h2 id="policy-settings-title">Policy &amp; Guidance</h2>
      </header>

      {error ? <p className="form-notice form-notice--error">{error}</p> : null}

      <section className="settings-panel policy-library" aria-label="Policy Documents">
        <header className="policy-library-heading">
          <div>
            <h3>Annual Leave Documents</h3>
            <p>Read-only source documents used for annual leave policy and calculations.</p>
          </div>
          <span>{documents?.length ?? 0} Documents</span>
        </header>

        {documents ? (
          <ul className="policy-document-list">
            {documents.map((document) => (
              <li key={document.document_id}>
                <span className="policy-document-icon" aria-hidden="true">
                  <AppIcon name="document" />
                </span>
                <div className="policy-document-title">
                  <span>{document.document_type}</span>
                  <strong>{document.title}</strong>
                </div>
                <dl className="policy-document-metadata">
                  <div>
                    <dt>Version</dt>
                    <dd>{document.version}</dd>
                  </div>
                  <div>
                    <dt>Effective</dt>
                    <dd>{displayEffectiveDate(document.effective_date)}</dd>
                  </div>
                </dl>
                <button
                  className="button button--overview-action button--with-icon"
                  type="button"
                  disabled={downloadingId !== null}
                  onClick={() => void download(document)}
                >
                  <AppIcon name="download" />
                  {downloadingId === document.document_id ? 'Downloading...' : 'Download PDF'}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="settings-empty">Loading policy documents...</p>
        )}

        <footer className="policy-library-note">
          <AppIcon name="lock" />
          <p>
            Downloaded copies are uncontrolled. Confirm the current approved local policy before
            live use.
          </p>
        </footer>
      </section>
    </section>
  )
}
