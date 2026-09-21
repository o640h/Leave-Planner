# Internet-Facing Session Hardening

## Security boundary

Leave Planner keeps verified-email and Argon2id password authentication. It does not add TOTP,
MFA recovery codes, or a second general-purpose recovery credential. Password recovery continues to
require a short-lived, single-use link delivered to the verified mailbox; the deployment operator's
audited server-side recovery command remains the exceptional recovery route.

Production is configured for Cloudflare Tunnel. In that mode the application accepts
`CF-Connecting-IP` only on non-loopback connections reaching the application through its private edge
network. A missing or malformed address fails closed. Development and direct access ignore forwarded
address headers and use the actual peer, so callers cannot rotate a header to evade local limits.
The health endpoint remains available to the container's loopback health check.

## Abuse controls

HTTP request, login, and unauthenticated account-action counters use bounded, thread-safe sliding
windows. Authenticated workspace creation, invitations, Member requests, and Owner/Admin request
decisions also have per-account action buckets. This prevents one abusive account from consuming the
allowance belonging to unrelated users while the outer client limit still constrains unauthenticated
traffic.

The live workspace channel retains exact-origin enforcement, a 512-byte message ceiling, strict
schemas, normalised coordinates, and an allow-list of supported views and event types. It additionally
limits connection attempts per client, simultaneous sockets per account, and messages per socket.
The message ceiling is deliberately above the UI's 20 Hz coalesced pointer rate. A rate-limited browser
waits for the window to clear instead of creating an aggressive reconnect loop. Counters retain at
most the configured number of keys, preventing attacker-generated identities from growing process
memory without bound.

Security rejection logs contain only an event name and reason category. They do not contain tokens,
email addresses, message bodies, pointer coordinates, or consultant data.

## Live-session revocation

A socket authenticates its server-side session and selected workspace membership before acceptance.
Every open connection is associated with the exact session record, not merely an account or browser.
The server repeats the session, account-state, selected-workspace, and membership checks every 30
seconds, including while the socket is idle.

Logout and workspace switching close the exact session's socket immediately after the database commit.
Password reset and confirmed email change close every socket for that account. Password change also
forces existing live connections to reconnect, while the deliberately retained current HTTP session
can authenticate the replacement socket. Membership and workspace lifecycle changes continue to
publish a post-commit workspace-context invalidation and close affected live connections. Periodic
validation is the backstop for server-side account disablement and any missed process-local event.

## Recovery evidence

The PostgreSQL backup role still reads the complete database through RLS, and verification restores
each dump into a new disposable database. The verification now fails unless the restored schema
contains users, server-side sessions, one-time account-action tokens, and workspace memberships. It
also fails when the core workspace, membership, or consultant tables have lost row-level security,
and records protected-table row counts in the verification report.

This proves the archive contains the authority needed to preserve account and workspace access after
recovery. It does not make same-NAS storage an off-device backup: whole-NAS loss remains an accepted,
documented residual risk for this phase.
