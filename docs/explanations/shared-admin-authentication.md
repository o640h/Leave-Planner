# Shared Admin Authentication

This document records the legacy shared authentication boundary that was superseded on 15 September 2026.

The password-only `Admin` identity and its server administration module have been removed. The
operator approved a clean account database rather than assigning an email address to that shared
identity or carrying its workspace into the named-account system. Migration `0015` refuses to discard consultant,
Trust-correction, or audit data, so an occupied legacy database must be handled explicitly.

The current email identity and session design is documented in
[`email-identity-authentication.md`](email-identity-authentication.md). The Argon2id hashing,
server-side hashed sessions, CSRF checks, same-origin validation, secure cookie settings, expiry, and
revocation controls established by that earlier boundary remain in use.
