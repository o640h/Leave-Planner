# Workspace Membership Administration

## Operator outcome

**Settings > Workspace** is the workspace-scoped administration surface. It lists every active
Owner/Admin membership and any closed workspace still inside its recovery period. Selecting a row
opens management details; it does not switch the planner's active workspace. **Create Workspace**
remains a separate action in the page header.

An Owner can rename the workspace, invite Admins or linked Members, resend or revoke invitations,
change Admin/Member roles, link a Member to an active consultant, remove people, request ownership
transfer, and review workspace-level changes. An Admin can invite, relink, and remove Members only.
The database's one-Owner constraint remains in force, so ownership changes only after the selected
Admin explicitly accepts the pending transfer.

## Invitation flow

An invitation stores the canonical destination email, workspace, role, optional same-workspace
consultant link, inviter, seven-day expiry, and lifecycle state. Its email action stores only the hash
of a random token. Resending revokes the previous token; accepting consumes it. A signed-in account
whose canonical email differs from the invitation is rejected.

An existing account signs in and accepts the link. A new person can follow the link into account
creation even when general registration is Invitation Only. Registration consumes and claims the
invitation token, but does not grant membership. The membership is created only when the separate
email-verification token activates that account. Open registration still never grants access to an
existing workspace without this invitation path.

Delivery is deliberately outside the transaction that creates or refreshes the invitation. A mail
failure is recorded but does not erase the authoritative pending invitation, so an authorised
operator can resend it.

## Authorization and session effects

Every management request first discovers the caller's membership under the account-scoped
PostgreSQL context, checks the workspace state and role, then binds the target workspace before
reading or writing tenant rows. Invitation, ownership-transfer, and workspace-event tables use the
same workspace row-level-security boundary and indexed workspace foreign keys as the existing
tenant roots.

Removing a person deletes only that workspace membership. Any session currently selecting that
workspace has its active selection cleared, as does the account's remembered selection. The session
itself remains valid, so access to other workspaces is unaffected. A closed workspace is excluded
from normal workspace context resolution even if a stale client retains its former identifier.

## Workspace lifecycle

The impact endpoint distinguishes a genuine empty setup mistake from a workspace with operational
or consultant audit history:

- an empty workspace can be deleted after the Owner types its exact name; pending invitations and
  workspace-administration events cascade with that setup mistake;
- a workspace with consultant, Trust-correction, or consultant audit history cannot use the delete
  path; the Owner must confirm the current password, review impact, and type the exact name before
  closure;
- closure revokes pending invitations, cancels a pending ownership transfer, clears every active
  session selection, and sets a 30-day recovery deadline;
- the same Owner can recover before that deadline after confirming the current password; and
- permanent post-retention purge has no ordinary HTTP or interface control. After a verified backup,
  the server owner may run the separately authorised command below; it refuses an active workspace,
  an unexpired recovery period, or either missing typed confirmation.

```powershell
Set-Location "C:\Projects\Leave Planner\backend"
$env:PYTHONPATH = (Resolve-Path "src").Path
..\.venv\Scripts\python.exe -m workspaces.workspace_admin purge-closed WORKSPACE_ID
```

## Calculation boundary

This slice does not call or alter the leave calculation engine. Consultant presence is used only to
link Member visibility and decide whether deletion would destroy operational history. Entitlement,
job-plan, holiday, booking, deduction, ledger, and balance behaviour is unchanged.
