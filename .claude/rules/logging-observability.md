# Logging & Observability

We must ALWAYS know where an error happened and why. No silent failures, ever — a swallowed error is NEVER-tier (core §5, §7). When something breaks in production, the logs must answer "what happened, to whom, in which request" without reproducing the bug first.

## 1. What to log

**Backend:**
- Every API request: endpoint, method, status code, latency, request ID.
- Every external API call: target, operation, status, latency, retries. Third-party failures are the #1 source of "it works on my machine".
- Every DB error — full driver error in the log, generic message to the user.
- Every auth failure: failed login, invalid/expired token, permission denial (user ID + resource, never the credentials themselves).
- Startup and shutdown: config loaded (names, not values), migrations applied, port bound.

**Frontend:**
- Page/route loads and load failures.
- User action failures: a click or submit that should have worked and didn't.
- Network errors: failed fetches with endpoint and status.
- Render boundary errors (error-boundary equivalent in whatever the UI framework is) — caught, reported, and replaced with a fallback UI, never a blank screen.

**Business events:** the few events that define whether the product works — signup, purchase, core action completed, export generated. Log them as first-class events; they double as a sanity dashboard.

## 2. Format

- Structured JSON, one event per line: `{ timestamp, level, message, context }`. `context` carries request ID, user ID, and event-specific fields. Never bare `print`-style strings in production paths — structure is what makes logs searchable.
- Levels mean something: `error` = something failed and someone may need to act; `warn` = degraded or suspicious; `info` = normal milestones; `debug` = noisy detail, off in production by default.
- **Correlation IDs end to end:** generate a request ID at the edge, attach it to every log line, pass it to downstream services and external calls, return it in error responses so a user-reported error string finds the exact backend trace.

## 3. Error tracking

- All errors auto-report to an error tracker (*example:* Sentry-style service) with stack trace, request ID, user ID, release/version, and environment. Manual log-diving is the fallback, not the system.
- Unhandled exceptions and unhandled promise rejections are caught at the top level, reported, and logged — nothing escapes unrecorded.
- Group/alert on new error types and on error-rate spikes, not on every single event.

## 4. The fallback rule

Anything fails → three things happen, always, in this order:
1. **User sees a clear, human message** — what went wrong in their terms, what to try, never a stack trace or raw error code.
2. **Full error is logged** — stack, context, request ID, the works.
3. **App continues in degraded mode** — the failed feature is disabled or stubbed, everything else keeps working.

The app NEVER crashes outright, and it NEVER pretends a failure succeeded. `catch`-and-ignore blocks are forbidden; every catch either handles meaningfully or reports and degrades. *Example:* recommendation service down → show "recommendations unavailable", log the upstream error with request ID, render the rest of the page.

## 5. Do not log

PII (emails, names, addresses, phone numbers), API keys, passwords, tokens, session IDs, full user content (messages, documents, uploads). Log IDs and metadata: `userId: 123, messageLength: 482` — not the message. Scrub at the logger level (redaction middleware/serializer) so a careless call site can't leak. Same NEVER-tier rule as core §5 and `rules/security-baseline.md` §7.

## 6. Production

Uptime monitoring, alerting on error rates and downtime, and a basic dashboard (requests, errors, latency, key business events) are launch requirements for anything real users touch — full checklist in `rules/production-readiness.md` §16. Logging without anyone watching is write-only storage.
