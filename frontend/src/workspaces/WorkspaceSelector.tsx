import { useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import type { WorkspaceContext } from '../authentication/types'
import { selectWorkspace } from './api'

type WorkspaceSelectorProps = {
  context: WorkspaceContext
  required?: boolean
  onSelected: (context: WorkspaceContext) => void
}

const roleLabels = { owner: 'Owner', admin: 'Admin', member: 'Member' } as const

export function WorkspaceSelector({
  context,
  required = false,
  onSelected,
}: WorkspaceSelectorProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function choose(workspaceId: number) {
    if (workspaceId === context.active_workspace_id || busy) return
    setBusy(true)
    setError(null)
    try {
      onSelected(await selectWorkspace(workspaceId))
    } catch (selectionError) {
      setError(operatorErrorMessage(selectionError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={required ? 'workspace-choice' : 'workspace-selector'}>
      <label htmlFor={required ? 'required-workspace' : 'active-workspace'}>
        {required ? 'Choose Workspace' : 'Workspace'}
      </label>
      <select
        id={required ? 'required-workspace' : 'active-workspace'}
        value={context.active_workspace_id ?? ''}
        disabled={busy}
        onChange={(event) => void choose(Number(event.target.value))}
      >
        {required ? <option value="">Select a workspace</option> : null}
        {context.memberships.map((membership) => (
          <option key={membership.workspace_id} value={membership.workspace_id}>
            {membership.workspace_name} · {roleLabels[membership.role]}
          </option>
        ))}
      </select>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}
