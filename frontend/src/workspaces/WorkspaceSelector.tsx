import { useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import type { WorkspaceContext } from '../authentication/types'
import { SelectMenu } from '../system/SelectMenu'
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
      <SelectMenu
        id={required ? 'required-workspace' : 'active-workspace'}
        value={context.active_workspace_id?.toString() ?? ''}
        disabled={busy}
        placeholder="Select a workspace"
        options={context.memberships.map((membership) => ({
          value: membership.workspace_id.toString(),
          label: membership.workspace_name,
          detail: roleLabels[membership.role],
        }))}
        onChange={(workspaceId) => void choose(Number(workspaceId))}
      />
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}
