# OMNIVEX Web Frontend (v3)

**Academic Research Prototype Web Interface**  
*Intelligent AI Reliability Monitoring Under Changing Real-World Conditions*

---

## 1. Architecture & Design Principles

The OMNIVEX Web Frontend is an accessible, modern, dependency-free web application.

- **Zero Build Tools**: Built with pure HTML5, modern Vanilla CSS, and native ES Modules. No npm installations, no bundlers, no transpilers required.
- **Strict Layering**:
  - `views/`: View orchestration only. Never touches `fetch` directly.
  - `components/`: UI element builders (cards, tables, badges, charts, empty/error states).
  - `core/`: State management, session guarding, safe DOM utilities, formatting helpers.
  - `api/`: The **ONLY** layer that executes network calls via `OmnivexClient`.
- **Security by Design**:
  - **No `innerHTML` with API data**: `js/core/dom.js` strictly constructs nodes using `document.createElement`, `textContent`, and safe attribute assignment to prevent Cross-Site Scripting (XSS).
  - **Path Traversal Protection**: Rejects parameter tampering (`..`, `%2e%2e`, slashes) before network requests.
  - **Credential Redaction**: `X-API-Key` headers are never serialized into logs, error outputs, or URLs.

---

## 2. Four-Colour Light Design System

The application strictly implements the OMNIVEX four-colour calm light palette defined in [css/styles.css](file:///c:/OMNIVEX/frontend-web/css/styles.css):

| Role | Color Name | Hex Code | Primary Usage |
| :--- | :--- | :--- | :--- |
| **Primary / Structure** | Navy | `#1B2A41` | Headings, sidebar, table headers, primary text, neutral status |
| **Accent / Healthy** | Teal | `#1F9E9E` | Primary buttons, active nav, "Normal / Healthy" state, info severity |
| **Caution** | Amber | `#F2A93B` | "Drift Detected" state, warning severity alerts, non-critical shifts |
| **Critical** | Coral | `#E4572E` | "Performance Degradation" state, critical severity alerts, errors |

Background is light neutral (`#F8FAFC`), surfaces are crisp white (`#FFFFFF`), borders are subtle slate (`#E2E8F0`).

---

## 3. Directory Structure

```
frontend-web/
  index.html            # Login entry page & backend connection gate
  app.html              # Dashboard SPA shell
  css/
    styles.css          # Design system tokens, utilities, cards, tables, responsive rules
  js/
    api/
      config.js         # Endpoint URLs, timeouts, retry limits
      client.js         # Complete REST client with ApiResult pattern
    core/
      router.js         # Hash-based SPA router with session guarding
      store.js          # Reactive session store
      auth.js           # Login / logout / session guard
      format.js         # Dates, percentages, decimals, reliability status mapping
      dom.js            # Safe DOM builder avoiding innerHTML with untrusted data
    components/
      statusBadge.js    # Badges for 6 reliability states & alert severities
      metricCard.js     # Key metric display cards
      charts.js         # Plotly wrappers with SVG fallback
      tables.js         # Interactive sortable, paginated tables
      states.js         # Loading, empty, error, and offline UI state renderers
    views/
      overview.js       # Mission Control overview & active alerts
      datasets.js       # Dataset upload, inspection, and schema validator
      models.js         # Train models, baseline metrics, artifact verification
      drift.js          # Two-sample KS, Chi², TVD tests with FDR correction
      performance.js    # Empirical performance & bootstrap confidence intervals
      alerts.js         # Alert lifecycle audit log & acknowledgement
      experiments.js    # Simulation scenarios (shocks, noise) & CSV/JSON export
      system.js         # Backend connectivity, ping latency, API key settings
  assets/
    favicon.svg         # SVG favicon
    logo.svg            # SVG wordmark
  tests/
    client.test.mjs     # Standalone unit tests for client.js (node --test)
  README.md
  SCHEMA_MISMATCHES.md
```

---

## 4. Execution Instructions

### A. Start the FastAPI Backend (if not already running)
```powershell
cd C:\OMNIVEX
.\venv\Scripts\activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### B. Serve the Web Frontend
From `C:\OMNIVEX`, run Python's built-in static HTTP server on port 3000:
```powershell
cd C:\OMNIVEX\frontend-web
..\venv\Scripts\python -m http.server 3000 --bind 127.0.0.1
```

### C. Access the Application
1. Open your browser to [`http://127.0.0.1:3000`](http://127.0.0.1:3000) (or `http://localhost:3000`).
2. Enter your Operator / Researcher name (e.g. `researcher`).
3. Click **Connect & Enter Dashboard**.
4. The login gate verifies connectivity with `GET /api/health` and automatically transitions into the SPA dashboard at `app.html#/overview`.
