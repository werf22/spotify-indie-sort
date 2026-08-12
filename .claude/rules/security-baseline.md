# Security Baseline

Non-negotiable floor for anything exposed to users or the internet. Applies to every stack. Core: §5 (NEVER tier), §7. For launch gates see `rules/production-readiness.md`.

## 1. Inputs and outputs

- Treat ALL user input as hostile: form fields, URL params, headers, file uploads, webhook payloads, API bodies. Sanitize against XSS, SQL injection, and command injection — no exceptions for "internal" or "admin-only" inputs.
- Schema-validate at every boundary: API request in, API response out, queue messages, webhook payloads, env config at startup. Validation lives at the edge, not scattered through business logic. *Example:* a Zod-style schema per endpoint — reject and log anything that doesn't parse; never "clean up" malformed input silently.
- Use parameterized queries / prepared statements only. String-concatenated queries are a NEVER, even in one-off scripts.
- Never pass user input into shell commands. If unavoidable, use the platform's argument-array form, never string interpolation.
- Encode output for its context (HTML, attribute, URL, JS). Rendering user content as raw HTML requires an explicit, justified decision — default is escaped.
- File uploads: validate type and size server-side, randomize stored names, serve from a non-executing location or separate origin.

## 2. HTTP layer

- Rate-limit every public endpoint. Stricter limits on auth, signup, password reset, and anything that sends email/SMS or costs money per call.
- CORS: explicit allowlist of origins. Never `*` with credentials. No reflecting the request origin.
- Security headers on every response: CSP (start strict, loosen deliberately), HSTS, `X-Frame-Options: DENY` (or CSP frame-ancestors), `X-Content-Type-Options: nosniff`, a restrictive Referrer-Policy.
- Cookies: `HttpOnly` + `Secure` + `SameSite` (Lax minimum, Strict where flows allow). Session tokens never readable by client-side script.
- HTTPS only, everywhere, including staging. Redirect HTTP; never accept credentials over plain HTTP.

## 3. Data layer

- Row-level security or its equivalent (tenant scoping enforced in the data layer, not just in app code) on EVERY table holding user data. A missing tenant filter must fail closed, not leak rows.
- Least privilege everywhere: the app's DB user can't drop tables; API keys are scoped to the minimum capability; service-to-service credentials are per-service, not shared.
- Never expose internal IDs or trust client-supplied IDs without an ownership check — every "get by id" verifies the requester may see that row (IDOR is the classic vibe-coding leak).
- Encrypt sensitive data at rest where warranted: anything regulated, financial, health-related, or that would harm a user if dumped. Passwords are always hashed with a modern slow hash — never encrypted, never reversible.

## 4. Secrets

- Secrets live in env vars or a secret manager only. Never in code, never in git history, never in client-side bundles, never in logs or error messages.
- `.env.example` documents every required variable with a placeholder and a one-line comment — kept current as part of every task that adds a variable (core §7).
- Secret scanning runs on the repo (pre-commit hook and/or CI). A committed secret is compromised the moment it lands: rotate immediately, don't just delete the line.
- Rotate on suspicion, not on proof. Rotation must be cheap — if rotating a key is scary, that's a harness bug to fix.

## 5. Dependencies

- Update dependencies regularly; don't let the project drift years behind — old versions accumulate known CVEs.
- Vulnerability audit runs in CI (`npm audit`-style for the stack at hand, labeled per ecosystem). High/critical findings block the merge or get an explicit, documented exception.
- Adding a dependency is ASK-FIRST (core §5). Prefer well-maintained, widely-used packages; check last release date and open issues before adopting.

## 6. Admin surfaces

- Every admin route, dashboard, debug endpoint, and internal tool: always authenticated, always authorized (role check, not just login), always logged (who, what, when).
- No security through obscurity — an unlinked `/admin` URL is not protection. No "temporary" unauthenticated debug endpoints; they outlive their excuse.

## 7. Never log

PII, passwords, tokens, API keys, session IDs, or full user message content. Log identifiers (user ID, request ID) and metadata instead — detail in `rules/logging-observability.md`. This is NEVER-tier (core §5); enforce with a hook or log-scrubbing middleware where possible, not just intent.
