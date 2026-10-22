/**
 * OMNIVEX API Client
 * The ONLY module that calls window.fetch.
 * Returns consistent ApiResult objects: { ok, data, error: { code, message, details }, status, elapsedMs }
 */

import { API_CONFIG, getApiBaseUrl } from "./config.js";

export class OmnivexClient {
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || getApiBaseUrl()).replace(/\/+$/, "");
    this.apiKey = options.apiKey || null;
    this.timeoutMs = options.timeoutMs || API_CONFIG.REQUEST_TIMEOUT_MS;
    this.lastSuccessfulRequest = null;
  }

  setApiKey(key) {
    this.apiKey = key || null;
  }

  getApiKey() {
    return this.apiKey;
  }

  /**
   * Internal validation of URL path parameters (IDs) to prevent path traversal or injection.
   */
  _validatePathId(id, paramName = "ID") {
    if (!id || typeof id !== "string") {
      return { ok: false, error: `${paramName} must be a non-empty string.` };
    }
    const trimmed = id.trim();
    if (trimmed.length > API_CONFIG.MAX_ID_LENGTH) {
      return { ok: false, error: `${paramName} length exceeds maximum allowed limit.` };
    }
    if (trimmed.includes("..") || trimmed.toLowerCase().includes("%2e%2e") || trimmed.includes("/") || trimmed.includes("\\")) {
      return { ok: false, error: `Malicious or invalid characters detected in ${paramName}.` };
    }
    return { ok: true, cleanId: trimmed };
  }

  /**
   * Primary HTTP request orchestrator with timeout, retry policy, and normalized ApiResult.
   */
  async _request(endpoint, {
    method = "GET",
    headers = {},
    body = null,
    isFormData = false,
    retryCount = 0,
  } = {}) {
    const url = `${this.baseUrl}${API_CONFIG.API_PREFIX}${endpoint}`;
    const startTime = Date.now();

    const requestHeaders = { ...headers };
    if (!isFormData && body && !requestHeaders["Content-Type"]) {
      requestHeaders["Content-Type"] = "application/json";
    }

    if (this.apiKey) {
      requestHeaders["X-API-Key"] = this.apiKey;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        method,
        headers: requestHeaders,
        body: isFormData ? body : (body ? JSON.stringify(body) : null),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      const elapsedMs = Date.now() - startTime;

      let responseData = null;
      const contentType = response.headers.get("content-type") || "";

      if (contentType.includes("application/json")) {
        try {
          responseData = await response.json();
        } catch {
          responseData = null;
        }
      } else {
        try {
          responseData = await response.text();
        } catch {
          responseData = null;
        }
      }

      if (response.ok) {
        this.lastSuccessfulRequest = {
          endpoint,
          method,
          status: response.status,
          timestamp: new Date().toISOString(),
          elapsedMs,
        };

        return {
          ok: true,
          data: responseData,
          error: null,
          status: response.status,
          elapsedMs,
        };
      }

      // Handle non-2xx responses
      let errorCode = `HTTP_${response.status}`;
      let errorMessage = response.statusText || "Request failed";
      let errorDetails = [];

      if (responseData && typeof responseData === "object") {
        if (responseData.error && typeof responseData.error === "object") {
          errorCode = responseData.error.code || errorCode;
          errorMessage = responseData.error.message || errorMessage;
          errorDetails = Array.isArray(responseData.error.details) ? responseData.error.details : [];
        } else if (responseData.detail) {
          if (Array.isArray(responseData.detail)) {
            // FastAPI validation errors
            errorCode = "VALIDATION_ERROR";
            errorMessage = "One or more fields failed validation.";
            errorDetails = responseData.detail.map((d) => `${d.loc ? d.loc.join(".") + ": " : ""}${d.msg}`);
          } else if (typeof responseData.detail === "string") {
            errorMessage = responseData.detail;
          }
        }
      }

      // Map common statuses to clear operator messages
      if (response.status === 401 || response.status === 403) {
        errorCode = "UNAUTHORIZED";
        errorMessage = "Invalid or missing API Key. Please verify your credentials in System or Login.";
      } else if (response.status === 404) {
        errorCode = "NOT_FOUND";
        errorMessage = errorMessage || "Requested resource was not found.";
      } else if (response.status === 413) {
        errorCode = "PAYLOAD_TOO_LARGE";
        errorMessage = "Uploaded file or payload exceeds backend size limit (10 MB).";
      } else if (response.status === 415) {
        errorCode = "UNSUPPORTED_MEDIA_TYPE";
        errorMessage = "File type not supported. Please upload valid CSV files.";
      } else if (response.status === 429) {
        errorCode = "RATE_LIMITED";
        const retryAfter = response.headers.get("retry-after") || "10";
        errorMessage = `Rate limit exceeded. Please retry after ${retryAfter} seconds.`;
      } else if (response.status >= 500) {
        errorCode = "SERVER_ERROR";
        errorMessage = "The backend encountered an internal error. Check server logs.";
      }

      return {
        ok: false,
        data: null,
        error: {
          code: errorCode,
          message: errorMessage,
          details: errorDetails,
        },
        status: response.status,
        elapsedMs,
      };
    } catch (err) {
      clearTimeout(timeoutId);
      const elapsedMs = Date.now() - startTime;

      // Handle GET retries on transient network disconnects
      if (method === "GET" && retryCount < API_CONFIG.MAX_GET_RETRIES && err.name !== "AbortError") {
        const backoff = API_CONFIG.RETRY_BACKOFF_BASE_MS * Math.pow(2, retryCount);
        await new Promise((res) => setTimeout(res, backoff));
        return this._request(endpoint, {
          method,
          headers,
          body,
          isFormData,
          retryCount: retryCount + 1,
        });
      }

      let errorCode = "NETWORK_ERROR";
      let errorMessage = "Unable to connect to the OMNIVEX backend. Check that the server is running.";

      if (err.name === "AbortError") {
        errorCode = "TIMEOUT";
        errorMessage = `Request timed out after ${this.timeoutMs / 1000} seconds.`;
      }

      return {
        ok: false,
        data: null,
        error: {
          code: errorCode,
          message: errorMessage,
          details: [err.message || String(err)],
        },
        status: 0,
        elapsedMs,
      };
    }
  }

  // --- 1. HEALTH & FOUNDATION ---
  async health() {
    return this._request("/health", { method: "GET" });
  }

  // --- 2. DATASETS ---
  async listDatasets({ role = null, limit = API_CONFIG.DEFAULT_PAGE_LIMIT, offset = 0 } = {}) {
    const params = new URLSearchParams();
    if (role) params.set("role", role);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    return this._request(`/datasets?${params.toString()}`, { method: "GET" });
  }

  async getDataset(datasetId) {
    const check = this._validatePathId(datasetId, "Dataset ID");
    if (!check.ok) {
      return { ok: false, data: null, error: { code: "INVALID_INPUT", message: check.error, details: [] }, status: 400, elapsedMs: 0 };
    }
    return this._request(`/datasets/${check.cleanId}`, { method: "GET" });
  }

  async uploadDataset(file, role = "reference") {
    if (!file) {
      return { ok: false, data: null, error: { code: "INVALID_INPUT", message: "A CSV file is required for upload.", details: [] }, status: 400, elapsedMs: 0 };
    }
    const formData = new FormData();
    formData.append("file", file);
    formData.append("role", role);
    return this._request("/datasets/upload", {
      method: "POST",
      body: formData,
      isFormData: true,
    });
  }

  async validateIncomingDataset(referenceId, incomingId, targetColumn = null) {
    const checkRef = this._validatePathId(referenceId, "Reference Dataset ID");
    const checkInc = this._validatePathId(incomingId, "Incoming Dataset ID");
    if (!checkRef.ok) return { ok: false, data: null, error: { code: "INVALID_INPUT", message: checkRef.error, details: [] }, status: 400, elapsedMs: 0 };
    if (!checkInc.ok) return { ok: false, data: null, error: { code: "INVALID_INPUT", message: checkInc.error, details: [] }, status: 400, elapsedMs: 0 };

    const query = targetColumn ? `?target_column=${encodeURIComponent(targetColumn)}` : "";
    return this._request(`/datasets/${checkRef.cleanId}/validate-incoming/${checkInc.cleanId}${query}`, {
      method: "POST",
    });
  }

  // --- 3. MODELS ---
  async listModels({ limit = API_CONFIG.DEFAULT_PAGE_LIMIT, offset = 0 } = {}) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this._request(`/models?${params.toString()}`, { method: "GET" });
  }

  async getModel(modelId) {
    const check = this._validatePathId(modelId, "Model ID");
    if (!check.ok) {
      return { ok: false, data: null, error: { code: "INVALID_INPUT", message: check.error, details: [] }, status: 400, elapsedMs: 0 };
    }
    return this._request(`/models/${check.cleanId}`, { method: "GET" });
  }

  async trainModel(payload) {
    if (!payload || !payload.name || !payload.dataset_id || !payload.target_column) {
      return { ok: false, data: null, error: { code: "INVALID_INPUT", message: "Model name, dataset ID, and target column are required.", details: [] }, status: 400, elapsedMs: 0 };
    }
    return this._request("/models/train", {
      method: "POST",
      body: payload,
    });
  }

  async predictModel(modelId, datasetId) {
    const check = this._validatePathId(modelId, "Model ID");
    if (!check.ok) return { ok: false, data: null, error: { code: "INVALID_INPUT", message: check.error, details: [] }, status: 400, elapsedMs: 0 };
    return this._request(`/models/${check.cleanId}/predict`, {
      method: "POST",
      body: { dataset_id: datasetId },
    });
  }

  // --- 4. MONITORING (DRIFT & PERFORMANCE) ---
  async runDrift(payload) {
    if (!payload || !payload.reference_dataset_id || !payload.incoming_dataset_id) {
      return { ok: false, data: null, error: { code: "INVALID_INPUT", message: "Reference and incoming dataset IDs are required.", details: [] }, status: 400, elapsedMs: 0 };
    }
    return this._request("/monitor/drift", {
      method: "POST",
      body: payload,
    });
  }

  async runPerformance(payload) {
    if (!payload || !payload.model_id || !payload.dataset_id) {
      return { ok: false, data: null, error: { code: "INVALID_INPUT", message: "Model ID and dataset ID are required.", details: [] }, status: 400, elapsedMs: 0 };
    }
    return this._request("/monitor/performance", {
      method: "POST",
      body: payload,
    });
  }

  async runMonitoringCycle(payload) {
    return this._request("/monitor/run", {
      method: "POST",
      body: payload,
    });
  }

  async getMonitoringSummary() {
    return this._request("/monitor/summary", { method: "GET" });
  }

  // --- 5. ALERTS ---
  async listAlerts({ severity = null, alertType = null, acknowledged = null, runId = null, limit = API_CONFIG.DEFAULT_PAGE_LIMIT, offset = 0 } = {}) {
    const params = new URLSearchParams();
    if (severity) params.set("severity", severity);
    if (alertType) params.set("alert_type", alertType);
    if (acknowledged !== null) params.set("acknowledged", String(acknowledged));
    if (runId) params.set("run_id", runId);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    return this._request(`/alerts?${params.toString()}`, { method: "GET" });
  }

  async acknowledgeAlert(alertId, acknowledgedBy = "researcher") {
    const check = this._validatePathId(alertId, "Alert ID");
    if (!check.ok) return { ok: false, data: null, error: { code: "INVALID_INPUT", message: check.error, details: [] }, status: 400, elapsedMs: 0 };
    return this._request(`/alerts/${check.cleanId}/acknowledge`, {
      method: "PATCH",
      body: { acknowledged_by: acknowledgedBy },
    });
  }

  // --- 6. EXPERIMENTS ---
  async createExperiment(payload) {
    if (!payload || !payload.name || !payload.reference_dataset_id || !payload.incoming_dataset_id) {
      return { ok: false, data: null, error: { code: "INVALID_INPUT", message: "Experiment name, reference dataset, and incoming dataset are required.", details: [] }, status: 400, elapsedMs: 0 };
    }
    return this._request("/experiments", {
      method: "POST",
      body: payload,
    });
  }

  async listExperiments({ limit = API_CONFIG.DEFAULT_PAGE_LIMIT, offset = 0 } = {}) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this._request(`/experiments?${params.toString()}`, { method: "GET" });
  }

  async getExperiment(experimentId) {
    const check = this._validatePathId(experimentId, "Experiment ID");
    if (!check.ok) return { ok: false, data: null, error: { code: "INVALID_INPUT", message: check.error, details: [] }, status: 400, elapsedMs: 0 };
    return this._request(`/experiments/${check.cleanId}`, { method: "GET" });
  }

  async exportExperiment(experimentId, format = "csv") {
    const check = this._validatePathId(experimentId, "Experiment ID");
    if (!check.ok) return { ok: false, data: null, error: { code: "INVALID_INPUT", message: check.error, details: [] }, status: 400, elapsedMs: 0 };
    return this._request(`/experiments/${check.cleanId}/export?format=${encodeURIComponent(format)}`, {
      method: "GET",
    });
  }
}

// Default singleton instance
export const apiClient = new OmnivexClient();
