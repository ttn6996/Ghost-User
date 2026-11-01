# Project: AutoQA Agent

AutoQA Agent is a production-grade autonomous web application testing platform that explores web applications using real browser execution, correlates findings with source code, and produces verifiable bug reports with rich evidence.

## User Operational Directives & Core Pillars

### 1. Standalone / Local Code Audit Operational Modes
The platform supports testing local applications directly from source code directories (e.g. `d:\code\DA2\sourcecode\CampusHub-Frontend`):
- **Mode A (Manual Local Server URL)**: The user starts their local dev server (e.g. `http://localhost:3000` or `http://localhost:8080`) and provides the URL. The system validates the project with `allow_local_targets=True` in development mode, allowing local testing without being falsely rejected by SSRF guards (production mode continues to enforce strict SSRF blocks).
- **Mode B (Autonomous Background Dev Server)**: The system inspects the target source code (`package.json`, `pom.xml`, etc.), detects the start command (e.g. `npm run dev`, `mvn spring-boot:run`), launches the background dev server, extracts the active URL/port, and automatically audits the application.

### 2. Four Functional Pillars
- **Pillar 1: Local Source Code Analysis & Discovery**: Parsing local directories for routes, pages, forms, endpoints, and validation schemas.
- **Pillar 2: Network Environment & Authentication**: Localhost loopback permissions, session injection / login profiles (`auth_profile`: cookies, localStorage, tokens) for instant authenticated exploration.
- **Pillar 3: Self-Adaptive & Anti-Flaky Test Engine**: Self-healing element locators with accessibility tree (AXTree) semantic fallbacks; automated async spinner/loading overlay handling.
- **Pillar 4: Data Management & Automated Cleanup**: Synthetic test data tagged with unique run identifiers (`[AUTOQA_<run_id>]`) and post-run teardown hooks to keep the user's local database clean.

---

## Architecture

```
                          ┌────────────────────────┐
                          │   Next.js Dashboard    │
                          │      (apps/web)        │
                          └───────────┬────────────┘
                                      │ REST API / Mode A & B Controls
                                      ▼
                          ┌────────────────────────┐
                          │   FastAPI Core API     │
                          │      (apps/api)        │
                          └─────┬────────────┬─────┘
                                │            │
      Source Code Parser & AST  │            │ SQLite / SQLAlchemy
      Dev Server Runner (Mode B)│            ▼
      Confidence Correlation    │    ┌───────────────┐
                                │    │ Relational DB │
                                │    └───────┬───────┘
                                ▼            │ Atomic Claims
                          ┌──────────────────┴─────┐
                          │    Playwright Worker   │
                          │     (apps/worker)      │
                          └───────────┬────────────┘
                                      │ Route Interception & SSRF Filter (Mode A/B aware)
                                      ▼
                          ┌────────────────────────┐
                          │ Isolated Chromium Page │
                          │ (Self-Healing & Auth)  │
                          └────────────────────────┘
```

- **`packages/shared`**: Shared constants, state enums (`RunStatus`, `SeverityLevel`, `ActionType`), Pydantic action schemas, login profile schemas, and test definitions.
- **`apps/api`**: FastAPI application handling project workspaces, local directory paths, dev server management (Mode B), AST route/controller/schema parsing, test case management, run lifecycle state machine, source correlation engine, report exports (JSON/HTML), and security authorization.
- **`apps/worker`**: Background queue consumer executing Playwright browser tests in isolated browser contexts with SSRF network route interception (with local dev mode bypass), session injection, self-healing locators via AXTree, multi-signal verification (DOM, reload, HTTP status, console.error), screenshot/trace artifact generation, and automated tagged test data cleanup.
- **`apps/web`**: Next.js 14 dark-mode dashboard displaying run lifecycles, local directory inputs, Mode A/B toggles, auth profile configs, step timelines with screenshots and trace downloads, bug reproduction flows, route coverage tracking, and export triggers.

---

## Feature Inventory

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | SSRF CIDR Blocking | Blocks IPv4/IPv6 private, link-local, loopback, CGNAT, benchmark, multicast ranges at config & runtime | M1 | survey (R1, AC 1.1) |
| 2 | DNS Pre-Resolution Inspection | Resolves target hostname via DNS before HTTP/Playwright connection and verifies all resolved IP addresses | M1 | survey (R1, AC 1.1) |
| 3 | Origin Confinement & Domain Allowlists | Restricts navigations, redirects, and subresources to project's authorized base URL or domain allowlist | M1 | survey (R1, AC 2.1) |
| 4 | Production Mode Guard | Strict refusal to allow loopback or local destinations when `ENVIRONMENT=production` | M1 | survey (R1, AC 1.1) |
| 5 | Credential & Secret Masking | Masks authentication secrets, tokens, and passwords in console logs, traces, error dumps, and JSON exports | M1 | survey (R1, AC 1.2) |
| 6 | Artifact Path Traversal Guard | Sanitizes artifact requests against directory traversal (`..`), symlinks, and null bytes | M1 | survey (R1) |
| 7 | Project Workspace Management (Local Paths) | Manages projects with target URL, local directory path, domain allowlist, and Mode A/B configs | M1 | survey (R1, Directive) |
| 8 | Source Code Route & Schema Parser | Statically parses local application source code to extract routes, HTTP methods, controllers, and validation schemas | M2 | survey (R2, AC 2.2, Directive) |
| 9 | Autonomous Web Exploration & Crawling | Explores web pages within domain boundary using Playwright Chromium and accessibility tree snapshots | M2 | survey (R2, AC 2.1) |
| 10 | Form Inspection & Semantic Classification | Inspects DOM forms and inputs, classifying as Login, Registration, Search, CRUD, or General | M2 | survey (R2) |
| 11 | Test Scenario Generation (Auth & CRUD) | Synthesizes executable test suites covering smoke tests, boundary conditions, input validations, and CRUD workflows | M2 | survey (R2, AC 2.2) |
| 12 | Tagged Synthetic Test Data Generation | Generates realistic, non-destructive test input data tagged with `[AUTOQA_<run_id>]` for safe tracking | M2 | survey (R2, AC 2.3, Directive) |
| 13 | Autonomous Dev Server Runner (Mode B) | Automatically inspects project, executes start command, and extracts active localhost port/URL | M2 | user directive (Mode B) |
| 14 | Isolated Playwright Browser Sandbox | Runs each test journey in a dedicated, isolated browser context (clean cookies, localStorage, cache) | M3 | survey (R3, AC 3.1) |
| 15 | Session Injection / Login Profiles | Injects authentication cookies, localStorage, and bearer tokens directly into browser context | M3 | user directive (Pillar 2) |
| 16 | Self-Healing Element Locators | Automatically recovers from broken selectors by falling back to semantic AXTree attributes (role, name) | M3 | user directive (Pillar 3) |
| 17 | Async Loading & Spinner Resilience | Automatically waits for network idle and loading spinner/skeleton overlay removal before assertions | M3 | user directive (Pillar 3) |
| 18 | Execution Timeouts & Hanging Protection | Enforces per-action timeout and global run timeout to prevent worker hangs | M3 | survey (R3, AC 3.1) |
| 19 | Observable DOM State Assertions | Validates element visibility (`assert_visible`), text content (`assert_text`), and URL pattern (`assert_url`) | M3 | survey (R3) |
| 20 | Multi-Signal: Post-Action Page Reload | Reloads page after state-modifying actions to verify observable DOM state and session persistence | M3 | survey (R3) |
| 21 | Multi-Signal: HTTP Status & Console Error Detection | Intercepts HTTP 4xx/5xx responses and captures unhandled `console.error` and `pageerror` events | M3 | survey (R3, AC 3.2) |
| 22 | Automatic Evidence Capture | Automatically captures full-page screenshot on failure/error and archives Playwright `trace.zip` | M3 | survey (R3, AC 3.3) |
| 23 | Severity Taxonomy Categorization | Categorizes detected findings by impact: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` | M3 | survey (R3, AC 3.2) |
| 24 | Automated Test Data Cleanup / Teardown | Executes post-run cleanup to purge synthetic data created during the test run from local database | M4 | user directive (Pillar 4) |
| 25 | Source Code Correlation Heuristics | Correlates runtime failures, console errors, and HTTP faults with specific source code files and line numbers | M4 | survey (R4, AC 4.1) |
| 26 | Confidence Scoring Engine | Computes correlation confidence score (0.0 to 1.0) based on stack trace symbols, route matches, and DOM selectors | M4 | survey (R4, AC 4.1) |
| 27 | Test Run Lifecycle State Machine | Manages structured lifecycle states: `CREATED -> ANALYZING -> PLANNING -> RUNNING -> COMPLETED/FAILED` | M4 | survey (R4, AC 4.2) |
| 28 | Step-by-Step Reproduction Flow | Generates reproducible user reproduction steps including preconditions, action sequence, and observed vs expected | M4 | survey (R4, AC 4.3) |
| 29 | Route & Form Coverage Tracking | Tracks percentage of discovered application routes and interactive forms exercised by tests | M4 | survey (R4, AC 4.3) |
| 30 | Report Exports (JSON & HTML) | Generates and exports comprehensive test reports in structured JSON and self-contained HTML formats | M4 | survey (R4, AC 4.3) |
| 31 | Worker Queue Atomic Conditional Job Claiming | Claims queued runs atomically using conditional update queries preventing race conditions | M3 | survey (R3) |
| 32 | Worker Crash Recovery of Orphaned Runs | On worker reboot, detects runs stuck in running status and resets them cleanly | M3 | survey (R3) |
| 33 | Scheduler Recurring Test Execution & De-duping | Enqueues scheduled test runs via fixed interval or cron trigger while preventing duplicate concurrent runs | M3 | survey (R3) |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Security Isolation, Domain Allowlists & Workspace Management | Config & runtime SSRF validation, Mode A localhost dev mode flag, multi-domain allowlists, local source path inputs, secret masking, login profile schema | none | IN_PROGRESS |
| M2 | Source Code Route/Schema Parser & Autonomous Scenario Generation | AST/schema parser for local dirs, Mode B dev server runner, accessibility tree exploration, CRUD/auth scenarios, tagged synthetic test data | M1 | PLANNED |
| M3 | Sandbox Browser Execution, Multi-Signal Verification & Anti-Flaky Engine | Isolated Playwright execution, session injection (Pillar 2), self-healing locators & spinner resilience (Pillar 3), multi-signal verify, severity taxonomy | M1 | PLANNED |
| M4 | Source Code Correlation, Data Cleanup & Dashboard Reporting | Code correlation & confidence, automated data cleanup teardown (Pillar 4), 5-stage lifecycle state machine, reproduction flow, coverage tracking, JSON/HTML exports, Next.js UI | M1, M2, M3 | PLANNED |
| M5 | Final Milestone: 100% E2E Test Suite Pass & Adversarial Hardening | Phase 1: 100% pass on Tiers 1-4 E2E test suite. Phase 2: Adversarial coverage hardening (Tier 5) with Challenger stress testing | M1, M2, M3, M4, TEST_READY.md | PLANNED |

In parallel:
- **E2E Testing Track**: Independent opaque-box test track creating test harness, test runner, and test cases covering Tiers 1-4 across all 33 features. Publishes `TEST_INFRA.md` and `TEST_READY.md`.

---

## Code Layout & File Boundaries

```
D:\code\nghich\Ghost-User\
├── packages/
│   └── shared/               # Shared constants, enums, schemas (Owned by M1, M3, M4)
│       ├── constants.py      # RunStatus (CREATED..FAILED), SeverityLevel, ActionType, ExecutionMode
│       └── schemas.py        # Pydantic models for actions, test defs, reports, auth_profile
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── api/v1/       # REST endpoints (M1: projects, M2: discover, M4: test_runs/export)
│   │   │   ├── core/         # Config, logging, masking (M1)
│   │   │   ├── db/models.py  # SQLAlchemy database models (M1, M3, M4)
│   │   │   ├── schemas/      # API schemas (M1, M2, M4)
│   │   │   └── services/     # source_parser (M2), dev_server (M2), correlation (M4)
│   │   └── alembic/          # Database migrations
│   ├── worker/
│   │   ├── runner/
│   │   │   ├── security.py   # SSRF & domain security (M1, Mode A aware)
│   │   │   ├── masking.py    # Log & trace secret masking (M1)
│   │   │   ├── crawler.py    # AXTree web crawler & discovery (M2)
│   │   │   ├── data_gen.py   # Tagged synthetic test data generator (M2, Pillar 4)
│   │   │   ├── engine.py     # Playwright browser sandbox, session injection, self-healing (M3)
│   │   │   ├── actions.py    # Action executors & reload verification (M3)
│   │   │   ├── cleanup.py    # Teardown & data cleanup executor (M4, Pillar 4)
│   │   │   ├── queue_consumer.py # Job queue claims (M3)
│   │   │   └── artifacts.py  # Screenshots & Playwright trace (M3)
│   │   └── scheduler/        # Recurring run scheduler (M3)
│   └── web/                  # Next.js 14 Dashboard (M4)
│       └── src/app/          # UI pages, Mode A/B controls, login profiles, reproduction flows
└── tests/
    ├── api/                  # API test suites (M1, M2, M4)
    ├── worker/               # Worker & browser tests (M1, M2, M3)
    └── e2e/                  # Dual-track opaque-box E2E test suite (E2E Track & M5)
```

---

## Interface Contracts

### 1. Project Management & Security (`apps/api` ↔ `apps/worker`)
- **`Project` model additions**:
  - `allowed_domains: List[str]` (JSON-encoded list of allowed hostnames/domains).
  - `source_code_path: Optional[str]` (Path to local source directory or uploaded archive).
  - `allow_local_loopback: bool` (Permits `http://localhost:*` and `127.0.0.1` in development mode).
  - `execution_mode: str` (`"mode_a_manual"` or `"mode_b_auto"`).
  - `auth_profile_json: Optional[str]` (JSON storage for cookies, localStorage, and bearer tokens).
- **Validation Contract**:
  - In production mode, SSRF strictly rejects private/loopback/cloud metadata CIDRs.
  - In development mode (`ENVIRONMENT != "production"`), if `allow_local_loopback=True`, `localhost` and `127.0.0.1` are permitted for Mode A & B local auditing.

### 2. Source Code Parser & Dev Server Runner (`apps/api` ↔ `apps/worker`)
- **Parser Signature**:
  - `SourceCodeParser.extract_routes(local_path: str) -> List[DiscoveredRoute]`
- **Dev Server Signature (Mode B)**:
  - `DevServerRunner.start_server(local_path: str) -> DevServerProcess(url: str, port: int, pid: int)`
  - `DevServerRunner.stop_server(pid: int)`

### 3. Execution Engine & Self-Healing Contract (`apps/worker` ↔ `packages/shared`)
- **Session Injection**:
  - Before journey execution, if `auth_profile` is present, `context.add_cookies(...)` and `page.evaluate(...)` inject auth state into the browser.
- **Self-Healing Locators**:
  - When primary selector fails, `locator_resolver.resolve_fallback(page, action.target_role, action.target_name)` queries the accessibility tree snapshot to find the matching element.
- **Spinner Resilience**:
  - `engine.wait_for_page_readiness(page)` waits for network idle and ensures no loading spinners/skeletons are active.

### 4. Tagged Data & Cleanup Contract (`apps/worker` ↔ `apps/api`)
- **Data Tagging**:
  - All synthetic inputs use format `AUTOQA_{run_id}_{field}_{uuid}`.
- **Cleanup**:
  - `DataCleanupExecutor.teardown(project_id: str, run_id: str)` executes cleanup routines.
