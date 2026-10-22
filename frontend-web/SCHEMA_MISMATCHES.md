# OMNIVEX Frontend Web v3: Backend Contract Audit & Schema Mismatches

**Audited Backend Version**: `2.0.0` (FastAPI + Pydantic v2)  
**Host Target**: `http://127.0.0.1:8000/api`  
**OpenAPI Specification**: Audited via `/api/openapi.json` and `backend/app/schemas/`

---

## 1. Authentication & Security Headers

| Backend Rule | Implementation Details | Frontend Adaptation |
| :--- | :--- | :--- |
| **Optional API Key** | `require_api_key` checks `X-API-Key` only if `OMNIVEX_API_KEY` is configured in `.env` / environment. | `index.html` and `System` view provide an optional `X-API-Key` input. If omitted and backend requires it, API client captures `401 Unauthorized` and displays a clear credential error. |
| **Key Transmission** | Header alias: `X-API-Key` | Handled strictly via request headers in `OmnivexClient._request`. Never passed in query strings or logged to console. |
| **CORS Origins** | `CORS_ORIGINS` in `config.py` configured for local development servers (`http://localhost:3000`, `8080`, `5000`, `5500`, `8501`). | Web server can be run from any standard development port (e.g. `python -m http.server 3000`). |

---

## 2. Endpoint Contracts & Response Shapes

### A. Monitoring Summary (`GET /api/monitor/summary`)
- **Expected Shape**: `{ run_id, experiment_id, reliability_state, drift_detected, performance_status, reasons, execution_time_ms, created_at }`
- **Observed Behavior When No Runs Exist**: Returns HTTP `404 Not Found` (`NotFoundError: Monitoring Run latest not found`).
- **Frontend Adaptation**: Handled gracefully in `overview.js`. If 404 is returned, the hero banner presents a clean default state: *"No monitoring runs executed yet. Run an experiment or monitoring cycle to record system health."*

### B. Pagination Format (`GET /api/datasets`, `GET /api/models`, `GET /api/alerts`, `GET /api/experiments`)
- **Expected Shape**: Generic `PaginatedResponse[T]` schema:
  ```json
  {
    "items": [...],
    "total": 12,
    "limit": 50,
    "offset": 0
  }
  ```
- **Observed Alignment**: All four collection endpoints adhere directly to `{ items, total, limit, offset }`.
- **Frontend Adaptation**: Handled natively by `renderTable` in `js/components/tables.js`.

### C. Error Response Normalization
- **Backend Shapes**:
  1. Internal AppError: `{"error": {"code": "...", "message": "...", "details": [...]}}`
  2. FastAPI Validation: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`
  3. Starlette HTTP errors: `{"detail": "..."}` or plain text
- **Frontend Adaptation**: `OmnivexClient._request()` maps all three formats into a uniform structure:
  ```js
  {
    ok: false,
    data: null,
    error: {
      code: "VALIDATION_ERROR" | "NOT_FOUND" | "RATE_LIMITED" | "SERVER_ERROR" | ...,
      message: "Human-readable description",
      details: ["loc: msg", ...]
    },
    status: 422,
    elapsedMs: 14
  }
  ```

### D. Single Experiment Retrieval (`GET /api/experiments/{id}`)
- **Backend Schema**: Returns `{ "experiment": { ... }, "run": { ... } }` rather than a flat object.
- **Frontend Adaptation**: `showExperimentModal()` in `js/views/experiments.js` unpacks `data.experiment` and `data.run` separately.

### E. Dataset Upload (`POST /api/datasets/upload`)
- **Backend Expectation**: `multipart/form-data` with fields `file` (UploadFile) and `role` (`reference` or `incoming`).
- **Frontend Adaptation**: `uploadDataset()` builds a native `FormData` instance with `isFormData: true`, letting the browser set the boundary header automatically.
