# Production Readiness — the full-stack gate

On-demand gate, not always-loaded. Triggered from core §7 when building something real users will touch.
Walk it WITH the user, category by category. Classify each category: **NOW** (MVP blocker) / **LATER** (backlog) / **N/A** — always with a one-line reason.
Every NOW gap becomes a task in the project task file. Re-run the full list before launch.
Not every project needs all 35 categories — but skipping one must be a decision, never an accident.

## 1. Product & business

- [ ] Clear product goal and target users written down
- [ ] User stories / spec with acceptance criteria (core §2: spec-first)
- [ ] Explicit MVP vs nice-to-have split
- [ ] Roadmap with priorities
- [ ] Success metrics / KPIs defined — how do we know it's working?

## 2. Architecture

- [ ] Architecture style chosen deliberately: monolith / modular monolith / microservices
- [ ] One diagram: main components + main data flows
- [ ] Layer separation: UI / API / business logic / data access
- [ ] ADRs (architecture decision records) for significant choices
- [ ] Module dependency rules — what may import what
- [ ] System boundaries: what is inside vs external

## 3. Frontend

- [ ] Framework, routing, and state management chosen and consistent
- [ ] Forms with client-side validation (server still validates — §4)
- [ ] Every view has error, loading, and empty states
- [ ] Responsive on target devices
- [ ] Accessibility basics: keyboard, contrast, labels, focus
- [ ] SEO if public-facing; i18n if multi-language — else N/A with reason
- [ ] Design system / component conventions; asset management
- [ ] Frontend tests for critical flows
- [ ] Performance: bundle size, render cost, perceived speed

## 4. Backend

- [ ] Clear layers: API / business logic / data access
- [ ] Input validation on every entry point; consistent error handling
- [ ] Structured logging at critical paths (core §7)
- [ ] Authentication and authorization wired in (details §7, §8)
- [ ] Rate limiting on public endpoints
- [ ] Background jobs for slow work (details §22)
- [ ] External integrations isolated behind adapters
- [ ] Health check endpoint(s)
- [ ] API docs and a versioning approach

## 5. API design

- [ ] Clear, consistent endpoint naming
- [ ] Consistent status codes and one error response format everywhere
- [ ] Request/response schemas defined; payloads validated against them
- [ ] OpenAPI (or equivalent) docs generated, not hand-drifted
- [ ] Pagination, filtering, sorting on list endpoints
- [ ] Idempotency on critical operations (payments, orders, webhooks)
- [ ] Rate limits documented
- [ ] Versioning + backwards-compatibility strategy

## 6. Database

- [ ] Right DB type for the data — chosen, not defaulted
- [ ] Data model documented; normalization (or deliberate, justified denormalization)
- [ ] Indexes for real query patterns; constraints enforce integrity
- [ ] Migrations: versioned, repeatable, with rollback plan
- [ ] Seed data for local/dev
- [ ] Transactions where multi-step writes must be atomic
- [ ] Connection pooling configured
- [ ] Backups + tested restore process (details §28)
- [ ] Audit of sensitive changes; deletion/archival strategy

## 7. Authentication

- [ ] Register / login / logout flows complete
- [ ] Password reset + email verification
- [ ] Session or token management; refresh tokens if JWT
- [ ] Brute-force protection (lockout / throttling)
- [ ] MFA for sensitive systems — else N/A with reason
- [ ] OAuth / social login if needed
- [ ] Secure password storage (modern adaptive hash, never homemade)
- [ ] Secure cookies: HttpOnly, Secure, SameSite

## 8. Authorization

- [ ] Roles and permissions model defined
- [ ] Ownership checks: users only touch their own data
- [ ] Admin vs user split enforced
- [ ] ALL checks server-side — client checks are UX, not security
- [ ] IDOR protection: never trust an ID from the client
- [ ] Central policy system, not scattered if-statements
- [ ] Audit of permission changes
- [ ] Tests that verify permission boundaries

## 9. Security

- [ ] Input validation + output encoding everywhere
- [ ] XSS, CSRF, SQL-injection, command-injection protections in place
- [ ] Secure headers; CORS locked to known origins
- [ ] Rate limiting on auth and expensive endpoints
- [ ] Dependency scanning + secret scanning in CI
- [ ] SAST baseline; DAST for bigger systems
- [ ] Vulnerability management: who patches, how fast
- [ ] Audit logs for security-relevant events
- [ ] Least privilege everywhere; secure defaults; admin surface protected
- [ ] Regular dependency updates scheduled, not "someday"

## 10. Config & secrets

- [ ] Config separated from code; `.env.example` always current (core §7)
- [ ] No secrets in git — ever (core §5 NEVER tier)
- [ ] Secret manager for production
- [ ] Per-environment configs
- [ ] Secret rotation possible without a code deploy
- [ ] Feature flags for risky toggles
- [ ] Config validated at startup — fail fast on missing values

## 11. Environments

- [ ] Local, test, staging, production — each exists or is N/A with reason
- [ ] Each env has its own DB, secrets, and keys — zero sharing
- [ ] Each env has its own logging and monitoring
- [ ] Clear deploy rules: what goes where, when, approved by whom

## 12. Testing

- [ ] Unit tests for business logic
- [ ] Integration + API tests for contracts
- [ ] E2E tests for critical user flows
- [ ] Smoke test runnable after every deploy
- [ ] Regression coverage for fixed bugs
- [ ] Security and accessibility tests where relevant
- [ ] Performance tests if load matters — else N/A with reason
- [ ] Fixtures + test data management (no production data in tests)
- [ ] All of it runs in CI; coverage threshold where sensible, not as theater

## 13. CI/CD

- [ ] Pipeline: lint → typecheck → tests → build
- [ ] Dependency audit + secret scan in pipeline
- [ ] Artifact/image build reproducible
- [ ] Migration check before deploy
- [ ] Deploy to staging, then production — gated
- [ ] Rollback is one command/click
- [ ] Release notes + version tagging automated

## 14. Deployment

- [ ] Hosting, domains, DNS, SSL/TLS sorted
- [ ] CDN for static assets if public-facing
- [ ] Build artifacts versioned; runtime processes supervised
- [ ] Zero-downtime deploys if users are live — else N/A with reason
- [ ] Rollback strategy written down and tested
- [ ] Blue-green / canary for bigger systems
- [ ] Migrations run safely as part of deploy
- [ ] Health / readiness / liveness checks wired to the platform

## 15. Infrastructure

- [ ] Servers/cloud chosen; containerization (e.g. a Dockerfile) even if not orchestrated yet
- [ ] Orchestration, load balancer, reverse proxy as scale requires
- [ ] Object storage, managed DB, queue, cache — managed services where sane
- [ ] Networking: firewall, private networking for internal services
- [ ] Infrastructure as code — no click-ops as the source of truth
- [ ] **Zero vendor lock-in:** standard runtimes only; standard container tooling (e.g. Dockerfile + compose) for portability; generic `DATABASE_URL`-style connections — no proprietary SDK where a standard protocol works
- [ ] **Portability test:** "Can we export everything and run on any Linux server tomorrow?" Must be YES.

## 16. Observability

- [ ] Logs, metrics, traces — at least logs + metrics from day one
- [ ] Error tracking with alerting on new errors
- [ ] Uptime monitoring from outside the system
- [ ] Alerting routed to a human who will act
- [ ] Dashboards for the few numbers that matter
- [ ] Correlation IDs across services/requests
- [ ] Audit logs; performance and user-impact monitoring

## 17. Logging

- [ ] Structured (JSON or equivalent), with levels
- [ ] Every line: request ID, service name, environment, timestamp
- [ ] Stack traces on errors; business events logged at key points
- [ ] Sensitive-data masking — NEVER log passwords, tokens, cards, keys, or PII without explicit reason (core §5)
- [ ] Centralized and searchable, not scattered across machines

## 18. Error handling

- [ ] Global error handler — nothing escapes unformatted
- [ ] One consistent error response format; correct status codes
- [ ] User-friendly message + internal error code separation
- [ ] Retries and fallbacks where transient failure is expected
- [ ] Errors are LOUD: user sees a clear message, full detail is logged, app degrades instead of crashing (core §7)
- [ ] Error tracking captures every unexpected exception

## 19. Performance

- [ ] Load speed and API latency targets defined and measured
- [ ] DB indexes match real queries; slow-query review
- [ ] Caching where measured, not guessed (core §7: optimize when measured)
- [ ] Lazy loading + pagination — never "fetch all"
- [ ] Compression, CDN, image optimization, bundle size
- [ ] Load testing before launch if traffic is expected
- [ ] Memory/CPU profiles known; cold starts if serverless

## 20. Scalability

- [ ] Stateless backend — state lives in DB/cache, so horizontal scaling works
- [ ] Queue-based processing for spiky/slow work
- [ ] Cache invalidation strategy explicit
- [ ] Read replicas if read-heavy — else N/A
- [ ] Sharding ONLY if truly needed — default answer is no
- [ ] Workers scale independently of web
- [ ] Rate limits + graceful degradation under load
- [ ] Capacity planning: rough numbers for 10x current load

## 21. Resilience

- [ ] Retries with backoff on all external calls
- [ ] Timeouts on everything — no infinite waits
- [ ] Circuit breakers for flaky dependencies (bigger systems)
- [ ] Graceful shutdown: finish in-flight work, then exit
- [ ] Idempotent operations — safe to repeat
- [ ] Dead-letter queues for poison messages
- [ ] Fallbacks + overload protection + backpressure
- [ ] Recovery processes written down, not tribal knowledge

## 22. Background jobs & queues

- [ ] Queue system + workers for anything slow or external
- [ ] Retry policy with backoff; DLQ for permanent failures
- [ ] Job status tracking visible somewhere
- [ ] Jobs idempotent — duplicate delivery is harmless
- [ ] Job monitoring + alerting on backlog growth
- [ ] Cron/scheduled jobs with duplicate-run protection
- [ ] Typical candidates checked: emails, invoices, exports/imports, image processing, notifications, external-API syncs

## 23. File storage

- [ ] Object storage, not local disk
- [ ] Upload limits + file-type validation server-side
- [ ] Malware scanning for risky upload sources
- [ ] Signed URLs for private files; explicit private/public policy
- [ ] Image processing pipeline if images matter
- [ ] CDN in front of public files
- [ ] Retention policy + backups for stored files

## 24. Email & notifications

- [ ] Transactional email service (never raw SMTP from the app box)
- [ ] Templates managed in one place
- [ ] Unsubscribe for anything marketing-flavored
- [ ] Bounce handling + retry + delivery tracking
- [ ] SPF / DKIM / DMARC configured on the sending domain
- [ ] In-app / push / SMS channels as the product needs — else N/A

## 25. Admin interface

- [ ] User + role management
- [ ] Entity overviews for support: find any record fast
- [ ] Manual data-fix tools that go through business logic, not raw SQL
- [ ] Impersonation — only if needed, heavily secured and logged
- [ ] Exports; moderation tools if UGC
- [ ] Feature flag toggles
- [ ] EVERY admin action audited

## 26. Analytics

- [ ] Traffic + activation + retention measured
- [ ] Funnels for the core conversion path
- [ ] Error rate and performance visible alongside business metrics
- [ ] Business metrics tied to the KPIs from §1
- [ ] Feature usage — know what nobody uses

## 27. Privacy & compliance

- [ ] GDPR posture decided (applies to almost anything with EU users)
- [ ] Cookie consent if tracking; privacy policy + ToS published
- [ ] DPAs with processors handling personal data
- [ ] Personal-data export + account deletion + right to be forgotten
- [ ] Retention limits + data minimization — collect less
- [ ] Sensitive data encrypted at rest
- [ ] Access to personal data audited; consent logged

## 28. Backups & disaster recovery

- [ ] Automated DB backups
- [ ] Restore TESTED regularly — an untested backup is a hope, not a backup
- [ ] RPO defined (max acceptable data loss) and RTO defined (max acceptable downtime)
- [ ] Offsite/cross-region backup copies
- [ ] File/object storage backed up too
- [ ] Restore runbook + DR plan written
- [ ] Accidental-deletion protection (soft delete / delayed purge)
- [ ] Every migration has a rollback plan

## 29. Documentation

- [ ] README + setup guide that actually works from scratch
- [ ] Architecture overview + API docs
- [ ] Env vars documented; deploy guide; testing guide
- [ ] Troubleshooting + runbooks + incident response steps
- [ ] Onboarding path for a new contributor
- [ ] Changelog maintained

## 30. Developer experience

- [ ] One-command local setup (core §4: zero-setup)
- [ ] Seed data so local isn't empty
- [ ] Compose-style local environment for dependencies
- [ ] Lint / format / typecheck + pre-commit hooks
- [ ] Hot reload; clear folder structure; consistent naming
- [ ] Editor config committed; repetitive chores scripted

## 31. Code quality

- [ ] Style enforced by linter + formatter, not by debate
- [ ] Types where the language offers them
- [ ] Reviews (or critic-pass per core §2) on every change
- [ ] Static analysis + dependency rules in CI
- [ ] Modular: no god-files (core §7: split before ~250 lines)
- [ ] No hardcoded secrets; sane abstractions, not premature ones
- [ ] Complex parts documented WHY + HOW TO TWEAK (core §7)
- [ ] Refactoring is a scheduled process, not an emergency

## 32. Release management

- [ ] Versioning scheme; release notes + changelog
- [ ] Deploy checklist + rollback checklist
- [ ] Feature flags decouple deploy from release
- [ ] Migration strategy keeps old and new code compatible during rollout
- [ ] Staged rollout for risky changes
- [ ] Post-release monitoring window with an owner
- [ ] Hotfix process defined before it's needed

## 33. Incident management

- [ ] Alerts reach a named responsible person
- [ ] Severity levels defined (what's a page vs a ticket)
- [ ] Runbook per known failure mode
- [ ] Comms channel for incidents; status page for bigger products
- [ ] Postmortems — blameless, with action items that get done
- [ ] Incident history kept and reviewed

## 34. Cost management

- [ ] Cloud, DB, storage, bandwidth, external-API, and email costs known
- [ ] Cost monitoring + budget alerts before the surprise invoice
- [ ] Cost per customer and cost per request roughly known
- [ ] The expensive line items have an owner and a plan

## 35. Legal & business

- [ ] ToS + privacy policy + cookie policy published
- [ ] SLA for B2B customers — else N/A
- [ ] DPA template when processing client data
- [ ] OSS licenses of dependencies checked for compatibility
- [ ] Copyright and UGC rules clear
- [ ] Refund policy defined if charging money
