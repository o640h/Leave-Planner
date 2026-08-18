import { useState } from 'react'
import type { SubmitEvent } from 'react'

import type { ConsultantInput } from './types'

type ConsultantFormProps = {
  initialValue: ConsultantInput
  mode: 'create' | 'edit'
  busy: boolean
  onSubmit: (details: ConsultantInput) => Promise<void>
  onCancel: () => void
}

export function ConsultantForm({
  initialValue,
  mode,
  busy,
  onSubmit,
  onCancel,
}: ConsultantFormProps) {
  const [details, setDetails] = useState<ConsultantInput>(initialValue)
  const [nameError, setNameError] = useState<string | null>(null)

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = details.name.trim()

    if (!name) {
      setNameError('Enter a consultant name.')
      return
    }

    await onSubmit({
      name,
      post_title: details.post_title?.trim() || null,
    })
  }

  function handleCancel() {
    setDetails(initialValue)
    onCancel()
  }

  return (
    <form className="consultant-form" noValidate onSubmit={handleSubmit}>
      <div className="form-introduction">
        <span className="section-label">
          {mode === 'create' ? 'New Record' : 'Selected Record'}
        </span>
        <h3 id="consultant-form-title">
          {mode === 'create' ? 'Add Consultant' : 'Edit Consultant'}
        </h3>
        <p>
          These are the identifying fields currently entered at the top of each annual leave
          workbook.
        </p>
      </div>

      <div className="form-fields">
        <div className="field">
          <label htmlFor="consultant-name">Consultant Name</label>
          <input
            id="consultant-name"
            name="name"
            value={details.name}
            maxLength={200}
            aria-required="true"
            aria-invalid={nameError ? 'true' : undefined}
            aria-describedby={nameError ? 'consultant-name-error' : undefined}
            autoComplete="off"
            disabled={busy}
            onChange={(event) => {
              setNameError(null)
              setDetails((current) => ({
                ...current,
                name: event.target.value,
              }))
            }}
          />
          {nameError ? (
            <small id="consultant-name-error" className="field-error" role="alert">
              {nameError}
            </small>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="post-title">Post Title (Optional)</label>
          <input
            id="post-title"
            name="post_title"
            value={details.post_title ?? ''}
            maxLength={200}
            autoComplete="off"
            disabled={busy}
            onChange={(event) =>
              setDetails((current) => ({
                ...current,
                post_title: event.target.value,
              }))
            }
          />
        </div>
      </div>

      <div className="form-actions">
        <button
          className="button button--quiet"
          type="button"
          disabled={busy}
          onClick={handleCancel}
        >
          Cancel
        </button>

        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? 'Saving...' : mode === 'create' ? 'Create Consultant' : 'Save Changes'}
        </button>
      </div>
    </form>
  )
}
