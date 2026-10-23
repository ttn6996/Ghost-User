# Ghost-User

> **Autonomous Website Testing Agent**  
> Simulates real user journeys, verifies web application behavior, captures step-by-step evidence, and diagnoses broken user flows.

---

## 1. Product & Architecture Overview

Ghost-User is built as an isolated asynchronous execution platform where HTTP API request handling is strictly separated from browser execution processes.

- **`apps/web`**: Dark-first Next.js 14 dashboard (TypeScript, Tailwind CSS, Lucide icons).
- **`apps/api`**: FastAPI backend with Pydantic v2 validation, SQLAlchemy 2.0 ORM, and Alembic migrations.
- **`apps/worker`**: Dedicated background worker utilizing Playwright Python Chromium to execute browser journeys.
- **`packages/shared`**: Shared Pydantic action schemas and constants.
- **`tests`**: Comprehensive test suites (API CRUD, SSRF security, browser engine, scheduler, and vertical slice E2E).

```
                      +-----------------------------+
                      |   apps/web (Next.js Dashboard)|
                      +--------------+--------------+
                                     |  HTTP REST
                      +--------------v--------------+
                      |     apps/api (FastAPI)      |
                      +-------+--------------+------+
                              |              |
                      Read /  |              | Serves static
                      Write   |              | artifacts
                              v              v
                      +---------------+  +---------------------+
                      | SQLite (WAL)  |  | data/artifacts/     |
                      | PostgreSQL    |  | (Screenshots/Traces)|
                      +-------^-------+  +----------^----------+
                              |                     |
                      Poll /  |                     | Writes
                      Lock    |                     |
                      +-------+--------------+------+
                      | apps/worker (Playwright)    |
                      +--------------+--------------+
                                     | Browser
                                     v
                      +-----------------------------+
                      | Target Website Under Test   |
                      +-----------------------------+
```

---

## 2. Key Capabilities

1. **Deterministic Action Engine**: Validated JSON test definitions supporting 11 browser actions (`goto`, `click`, `fill`, `select_option`, `check`, `uncheck`, `wait_for_visible`, `assert_visible`, `assert_text`, `assert_url`, `screenshot`).
2. **Definitive Diagnostics**: Distinguishes **Assertion Failures** (UI state mismatch) from **Execution Errors** (timeouts, missing selectors, navigation crashes).
3. **Evidence Capture**: Full-page screenshots on checkpoints and failures, Playwright trace recording (`trace.zip`), and unhandled console error capture (`console.error`, unhandled exceptions).
4. **SSRF & Security Isolation**: Blocks private RFC1918 IP addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), loopback addresses, link-local metadata (169.254.169.254), and prevents journeys from jumping outside their authorized project origin.
5. **Recurring Scheduler**: Recurring background test executions configured via intervals or cron expressions, with duplicate run prevention and crash recovery.

---

## 3. Quick Start Guide

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm 10+
- Git

### 1. Clone & Set Up Python Virtual Environment
```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock
python -m playwright install chromium

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
python -m playwright install chromium
```

> **Note**: `requirements.lock` contains fully pinned dependencies for deterministic and reproducible builds. `requirements.txt` defines abstract direct dependencies with version ranges.

### 2. Install Web Dashboard Dependencies
```bash
npm install
```

### 3. Run Database Migrations
```bash
# Windows PowerShell
.\.venv\Scripts\alembic.exe -c apps/api/alembic.ini upgrade head

# Linux / macOS
alembic -c apps/api/alembic.ini upgrade head
```

---

## 4. Running the Application

Ghost-User runs as three coordinated processes:

| Component | Port / Command | Description |
|---|---|---|
| **API Server** | `http://127.0.0.1:8000` | FastAPI backend & REST endpoints |
| **Worker Process** | Background loop | Polls database queue & runs Chromium tests |
| **Web Dashboard** | `http://localhost:3000` | Dark-mode interactive Next.js interface |

### Using Helper Scripts

**Windows (PowerShell):**
```powershell
# Terminal 1: Start API
.\scripts\start_api.ps1

# Terminal 2: Start Worker
.\scripts\start_worker.ps1

# Terminal 3: Start Web Dashboard
.\scripts\start_web.ps1
```

**Linux / macOS / WSL2 (Bash):**
```bash
# Terminal 1: Start API
./scripts/start_api.sh

# Terminal 2: Start Worker
./scripts/start_worker.sh

# Terminal 3: Start Web Dashboard
./scripts/start_web.sh
```

---

## 5. Automated Testing

Ghost-User includes an automated test suite with deterministic local fixture websites:

```powershell
# Run all tests (Windows PowerShell)
.\scripts\run_all_tests.ps1

# Run all tests (Linux / macOS)
./scripts/run_all_tests.sh
```

Or directly via pytest:
```bash
pytest -v
```

### Test Suite Structure
- `tests/api/test_api_crud.py`: Project, TestCase, TestRun, and Schedule REST endpoints.
- `tests/api/test_artifacts_security.py`: Path traversal guard verification and production-mode authorization boundary.
- `tests/api/test_security_ssrf.py`: Target URL SSRF guards, private IP blocking, origin restrictions, traversal guards.
- `tests/worker/test_browser_security.py`: Playwright route interception, external navigation/clicks, redirects, subresources, metadata IPs, DNS resolution checks, and production environment guards.
- `tests/worker/test_atomic_claims.py`: Atomic conditional status claiming (`UPDATE ... WHERE status='queued'`), concurrent multi-worker claims, and error resilience.
- `tests/worker/test_execution_engine.py`: Headless Chromium execution, action validations, assertion failures, error capture.
- `tests/worker/test_worker_queue.py`: Asynchronous queue consumer and worker claim transitions.
- `tests/worker/test_scheduler_and_recovery.py`: Crash recovery, scheduled job triggers, duplicate run prevention.
- `tests/e2e/test_full_journey.py`: End-to-end integration test creating a project, test case, enqueuing a run, executing via worker, and fetching results.

---

## 6. Sample Test Definition

Test definitions are stored as validated JSON objects:

```json
{
  "name": "E-Commerce Checkout Flow",
  "steps": [
    {
      "action": "goto",
      "url": "/"
    },
    {
      "action": "fill",
      "selector": "input[name='search']",
      "value": "mechanical keyboard"
    },
    {
      "action": "click",
      "selector": "button#submit-search"
    },
    {
      "action": "assert_visible",
      "selector": ".product-list"
    },
    {
      "action": "click",
      "selector": ".product-card:first-child button.add-to-cart"
    },
    {
      "action": "screenshot",
      "name": "cart_updated"
    },
    {
      "action": "click",
      "selector": "a#cart-checkout"
    },
    {
      "action": "assert_url",
      "expected_url": "/checkout"
    },
    {
      "action": "assert_text",
      "selector": "h1.checkout-title",
      "expected_text": "Complete Your Order",
      "exact": true
    }
  ]
}
```

---

## 7. API Documentation

Interactive API documentation is generated automatically by FastAPI:
- **Swagger UI**: `http://127.0.0.1:8000/api/v1/docs`
- **ReDoc UI**: `http://127.0.0.1:8000/api/v1/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/api/v1/openapi.json`

---

## 8. Security Posture & Safe Execution

- **Route Interception & Subresource SSRF Defense**: Playwright context-level route interception (`context.route("**/*")`) actively evaluates all outgoing requests, clicks, top-level navigations, redirects, and embedded subresources (`<img>`, `<script>`, `fetch`, `XMLHttpRequest`). Destinations resolving to private or special-use CIDRs (RFC 1918, CGNAT `100.64.0.0/10`, benchmark `198.18.0.0/15`, IPv4/IPv6 loopbacks, IPv6 ULA `fc00::/7`, IPv6 link-local `fe80::/10`, and cloud metadata `169.254.169.254`) are aborted at the browser layer.
- **Origin Confinement**: Clicks, script navigations, and redirects cannot jump outside the project's authorized `base_url` origin domain.
- **Production Mode Guard**: In `ENVIRONMENT=production`, local target resolution (`ALLOW_LOCAL_TARGETS=true`) is strictly prohibited and rejected.
- **SSRF Boundary Honesty**: Playwright route interception prevents navigation and subresource requests to disallowed origins and private/metadata IPs. However, total SSRF defense against sophisticated internal DNS rebinding on live targets requires network-level egress proxies in production cloud environments.
- **Atomic Job Claiming**: Workers atomically claim queued test runs via conditional database transitions (`UPDATE ... WHERE status = 'queued'`) committed before launching browser processes, preventing duplicate execution across competing workers.
- **Concurrency Honesty**: The MVP operates with bounded concurrency explicitly set to `WORKER_CONCURRENCY=1` per worker process, ensuring clean database session handling and browser process lifecycle isolation.
- **Artifact Authorization Boundary**: The local MVP artifact endpoint is designed for trusted local environments and enforces strict path traversal verification (`path.resolve()`, `is_relative_to()`). For production public exposure, an authentication reverse proxy or token authorization dependency (`verify_artifact_authorization`) must be enabled.
- **No Injected Code Execution**: Tests are strictly declarative JSON schemas; no arbitrary Python `eval()`, shell scripts, or raw JavaScript execution.
