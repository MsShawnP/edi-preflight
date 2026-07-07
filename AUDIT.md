# edi-preflight — Project Audit

Audited: 2026-05-16 (fresh audit, prospect review imminent)

---

## Phase 1: Baseline Assessment

**Date:** 2026-05-16
**Project:** edi-preflight
**Repo:** github.com/MsShawnP/edi-preflight
**Live:** edi.lailarallc.com

### What Was Intended

A free, ungated web tool for $15M–$30M specialty food brands doing EDI
by hand. Two modes: inbound 850 parser (CSV/PDF export) and outbound
856 validator (severity tags, chargeback-dollar attribution). Five
retailers. Purpose: lead-gen for a $15K–$25K EDI Health Audit
engagement offered by Lailara LLC.

### What Exists Today

The tool is complete and deployed. Both modes work end-to-end for all
five retailers. All originally planned features are shipped. A prior
audit (2026-05-15) identified gaps in hardening, product completion,
and code quality — all recommendations have been implemented.

| Capability | Status |
|---|---|
| Inbound 850 parsing (5 retailers) | Shipped |
| Outbound 856 validation (5 retailers, 3-layer) | Shipped |
| CSV export (850) | Shipped |
| PDF export (850 + 856) | Shipped |
| Chargeback-dollar attribution | Shipped |
| Input validation with diagnostics | Shipped |
| Security headers (CSP, nosniff, DENY) | Shipped |
| Input size limits (2MB) | Shipped |
| Self-hosted HTMX | Shipped |
| Non-root Docker | Shipped |
| Lead-gen CTA | Shipped |
| "Try a sample" buttons | Shipped |
| SEO meta tags + OG | Shipped |
| Responsive CSS | Shipped |
| Analytics script | Shipped (unconfigured — see Gap 1) |
| CI pipeline | Shipped |
| Deployed to Fly.io | Shipped |

### Tech Stack

- **Language:** Python 3.13
- **Framework:** FastAPI + Jinja2 templates
- **Frontend:** HTMX (self-hosted), vanilla CSS, vanilla JS
- **PDF:** ReportLab
- **Parser:** Custom X12 tokenizer (no external EDI library)
- **Hosting:** Fly.io (shared-cpu-1x, 256 MB, SEA region)
- **CI:** GitHub Actions (pytest on push/PR)

### Project Health Indicators

- **Activity:** Active — last commit 2026-05-15, built in 4 days
- **Documentation:** Good — README, CLAUDE.md, DECISIONS.md, HANDOFF.md all current
- **Test coverage:** High — 297 tests, 1:1 source/test line ratio, 3.7s runtime
- **Dependencies:** Current — 5 runtime deps, all recent versions
- **Code quality:** Clean — modular architecture, consistent patterns, no dead code
- **Security:** Hardened — CSP, input limits, non-root Docker, sanitized filenames

### Gap Analysis

The engineering is solid. The issues are presentation and
configuration — things a prospect would notice on review.

**Gap 1 — Google Analytics is unconfigured.** `base.html:16` loads
`gtag/js?id=GA_MEASUREMENT_ID` with a literal placeholder. The HTML
comment says "replace GA_MEASUREMENT_ID with your actual ID." This is
visible in page source. A technical prospect viewing source would see
unfinished setup. More importantly, the tool can't answer its business
question without working analytics.

**Gap 2 — CTA links to personal email.** The lead-gen CTA in the
results templates and footer both link to `mailto:msshawnp@gmail.com`.
For a prospect evaluating this as a professional credential, a Gmail
address undercuts the positioning. Should link to a professional
landing page, booking tool (Calendly/Cal.com), or at minimum a
business domain email.

**Gap 3 — No CI badge in README.** PLAN.md task 9.8 says "Badge in
README" but the README has no badge. Minor, but a prospect reviewing
the repo would expect to see build status.

**Gap 4 — Copyright/attribution is personal, not branded.** Footer
says "Built by Shawn P." README says "A Lailara LLC portfolio piece."
The brand identity is inconsistent — sometimes personal, sometimes
company. For a prospect, the company attribution is stronger.

**Gap 5 — CSP allows Google Analytics but GA isn't configured.** The
Content-Security-Policy header permits `googletagmanager.com` and
`google-analytics.com`, which is correct if GA is configured. But
since the measurement ID is a placeholder, the CSP is permitting
third-party scripts that serve no purpose. Either configure GA or
remove the CSP exceptions and script tags until you do.

**Gap 6 — No custom domain.** The tool lives at `edi.lailarallc.com`.
The README and OG tags reference this URL. A `.com` or branded
subdomain would be stronger for prospect presentation, but this was
explicitly marked out of scope.

### What's Strong (prospect-visible)

- The tool works. Both modes produce useful, accurate output.
- "Try a sample" removes friction — prospect can see results
  immediately without having their own EDI file.
- Chargeback-dollar attribution is a genuine differentiator nobody
  else offers for free.
- Code is clean, well-organized, and well-tested — repo review will
  reflect positively.
- README is clear, professional, and accurate.
- The stateless privacy story is good.

### Audit Motivation

Prospect client will be reviewing (live tool, codebase, or both) soon.
This audit produces: (1) confidence check that the project is
presentable, and (2) a punch list of specific fixes before the
prospect sees it.

---

## Phase 2: Internal Review

**Date:** 2026-05-16
**Dimensions reviewed:** Code quality, Architecture, Tests, Documentation, Performance, Security, UX, DevEx

### Top Opportunities (by leverage)

| # | Finding | Dimension | Impact | Effort | Leverage | Severity |
|---|---------|-----------|--------|--------|----------|----------|
| 1 | CI is failing — red badge on public repo | DevEx | 5 | 1 | 5.0 | Critical |
| 2 | GA placeholder literal in HTML source and ga.js | Security/UX | 4 | 1 | 4.0 | Important |
| 3 | CTA links to personal Gmail, not professional contact | UX | 4 | 1 | 4.0 | Important |
| 4 | No CI badge in README | Documentation | 3 | 1 | 3.0 | Minor |
| 5 | Footer attribution inconsistent (personal vs company) | UX | 3 | 1 | 3.0 | Minor |
| 6 | CSP permits unused GA domains | Security | 2 | 1 | 2.0 | Minor |
| 7 | Tab buttons lack ARIA roles | UX | 2 | 1 | 2.0 | Minor |
| 8 | `style-src 'unsafe-inline'` in CSP | Security | 1 | 2 | 0.5 | Minor |

### Detailed Findings

#### DevEx

**[Critical] CI is failing on main.** All three recent CI runs (May 15)
show failure. Cause: `test_main.py` imports `fastapi.testclient.TestClient`
which requires `httpx`, but `httpx` is not listed in
`pyproject.toml [project.optional-dependencies].dev`. Tests pass locally
because `httpx` is installed transitively, but the CI fresh install
only gets `pytest`.

- File: `pyproject.toml:15-17`
- Fix: Add `"httpx>=0.24"` to `[project.optional-dependencies].dev`

A prospect viewing the GitHub repo will see a red ❌ next to commits.
This is the single highest-priority fix.

**[Minor] No linting/formatting tooling.** No ruff, black, or mypy
configured. For a solo-dev portfolio piece this is acceptable, but if
the prospect expects production-grade DevEx, it's a gap. Low priority.

#### Security

**[Important] GA placeholder visible.** `base.html:16` loads a real
Google script with a literal `GA_MEASUREMENT_ID` string. `ga.js:4`
configures gtag with the same placeholder. A technical reviewer
inspecting page source will see unfinished setup. The HTML comment on
line 15 ("replace GA_MEASUREMENT_ID with your actual ID") confirms it.

**[Minor] CSP permits unused third-party domains.** The CSP allows
`googletagmanager.com`, `google-analytics.com`, and
`analytics.google.com` — but since GA isn't configured, these
permissions serve no purpose and slightly expand the attack surface.

**[Minor] `style-src 'unsafe-inline'`.** Required because some
elements may have inline styles. Not exploitable in this context but
noted for completeness.

**[Positive]** No XSS vectors found. Jinja2 auto-escaping is active
(no `| safe` filter usage). Input sanitization is solid. File handling
has proper size limits. Docker runs non-root. Filenames are sanitized.
Exception messages don't leak internals.

#### Code Quality

**[Positive] Clean, consistent, readable.** Modules follow a clear
naming pattern (`validate_856_<retailer>.py`). Dataclasses are
well-structured. Helper functions are appropriately scoped. No dead
code, no TODOs, no orphaned imports. The `RetailerConfig` pattern is
elegant — adding a new retailer is ~30 lines.

**[Positive] No duplication.** The previous audit found 284 lines of
Walmart duplication; this was resolved (now 34 lines). Formatting
utilities are centralized. Validation pipeline has a shared helper.

**[Positive] No unnecessary abstractions.** The codebase is
appropriately minimal — no framework indirection, no over-engineering.
A reviewer can trace any feature from endpoint to output in one pass.

#### Architecture

**[Positive] Clean pipeline.** `x12_tokenizer → envelope →
extract_850/validate_856 → export → templates`. Each layer has a
single responsibility. No circular dependencies. No global state.

**[Positive] Stateless by design.** No database, no sessions, no
file storage. Documents processed in memory and discarded. This is the
right architecture for a diagnostic tool handling potentially
sensitive EDI data.

**[Positive] Extensible where it matters.** Adding a new retailer
requires: one ~30-line validator module, one fee dict, one line in
`_RETAILER_VALIDATORS` in `main.py`. Adding a new document type
(e.g., 810 Invoice) would require a new extraction module but no
changes to the web layer pattern.

#### Tests

**[Positive] High coverage, fast execution.** 297 tests across 19
modules. 3.7s runtime. Tests cover tokenization, envelope parsing,
extraction (all 5 retailers), validation (structural + field + all 5
retailer-specific), CSV/PDF export, input validation, HTTP endpoints,
and security headers.

**[Positive] Good test structure.** Tests are grouped by behavior,
use descriptive class names, and test inputs/outputs rather than
implementation details.

**[Minor note] PDF tests are smoke-level.** They verify ReportLab
doesn't crash and output is non-trivial in size, but don't verify
rendered content (this is acceptable given ReportLab's compression).

#### Documentation

**[Positive] README is accurate and professional.** Clear description,
tech stack, repo structure, local run instructions, test command.
Matches current state of the project.

**[Important] No CI badge.** PLAN.md task 9.8 specified "Badge in
README" but it was never added. With CI fixed, adding the badge would
show green ✓ to prospects.

**[Positive] GitHub repo description is good.** Accurately describes
the tool and supported retailers.

#### Performance

**[Positive] Appropriate for scale.** Single-pass parsing, no
database, no external calls. 2MB input limit protects the 256MB VM.
Sync endpoints prevent event-loop blocking. For a diagnostic tool
processing one document at a time, there are no bottlenecks.

**[Minor note] Auto-stop machines.** `fly.toml` has
`auto_stop_machines = "stop"` and `min_machines_running = 0`. This
means the first request after inactivity has a cold-start delay
(~2-5s). For a prospect's first impression, this could feel slow.
Not a code issue — a hosting config tradeoff (cost vs. latency).

#### UX

**[Important] CTA uses personal Gmail.** Both results templates and
the footer link to `mailto:msshawnp@gmail.com`. For a tool
positioning the author as a professional EDI consultant, this
undercuts credibility. A Calendly link, business email, or landing
page would be stronger.

**[Minor] Tab buttons lack ARIA labels.** `<button class="mode-tab">`
has no `role="tab"`, no `aria-selected`, no `aria-controls`. Screen
readers won't announce tab behavior. Low priority for the target
audience but noted.

**[Minor] No skip-to-content link.** Standard accessibility pattern
missing. Low priority.

**[Positive] Error messages are clear and actionable.** Format-specific
diagnostics ("This looks like JSON, not EDI"), size limit messaging,
transaction type guards, all with helpful hints.

**[Positive] "Try a sample" is excellent UX.** Eliminates the
blank-page problem. A prospect can see results in one click.

**[Positive] Mobile responsive.** Breakpoints at 768px and 480px.
Tables scroll horizontally. Forms stack vertically.

### Summary

The codebase is solid — clean architecture, high test coverage, good
security posture, and professional documentation. The issues are all
in the "last mile" presentation layer: CI is broken (missing dev
dependency), GA is visibly unconfigured, and the CTA points to a
personal email. These are 10-minute fixes that would meaningfully
improve the prospect's impression. The code itself would hold up well
under technical review.

---

## Phase 3: Landscape Scan

**Date:** 2026-05-16
**Category:** Free/ungated EDI diagnostic tools for SMB specialty food brands
**Source:** Prior landscape scan (2026-05-15), confirmed still valid

### Competitors / Similar Projects

| # | Name | Type | Price | Key Differentiator |
|---|------|------|-------|-------------------|
| 1 | Stedi EDI Inspector | Web viewer | Free | Interactive segment tree, JSON translation, polished UI |
| 2 | EdiNation / EdiFabric | API + portal | Freemium | Base X12 spec validation, API-first |
| 3 | Orderful | EDI platform | $189/mo/TP | Free validator as lead-gen funnel → platform upsell |
| 4 | Crstl | AI EDI platform | Custom quote | Food-focused (UNFI, KeHE, Walmart), Series A with Shopify Ventures |
| 5 | SPS Commerce | EDI platform | ~$750/mo | Acquired SupplyPike ($206M) for chargeback prevention |
| 6 | TrueCommerce | EDI platform | ~$500/mo | Full-stack EDI with compliance |
| 7 | WebEDI / Edict | Forms-based | Subscription | Grocery-focused forms entry |
| 8 | pyx12 | Python library | Open source | HIPAA X12 only |
| 9 | Bots-EDI | Self-hosted | Open source | General EDI translator |

### Feature Matrix

| Feature | EDI Preflight | Stedi | EdiNation | Orderful | Crstl | SPS |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|
| Free / ungated | ✅ | ✅ | 🟡 | 🟡 | ❌ | ❌ |
| 850 PO parsing | ✅ | 🟡 view only | 🟡 parse only | ✅ | ✅ | ✅ |
| 856 ASN validation | ✅ | 🟡 base spec | 🟡 base spec | ✅ | ✅ | ✅ |
| Retailer-specific rules | ✅ 5 retailers | ❌ | ❌ | ✅ | ✅ 3 retailers | ✅ |
| Chargeback $ attribution | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ via SupplyPike |
| CSV/PDF export | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| No login required | ✅ | ✅ | ❌ | 🟡 | ❌ | ❌ |
| Stateless / no storage | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| "Try a sample" UX | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| EDI transmission (AS2/SFTP) | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Ongoing monitoring | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Auto-dispute chargebacks | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Interactive segment tree | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| All X12 transaction types | ❌ | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Food-brand messaging | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |

### Landscape Position

#### Table Stakes (standard in category)

- Parse/view X12 documents — ✅ covered
- Some form of validation — ✅ covered (3 layers, actually)
- Web-based access — ✅ covered

Nothing standard is missing.

#### Where This Project Is Stronger

- **Chargeback-dollar attribution** — Only free tool that attaches
  actual dollar estimates. SPS has this via SupplyPike ($206M
  acquisition) but that's a $750+/mo enterprise product.
- **Retailer-specific 856 validation** — Stedi and EdiNation validate
  against the generic X12 spec. EDI Preflight validates against
  retailer implementation guides (HL loop order, SSCC-18 format, OTIF
  timing, catch-weight requirements).
- **Ungated two-mode coverage** — Both inbound parsing and outbound
  validation in one free tool. Most tools do one or the other, and
  most that do both require accounts.
- **Food-brand specificity** — Retailer coverage (UNFI, KeHE alongside
  Walmart/Amazon/Costco) and chargeback amounts speak directly to the
  $15M–$30M specialty food segment.
- **"Try a sample" UX** — No competitor offers this. First-mover
  advantage for reducing friction.

#### Where This Project Is Weaker

- **UI polish** — Stedi's interface is significantly more polished
  (interactive segment trees, JSON translation, smooth animations).
  EDI Preflight is functional but plain.
- **Breadth** — Stedi supports all X12 and EDIFACT transaction types.
  EDI Preflight supports only 850 and 856.
- **Connectivity** — Not an EDI transmission platform. The paid
  competitors handle sending/receiving. Preflight is diagnostic-only.
- **Ongoing monitoring** — No continuous compliance checking. SupplyPike
  monitors and auto-disputes chargebacks.

#### Unique Differentiators

**Only this project has all of:**
1. Free + ungated (no login, no trial limit)
2. Retailer-specific validation (not just generic X12 spec)
3. Chargeback-dollar estimates on findings
4. Stateless / privacy-preserving
5. Both inbound + outbound in one tool

No competitor combines all five. The territory is genuinely unoccupied.

#### Market Signals (prospect-relevant)

- **SPS acquired SupplyPike for $206M (Aug 2024)** — validates the
  chargeback-prevention market. Consolidates under enterprise pricing,
  leaving SMBs underserved.
- **Crstl Series A (Mar 2025)** with Shopify Ventures — validates
  food-brand EDI automation thesis. But Crstl is paid platform, not
  free diagnostic.
- **Orderful's free-tool-as-lead-gen pattern** — proves the model
  works. Free EDI Validator drives awareness for their $189/mo
  platform.
- **Platform pricing floor** — SPS (~$750/mo) + TrueCommerce (~$500/mo)
  + Orderful ($189/mo per TP) means a brand doing 3 retailers pays
  $500–$2,250/mo minimum. A free diagnostic tool eliminates commitment
  risk for brands unsure if they have a problem.

#### Structural Analogy

Closest pattern: **MXToolbox** (free DNS/email diagnostic → shows
problems → paid monitoring/fix services) or **TurboTax Free Edition**
(free tool surfaces your situation → gates the fix behind paid
service). EDI Preflight has the diagnostic; the EDI Health Audit is
the fix. The CTA connects them.

### Summary

EDI Preflight occupies genuinely unoccupied territory — no competitor
combines free/ungated access + retailer-specific validation +
chargeback-dollar attribution. The landscape validates both the market
(SPS paid $206M for SupplyPike) and the lead-gen funnel pattern
(Orderful uses free tools to drive platform adoption). The weaknesses
(UI polish, breadth, connectivity) are deliberate scope boundaries,
not oversights — the tool is a diagnostic, not a platform. For a
prospect evaluating this as a credential, the positioning story is
strong and defensible.

---

## Phase 4: Differentiation & Next Moves

**Date:** 2026-05-16
**Context:** Prospect reviewing imminently. Moves ranked for
maximum impression improvement per unit effort.

### Cross-Reference Summary

The internal issues (Phase 2) and competitive position (Phase 3) tell
complementary stories. The code and architecture would impress a
technical reviewer — clean pipeline, high test coverage, modular
design. The competitive positioning would impress a business reviewer
— genuinely unoccupied territory with market validation. But the
"connective tissue" between these strengths is frayed: CI shows red,
analytics are visibly unfinished, and the lead-gen mechanism (the
whole business purpose) points to a personal Gmail.

None of the Phase 2 issues threaten the competitive advantages from
Phase 3. The chargeback attribution, retailer-specific validation,
and food-brand positioning are all solid. What's at risk is the
prospect's *confidence* — small presentation issues that signal
"unfinished" even though the substance is complete.

The strategic play is simple: fix the handful of visible blemishes so
the prospect sees what's actually there — a working, differentiated
tool with a strong competitive moat — rather than getting distracted
by placeholder text and failing CI badges.

### Ranked Next Moves

| # | Move | Category | Strategic | Internal | Effort | Score | Description |
|---|------|----------|-----------|----------|--------|-------|-------------|
| 1 | Fix CI (add httpx dep) | Foundational | 4 | 5 | 1 | 9.0 | Red badge on public repo is first thing a technical prospect sees. One line in pyproject.toml. |
| 2 | Remove GA placeholder | Foundational | 4 | 4 | 1 | 8.0 | Remove unconfigured GA script + comment from source. Add back when you have a real measurement ID. Removes "unfinished" signal. |
| 3 | Professional CTA link | Close gap | 5 | 3 | 1 | 8.0 | Replace Gmail mailto with Calendly/Cal.com booking link or business domain email. Closes gap with Orderful's professional funnel. |
| 4 | Add CI badge to README | Foundational | 3 | 3 | 1 | 6.0 | Green ✓ badge signals working project. Requires #1 first. |
| 5 | Consistent branding | Close gap | 3 | 2 | 1 | 5.0 | Footer + README both say "Lailara LLC" consistently. Professional identity throughout. |
| 6 | Tighten CSP (remove GA exceptions) | Foundational | 2 | 3 | 1 | 5.0 | If removing GA scripts (#2), also remove the CSP exceptions. Cleaner security posture. |
| 7 | Keep machine warm | Double down | 3 | 1 | 2 | 2.0 | Set min_machines_running=1 in fly.toml to eliminate cold-start on prospect's first visit. Costs ~$2/mo. |
| 8 | ARIA labels on tabs | Close gap | 1 | 2 | 1 | 3.0 | role="tab", aria-selected on mode tabs. Low priority but quick. |

### Recommended Sequence

**Pre-prospect sprint (30 minutes, all independent):**

1. Fix CI — add `httpx` to dev deps, push, verify green
2. Remove GA — strip script tags, ga.js reference, CSP exceptions
3. Professional CTA — replace Gmail link in results.html,
   validation_results.html, and base.html footer
4. Branding — footer says "Lailara LLC", README attribution consistent
5. CI badge — add to README (only after #1 lands and CI is green)

**Optional (if time permits):**

6. ARIA labels on tabs (5 minutes)
7. Warm machine — set `min_machines_running = 1` in fly.toml and
   redeploy (eliminates cold-start for prospect's first click)

All items in the sprint are one-line or few-line changes. No
architectural work, no new features, no risk of breaking anything.
The entire sprint could be one commit.

### What NOT to Do

**Don't chase Stedi's UI polish.** The tool is a diagnostic, not a
product. Operations staff at food brands care about accuracy and
actionable output, not smooth animations. Polishing the UI would be
weeks of work with no competitive return — Stedi's advantage is in
viewing/exploring EDI, not in validating it.

**Don't add more transaction types.** Breadth (supporting 810, 820,
997, etc.) doesn't serve the food-brand niche. The 850/856 pair
covers the exact pain point: "I keyed this PO wrong" and "my ASN will
trigger a chargeback." More types dilutes the messaging.

**Don't add connectivity/transmission.** This is competing with
platforms (SPS, TrueCommerce, Orderful) in their core value
proposition. The tool's strength is being diagnostic — it shows the
problem, the audit engagement fixes it. Adding AS2/SFTP would be
months of work that repositions the tool as a competitor to $750/mo
platforms rather than a complement.

**Don't add login/accounts.** The ungated model is a competitive
advantage. Every friction point you add (signup, email capture, rate
limiting) moves toward the territory competitors already own. The
lead-gen mechanism is the CTA, not a gate.

**Don't configure GA before the prospect meeting.** It's better to
have no analytics than visibly placeholder analytics. Add GA after
the prospect review when you have time to configure it properly and
verify it works. For now, remove the placeholder entirely.

### Prospect Talking Points (from this audit)

If the prospect asks about competitive positioning:
- "Only free tool that combines retailer-specific 856 validation with
  chargeback-dollar attribution — SPS paid $206M for that capability."
- "MXToolbox pattern: free diagnostic surfaces the problem, paid
  engagement fixes it."
- "Five grocery retailers because that's where the $15M–$30M brands
  are stuck — between manual processes and $750/mo platforms."

If the prospect looks at the code:
- 297 tests, 3.7s runtime, 1:1 source/test ratio
- Custom X12 parser (no external EDI library dependency)
- Adding a new retailer is ~30 lines
- Clean pipeline: tokenize → envelope → extract/validate → export
