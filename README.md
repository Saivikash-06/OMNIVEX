# OMNIVEX – Intelligent AI Reliability Monitoring Under Changing Real-World Conditions

> **SCOPE & ACADEMIC DISCLAIMER**  
> **Controlled Academic Research Tool:** OMNIVEX is a college-level academic research prototype designed for studying distribution drift, performance degradation, and automated alert triggering in machine learning systems. **It is NOT certified for safety-critical, medical, financial production, or autonomous decision-making environments.**

---

## 1. Project Objective & Core Principles

OMNIVEX continuously audits machine learning models when incoming data shifts relative to an established reference distribution.

### Core Methodological Principles
1. **Drift Is Not Failure:** A statistically significant input distribution shift ($p < \alpha$) does **not** equal confirmed model accuracy degradation. Input features can drift while accuracy remains stable, or model accuracy can decay without detectable input drift (concept drift).
2. **Missing Labels Are Not Model Failure:** In real-world deployments, ground-truth labels arrive with substantial latency or are completely unavailable. OMNIVEX reports `labels_unavailable` and flags degradation as *unconfirmed*, rather than assuming failure or fabricating estimates.
3. **Reproducibility & Integrity:** Every monitoring run records full settings snapshots, random seeds, library versions (`numpy`, `pandas`, `scipy`, `scikit-learn`), dataset SHA-256 hashes, and tampered-model validation.

---

## 2. Technology Stack

- **Runtime:** Python 3.10+ (targeted and validated on Python 3.11.16)
- **API Framework:** FastAPI, Uvicorn, Starlette
- **Data Validation & Settings:** Pydantic v2 & `pydantic-settings` (reading `.env`)
- **Scientific Computing:** Pandas, NumPy, SciPy, Scikit-learn
- **Database:** SQLAlchemy 2.x with SQLite (`PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;`)
- **Model Persistence:** Joblib with SHA-256 integrity verification
- **Rate Limiting:** SlowAPI (in-app per-IP token bucket)
- **Frontend Dashboard:** Streamlit with decoupled `OmnivexAPIClient`
- **Testing:** Pytest, pytest-asyncio, Starlette TestClient

---

## 3. Architecture & Module Design

```
OMNIVEX/
  backend/
    app/
      main.py                  # Lifespan context manager, security headers, CORS, exception handlers
      core/
        config.py              # pydantic-settings configuration
        security.py            # API key constant-time validation, path traversal guard, formula sanitization
        errors.py              # Unified error envelope and exception handlers
        logging.py             # Structured request logging with correlation IDs
      api/
        deps.py                # Database session, settings, and auth dependencies
        routes/
          health.py            # GET /api/health (status, DB check, version, UTC time)
          datasets.py          # POST upload, GET list, GET single, POST validate-incoming
          models.py            # POST train, GET list, GET single, POST predict
          monitoring.py        # POST drift, POST performance, POST run, GET summary
          alerts.py            # GET list/filter, PATCH acknowledge
          experiments.py       # POST create, GET list, GET details, GET export (CSV/JSON)
      services/
        dataset_service.py     # Streamed CSV parsing, schema inference, reference-fit preprocessor
        drift_service.py       # Pure statistical functions: KS test, numerical & categorical PSI, Chi-Square
        model_service.py       # Scikit-learn Pipeline (preprocessing + estimator), hash-verified loading
        performance_service.py # Confusion matrix, accuracy, F1, bootstrap confidence intervals
        reliability_service.py # Deterministic 6-state decision table
        alert_service.py       # Generation, severity mapping, deduplication/capping, acknowledgment
        experiment_service.py  # Orchestration, repeatability, sanitized CSV/JSON exports
        simulation.py          # Controlled drift perturbation generators (mean_shift, variance, etc.)
      database/
        connection.py          # SQLAlchemy 2.0 SQLite engine, WAL mode, session factory
        models.py              # Declarative models: datasets, models, experiments, runs, drift, alerts
      schemas/
        common.py              # Error schemas, pagination, enums
        dataset.py             # Dataset schemas, column schema, data quality summary
        drift.py               # Drift test requests and per-feature results
        model.py               # Model training requests and baseline metrics
        performance.py         # Performance requests, confidence intervals, reliability response
        alert.py               # Alert response and acknowledgment schemas
        experiment.py          # Experiment run and simulation schemas
    tests/
      conftest.py              # Isolated SQLite DB & temp directories per test session
      test_foundation.py       # Health, headers, correlation IDs
      test_datasets.py         # CSV upload, bounds, schema validation, preprocessing
      test_drift.py            # KS, PSI, Chi-Square, false-positive bounds, effect size
      test_models.py           # Training, target leakage, tampered file rejection, inference
      test_performance_and_reliability.py # Hand-computed metrics, 6 reliability states
      test_alerts.py           # Alert generation, capping, idempotent acknowledgment
      test_experiments.py      # Repeatability with seed, simulation labeling, CSV/JSON export
      test_security.py         # API key, rate limiting, 500 error sanitization, upload size
      test_api_client.py       # Decoupled Streamlit API client verification
  frontend/
    app.py                     # Streamlit research dashboard
    api_client.py              # Decoupled HTTP client with timeout & error mapping
  data/
    demo/                      # Demonstration datasets (credit risk reference and incoming drift scenarios)
    uploads/                   # Server-controlled UUID4 storage
    models/                    # Trained pipeline artifacts
  results/                     # Sanitized export output directory
```

---

## 4. Statistical Drift Methods & Limitations

| Test | Applicable Data | Metric / Statistic | Thresholds | Strengths & Limitations |
|---|---|---|---|---|
| **Kolmogorov–Smirnov (KS)** | Continuous numerical features | $D = \sup_x \|F_1(x) - F_2(x)\|$ | $\alpha = 0.05$ (default), minimum effect size $D \ge 0.10$ | Non-parametric; sensitive to shape, location, and scale. **Limitation:** In very large samples ($N > 10,000$), tiny, practically irrelevant deviations yield $p < 0.05$. OMNIVEX mitigates this by qualifying results with $D < 0.10$ as `significant_low_effect`. |
| **Population Stability Index (PSI)** | Numerical & Categorical features | $\sum (P_i - Q_i) \ln(P_i / Q_i)$ | Moderate: $\ge 0.10$, Major: $\ge 0.25$ | Quantifies distribution divergence across bins. Numerical bins are derived from **reference quantiles**. Unseen categories in incoming batches are grouped into an `__other__` bucket with Laplace-style epsilon smoothing ($10^{-4}$) to prevent $\ln(0)$ or division by zero. |
| **Chi-Square ($\chi^2$) Test** | Categorical features | $\sum \frac{(O_i - E_i)^2}{E_i}$ | $\alpha = 0.05$ (default) | Tests category frequency independence. **Limitation:** Degrades when expected cell frequencies are $< 5$. OMNIVEX checks expected frequencies and falls back to PSI when the test assumptions are violated. |

### Multiple-Testing Correction
Testing dozens of features simultaneously inflates family-wise error rate ($1 - (1-\alpha)^m$). OMNIVEX supports:
- **Benjamini–Hochberg (FDR)** *(default)*: Controls false discovery rate without extreme loss of statistical power.
- **Bonferroni**: Family-wise error rate control ($p \times m$).
- **None**: Raw p-values reported alongside.

---

## 5. Reliability Decision Table

Reliability state is determined by a deterministic rule table evaluated in **this exact priority order**:

| Priority | Reliability State | Condition / Rule | Meaning & UI Notice |
|---|---|---|---|
| **1** | `MONITORING_ERROR` | A required computation failed (exception caught and logged). | No conclusion is drawn; computation error reported. |
| **2** | `INSUFFICIENT_DATA` | (a) Incompatible schema (missing columns / type mismatch), OR (b) incoming samples $< N_{\min}$ (30) AND labels absent or too few. | Sample size is inadequate to reliably assert drift or evaluate performance. |
| **3** | `DRIFT_AND_PERFORMANCE_DEGRADATION` | Overall drift detected **AND** performance degradation confirmed on labelled batch (Accuracy or F1 drop $>$ tolerance and baseline outside 95% bootstrap CI). | **Critical alert:** Model degradation confirmed alongside significant distribution shift. |
| **4** | `PERFORMANCE_DEGRADATION` | Performance degradation confirmed on labelled batch, but **no** overall input data drift detected. | Accuracy loss without input shift (possible concept drift / change in $P(Y\|X)$). |
| **5** | `DRIFT_DETECTED` | Overall drift detected, AND (a) performance is within tolerance, OR (b) labels are unavailable. | Input shift observed. When labels are unavailable: *"Drift detected – performance impact not confirmed."* |
| **6** | `NORMAL` | No statistically significant drift, AND performance matches baseline (or labels unavailable). | System operating normally within observed parameters. |

---

## 6. Security Model & Residual Risks

### Implemented Controls
1. **Upload Security:**
   - Strict `.csv` extension verification.
   - Streaming size enforcement (`MAX_UPLOAD_SIZE_BYTES`, default 10MB) prevents memory exhaustion.
   - Content inspection rejects binary files (NUL bytes `\x00`) and enforces valid UTF-8.
   - Internal storage uses server-controlled UUID4 filenames (`uuid.uuid4().hex + '.csv'`).
   - `resolve_safe_path` verifies `os.path.commonpath` to strictly prevent directory traversal attacks (`../../`).
2. **Model Safety & Execution Risk:**
   - Serialized pipelines are arbitrary code execution risks. OMNIVEX **never accepts uploaded model files**.
   - Models are created **exclusively** via the internal training endpoint.
   - Every artifact is hashed with SHA-256 upon creation and **verified against its database hash before every load**. Tampered files raise `SecurityViolationError` and refuse execution.
3. **API Key Authentication:**
   - Optional `X-API-Key` authentication verified in constant time (`secrets.compare_digest`).
   - `/api/health` remains open for probes.
4. **Formula Injection Neutralization:**
   - All exported CSV reports sanitize text fields: any cell starting with `=`, `+`, `-`, `@`, `\t`, or `\r` is prepended with `'`.
5. **Rate Limiting & Security Headers:**
   - SlowAPI limits requests per IP (60/min default).
   - Responses enforce `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, `X-Frame-Options: DENY`.
6. **Error Sanitization:**
   - 500 errors return a generic message with a correlation ID; internal tracebacks, paths, and SQL queries are logged to the console only.

### Residual Risks & `pip-audit` Report
A dependency vulnerability audit was executed using `pip-audit`. The real output identified known vulnerabilities in secondary dependencies (e.g. `pillow`, `streamlit`, `starlette`):
```text
Found 29 known vulnerabilities in 5 packages
Name      Version ID              Fix Versions
--------- ------- --------------- ------------
pillow    11.3.0  PYSEC-2026-165  12.2.0
pytest    8.3.5   PYSEC-2026-1845 9.0.3
requests  2.32.5  PYSEC-2026-2275 2.33.0
starlette 0.46.2  PYSEC-2026-161  1.0.1
streamlit 1.42.2  PYSEC-2026-212  1.53.1
```
*Note on Model Deserialization:* While SHA-256 hashing verifies that an artifact has not been modified since creation on disk, Python `joblib`/`pickle` is inherently unsafe against a local root/filesystem attacker who has write access to both the artifact and the SQLite database. For multi-tenant production systems, non-pickle serialization formats (such as ONNX, PMML, or Skops) should be adopted.

---

## 7. Assumptions & Known Limitations

- **Statistical Uncertainty:** Statistical tests inherently carry Type I (false positive) and Type II (false negative) error rates. A $p$-value threshold of $\alpha=0.05$ will flag approximately 5% of stationary features as drifting purely by chance.
- **Label Latency:** In production, ground-truth labels often take weeks or months to arrive. OMNIVEX handles this by treating label absence as a standard operational state rather than an error.
- **SQLite Concurrency:** SQLite is configured with WAL mode and foreign keys enabled. While suitable for academic research and single-server environments, concurrent high-throughput write workloads should migrate to PostgreSQL (Alembic migration would be recommended).

---

## 8. Setup and Execution (Windows Command Prompt)

### Prerequisites
- Python 3.10+ (Recommended: Python 3.11)
- Windows Command Prompt (`cmd`) or PowerShell

### Step-by-Step Instructions
