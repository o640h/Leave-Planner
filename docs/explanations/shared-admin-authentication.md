# Shared Admin Authentication

This document records the Phase 6 authentication boundary that was superseded on 15 September 2026.

The password-only `Admin` identity and its server administration module have been removed. The
operator approved a clean account database rather than assigning an email address to that shared
identity or carrying its workspace into Phase 7. Migration `0015` refuses to discard consultant,
Trust-correction, or audit data, so an occupied legacy database must be handled explicitly.

The current email identity and session design is documented in
[`email-identity-authentication.md`](email-identity-authentication.md). The Argon2id hashing,
server-side hashed sessions, CSRF checks, same-origin validation, secure cookie settings, expiry, and
revocation controls established in Phase 6 remain in use.
