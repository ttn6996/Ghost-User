# AutoQA Agent — Test Infrastructure Specification (TEST_INFRA.md)

## 1. Overview & Scope

The **AutoQA Agent** testing infrastructure provides a robust, deterministic, opaque-box End-to-End (E2E) verification environment. It validates the full autonomous web application testing lifecycle across all **33 features**, 4 operational pillars, and 2 operational modes (Mode A manual server and Mode B autonomous background dev server) defined in `PROJECT.md` and `ORIGINAL_REQUEST.md`.

This specification defines the runtime architecture, opaque-box entry points, isolation boundaries, fixture models, and 4-tier test suite layout.

---

## 2. Architecture & Opaque-Box Entry Points

The E2E test harness interacts with the AutoQA Agent platform exclusively through public, opaque-box interfaces:

```
                            ┌────────────────────────┐
                            │    E2E Test Runner     │
                            │ (tests/e2e/test_suite) │
                            └───────────┬────────────┘
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
┌────────────────────────┐                               ┌────────────────────────┐
│  REST API Entry Point  │                               │ Playwright Worker /    │
│    (FastAPI Client)    │                               │  Browser Context       │
│                        │                               │                        │
│ • POST /api/v1/projects│                               │ • Chromium Sandbox     │
│ • POST /api/v1/test-   │                               │ • SSRF Route Guard     │
│   cases                │                               │ • Session Injection    │
│ • POST /api/v1/test-   │                               │ • AXTree Fallbacks     │
│   runs                 │                               │ • Multi-Signal Watcher │
│ • GET /api/v1/test-    │                               │ • Post-Action Reload   │
│   runs/{id}            │                               │ • Queue Consumer Claim │
│ • GET /api/v1/export/* │                               │ • Tagged Data Cleanup  │
└────────────┬───────────┘                               └───────────┬────────────┘
             │                                                       │
             ▼                                                       ▼
┌────────────────────────┐                               ┌────────────────────────┐
│  Isolated SQLite DB    │                               │ Deterministic Local    │
│ (In-Memory StaticPool) │                               │ Fixture Server (HTTP)  │
└────────────────────────┘                               └────────────────────────┘
```

### 2.1 REST API Interface
- **Base Endpoint**: `/api/v1`
- **Projects**:
  - `POST /api/v1/projects`: Create project workspace with `name`, `base_url`, `description`, `allowed_domains`, `source_code_path`, `allow_local_loopback`, `execution_mode`, `auth_profile_json`.
  - `GET /api/v1/projects`: List projects.
  - `GET /api/v1/projects/{id}`: Fetch project details.
  - `DELETE /api/v1/projects/{id}`: Delete project workspace.
- **Test Cases**:
  - `POST /api/v1/test-cases`: Create test case definition with steps (`goto`, `click`, `fill`, `assert_visible`, `assert_text`, `assert_url`, `reload_verify`, `screenshot`, etc.).
  - `GET /api/v1/test-cases`: List test cases by project.
  - `GET /api/v1/test-cases/{id}`: Fetch test case.
- **Test Runs & Lifecycle**:
  - `POST /api/v1/test-runs`: Enqueue test run (`test_case_id`, `trigger_type`).
  - `GET /api/v1/test-runs/{id}`: Poll run status (`queued`, `analyzing`, `planning`, `running`, `passed`, `failed`, `cancelled`).
  - `GET /api/v1/test-runs/{id}/export/json`: Standardized JSON report export.
  - `GET /api/v1/test-runs/{id}/export/html`: Standalone styled HTML report export.
- **Artifacts**:
  - `GET /api/v1/artifacts/{filepath}`: Retrieve screenshots, logs, and Playwright traces with path traversal guard.
- **Schedules**:
  - `POST /api/v1/schedules`: Create recurring execution schedule (interval or cron).
  - `GET /api/v1/schedules`: List schedules.
- **Stats**:
  - `GET /api/v1/stats/overview`: Overview metrics (total projects, test cases, runs, pass rate).

### 2.2 Worker & Sandbox Execution Interface
- **Queue Consumer**:
  - `QueueConsumer(session).process_next_job()`: Atomically claims the next pending run and executes the Playwright browser sandbox session.
- **Browser Execution Sandbox**:
  - Headless Chromium worker with route interception enforcing SSRF CIDR filters and origin confinement.
  - Session injection injecting cookies and localStorage tokens before navigation.
  - Self-healing locator fallback executing accessibility tree (AXTree) element matching upon CSS selector mismatch.
  - Async spinner waiting ensuring network and DOM stability before assertions.
  - Multi-signal evaluation: HTTP 4xx/5xx intercept, `console.error` and `pageerror` event listeners, post-action reload DOM verification.
  - Artifact capture: Full-page screenshot and trace recording on failure.
  - Automated tagged test data cleanup: Tagged synthetic records (`AUTOQA_<run_id>`) purged post-run.

---

## 3. Environment & Configuration Variables

| Variable | Permitted Values | Default in Testing | Purpose |
|---|---|---|---|
| `ENVIRONMENT` | `test`, `development`, `production` | `test` | When set to `production`, strictly blocks localhost/loopback targets regardless of settings. |
| `DATABASE_URL` | SQLite URI | `sqlite:///:memory:` | In-memory database with shared cache for fast, isolated test execution. |
| `ALLOW_LOCAL_TARGETS` | `true`, `false` | `true` | Allows local loopback fixture servers (`127.0.0.1`, `localhost`) to be tested in dev/test mode. |
| `ARTIFACT_STORAGE_DIR` | Filesystem Path | `tmp_path` fixture | Isolated temporary directory for screenshots, traces, and export artifacts. |

---

## 4. Test Fixtures & Deterministic Harness

### 4.1 In-Memory Database Session (`db_session`)
- Uses SQLAlchemy `create_engine` with `sqlite:///file:ghost_test_mem?mode=memory&cache=shared&uri=true` and `StaticPool`.
- `Base.metadata.create_all()` is executed on setup, and `Base.metadata.drop_all()` on teardown to guarantee 100% test isolation.

### 4.2 FastAPI HTTP Test Client (`client`)
- Overrides `get_db` dependency to inject the active test `db_session`.
- Exercises the full FastAPI route pipeline, request validation, exception handlers, and response serialization.

### 4.3 Deterministic Local HTTP Fixture Server (`fixture_server`)
- Runs a lightweight, multi-threaded `ReusableHTTPServer` on a random ephemeral port (`port=0`).
- Provides deterministic web pages:
  - `/`: Home page with headings and navigation links (`#nav-search`, `#nav-login`).
  - `/search`: Form with search input and live query result rendering.
  - `/login`: Form with email, role dropdown, checkbox, and redirect to `/dashboard`.
  - `/dashboard`: Authenticated dashboard with welcome banner.
  - `/external-link`: Outbound links to external domains for origin confinement testing.
  - `/redirect-to-metadata`: HTTP 302 redirecting to cloud metadata IP (`169.254.169.254`).
  - `/metadata-subresource`: Page embedding metadata IP image and fetch subresources.
  - `/broken`: Page intentionally emitting console errors and unhandled JavaScript exceptions.
  - `/spinner`: Page displaying simulated async loading spinner before resolving content.

---

## 5. 4-Tier Test Suite Architecture

The comprehensive E2E test suite in `tests/e2e/test_e2e_suite.py` is organized across 4 tiers:

### Tier 1: Feature Coverage (>=5 Tests Per Feature across Features 1–33)
Validates the primary expected behavior (happy path) for all 33 features:
1. **SSRF CIDR Blocking**: IPv4 private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), loopback (127.0.0.1), link-local metadata (169.254.169.254), CGNAT (100.64.0.0/10), IPv6 loopback (::1).
2. **DNS Pre-Resolution Inspection**: Pre-resolves domain names and verifies resolved IP addresses before connection.
3. **Origin Confinement & Domain Allowlists**: Enforces origin matching and allows configured domain allowlists.
4. **Production Mode Guard**: Enforces strict rejection of loopback and private IPs when `ENVIRONMENT=production`.
5. **Credential & Secret Masking**: Masks passwords, tokens, API keys across logs, traces, and JSON responses.
6. **Artifact Path Traversal Guard**: Prevents path traversal (`../`, `..\\`, null bytes `%00`) in artifact retrieval.
7. **Project Workspace Management**: CRUD on projects with local paths, allowlists, and Mode A/B configurations.
8. **Source Code Route & Schema Parser**: Parses project source trees to extract endpoints and parameters.
9. **Autonomous Web Exploration & Crawling**: Crawls web pages within domain boundary using accessibility tree snapshots.
10. **Form Inspection & Semantic Classification**: Identifies and classifies forms (Login, Search, Registration, CRUD).
11. **Test Scenario Generation**: Generates structured test definitions conforming to schemas.
12. **Tagged Synthetic Test Data Generation**: Creates test data tagged with `[AUTOQA_<run_id>]`.
13. **Autonomous Dev Server Runner (Mode B)**: Detects start scripts, starts background dev server, and parses port.
14. **Isolated Playwright Browser Sandbox**: Dedicated browser context per run with pristine storage and cache.
15. **Session Injection / Login Profiles**: Injects auth cookies, bearer tokens, and localStorage before execution.
16. **Self-Healing Element Locators**: Recovers from broken selectors by falling back to AXTree semantic role/name.
17. **Async Loading & Spinner Resilience**: Waits for loading overlays and network idle before executing assertions.
18. **Execution Timeouts & Hanging Protection**: Enforces per-action timeout and run timeout.
19. **Observable DOM State Assertions**: Asserts visibility, text content, and URL changes.
20. **Multi-Signal: Post-Action Page Reload**: Verifies state persistence and DOM consistency after page reload.
21. **Multi-Signal: HTTP Status & Console Error Detection**: Intercepts HTTP 4xx/5xx and browser console errors.
22. **Automatic Evidence Capture**: Captures full-page screenshots and archives Playwright traces on failure.
23. **Severity Taxonomy Categorization**: Categorizes findings into CRITICAL, HIGH, MEDIUM, LOW.
24. **Automated Test Data Cleanup / Teardown**: Post-run purging of tagged synthetic records.
25. **Source Code Correlation Heuristics**: Correlates runtime failures and HTTP faults with source files and line numbers.
26. **Confidence Scoring Engine**: Computes correlation confidence scores (0.0 to 1.0).
27. **Test Run Lifecycle State Machine**: Enforces valid state transitions (CREATED -> ANALYZING -> PLANNING -> RUNNING -> COMPLETED/FAILED).
28. **Step-by-Step Reproduction Flow**: Generates reproducible steps with observed vs expected values.
29. **Route & Form Coverage Tracking**: Computes percentage of discovered routes and forms exercised.
30. **Report Exports (JSON & HTML)**: Generates valid JSON report exports and styled standalone HTML documents.
31. **Worker Queue Atomic Conditional Job Claiming**: Prevents double-claiming via atomic status updates.
32. **Worker Crash Recovery of Orphaned Runs**: Recovers runs stuck in running status on worker reboot.
33. **Scheduler Recurring Test Execution & De-duping**: Enqueues recurring runs while preventing duplicate concurrent executions.

### Tier 2: Boundary & Corner Cases (>=5 Tests Per Feature Category)
Tests extreme values, malformed inputs, edge conditions, and resource limits:
- Extreme URL lengths (>2048 chars), IPv6 bracketed notation, octal/hex IP encodings.
- Empty payloads, missing required fields, extremely long strings (10,000+ chars).
- Special characters, unicode emojis, SQL injection patterns, script tags in project names and form fields.
- Zero-millisecond timeouts, extreme timeout values, rapid cancellation while queued.
- Concurrent job claiming under high worker concurrency.

### Tier 3: Cross-Feature Interactions
Tests pairwise and multi-feature combinations:
- SSRF route interception + Mode A loopback permission.
- Credential masking + trace archive export + JSON export.
- Source route parsing + crawler exploration + tagged synthetic test data generation.
- Session injection + post-action page reload + DOM assertion.
- Worker crash recovery + atomic queue claiming + scheduler de-duping.

### Tier 4: Real-World Application Scenarios
Simulates realistic, multi-step end-to-end user journeys:
1. **Local Project Audit (Mode A)**: Project creation with local directory -> route discovery -> test generation -> Playwright execution -> clean pass.
2. **Autonomous Background Server Exploration (Mode B)**: Source inspection -> dev server startup -> crawling -> form classification -> test execution.
3. **Authenticated User Journey with Session Injection**: Login profile injection -> authenticated dashboard navigation -> state modification -> post-action reload verification.
4. **Fault Detection & Root Cause Analysis Flow**: Exploration navigates to broken page -> HTTP 500 & console errors captured -> screenshot/trace stored -> source correlation pinpointed -> HTML/JSON report exported.
5. **High-Concurrency Worker Crash & Recovery**: Multiple runs enqueued -> worker crash simulation -> crash recovery resets orphaned runs -> queue claims and completes all runs.

---

## 6. Authoritative Output Derivation

For every test case, expected outputs are derived from authoritative specifications:
- **Status Codes**: RFC 9110 HTTP Semantics (200 OK, 201 Created, 400 Bad Request, 404 Not Found, 422 Unprocessable Entity).
- **Security Rejections**: `ORIGINAL_REQUEST.md` Acceptance Criteria (SSRF validation rejection for private/loopback/metadata CIDRs).
- **Lifecycle Enums**: `packages.shared.constants.RunStatus` and `StepStatus`.
- **Severity Levels**: `packages.shared.constants.SeverityLevel` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- **Dynamic Fields**: Timestamps, UUIDs, and duration metrics are verified for existence, type, and positive bounds (`assert data["duration_ms"] > 0`).

---

## 7. Execution & Runner Commands

### 7.1 Running the Entire Test Suite
```bash
python -m pytest tests/e2e/test_e2e_suite.py -v
```

### 7.2 Running Specific Tiers
```bash
# Tier 1: Feature Coverage
python -m pytest tests/e2e/test_e2e_suite.py -k "tier1" -v

# Tier 2: Boundary & Corner Cases
python -m pytest tests/e2e/test_e2e_suite.py -k "tier2" -v

# Tier 3: Cross-Feature Interactions
python -m pytest tests/e2e/test_e2e_suite.py -k "tier3" -v

# Tier 4: Real-World Application Scenarios
python -m pytest tests/e2e/test_e2e_suite.py -k "tier4" -v
```

### 7.3 Running with Coverage Report
```bash
python -m pytest tests/e2e/test_e2e_suite.py --tb=short
```
