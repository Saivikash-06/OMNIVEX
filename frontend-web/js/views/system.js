/**
 * OMNIVEX System View
 * Operational health, backend latency audit, API key credential manager, and security verification.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";
import { store } from "../core/store.js";
import { apiClient } from "../api/client.js";
import { getApiBaseUrl, setApiBaseUrl } from "../api/config.js";
import { renderMetricCard } from "../components/metricCard.js";
import { renderLoading, renderError } from "../components/states.js";

export async function renderSystem(container) {
  dom.clear(container);

  const intro = dom.el("div", { className: "view-intro" },
    dom.el("h2", { text: "System Status & Configuration" },
      dom.el("span", {
        style: { fontSize: "0.85rem", fontWeight: "normal", color: "var(--text-muted)", marginLeft: "0.75rem" },
        text: "Backend health, security headers, and credential management"
      })
    ),
    dom.el("p", { text: "Monitor backend server connectivity, audit operational latency, and manage researcher authentication keys." })
  );
  container.appendChild(intro);

  const contentArea = dom.el("div", { id: "system-content" });
  contentArea.appendChild(renderLoading("Probing backend health endpoint..."));
  container.appendChild(contentArea);

  // Probe health
  const healthRes = await apiClient.health();
  dom.clear(contentArea);

  const isOnline = healthRes.ok && healthRes.data?.status === "ok";

  // 1. Connectivity Status Card
  const connCard = dom.el("div", {
    className: "card",
    style: { borderTop: `4px solid ${isOnline ? "var(--color-teal)" : "var(--color-coral)"}` },
  },
    dom.el("div", { className: "card-header" },
      dom.el("div", {},
        dom.el("div", { className: "card-title", text: "Backend Server Connectivity" }),
        dom.el("div", { className: "card-subtitle", text: `Base Target: ${getApiBaseUrl()}` })
      ),
      dom.el("span", {
        className: `backend-status-pill ${isOnline ? "online" : "offline"}`,
      },
        dom.el("span", { className: "status-dot" }),
        dom.el("span", { text: isOnline ? "ONLINE" : "OFFLINE" })
      )
    ),
    dom.el("div", { className: "grid-4" },
      renderMetricCard({
        label: "REST Status",
        value: isOnline ? "Connected" : "Unreachable",
        theme: isOnline ? "healthy" : "critical",
      }),
      renderMetricCard({
        label: "Round-Trip Latency",
        value: `${healthRes.elapsedMs} ms`,
        theme: "healthy",
      }),
      renderMetricCard({
        label: "Backend Version",
        value: healthRes.data?.version || "—",
        theme: "navy",
      }),
      renderMetricCard({
        label: "Database Connection",
        value: healthRes.data?.database || (isOnline ? "Active" : "—"),
        theme: isOnline ? "healthy" : "critical",
      })
    )
  );
  contentArea.appendChild(connCard);

  // 2. Settings Grid (API Key & Base URL)
  const settingsGrid = dom.el("div", { className: "grid-2" });

  // API Key Management Card
  const keyCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "API Key Management" })
    ),
    dom.el("p", {
      style: { fontSize: "0.85rem", marginBottom: "1rem" },
      text: "If OMNIVEX_API_KEY is configured on the backend, every REST request must supply this secret key in the X-API-Key header.",
    })
  );

  const currentKey = apiClient.getApiKey() || "";
  const keyInput = dom.el("input", {
    type: "password",
    className: "form-control",
    placeholder: "Enter X-API-Key secret",
    value: currentKey,
  });

  const saveKeyBtn = dom.el("button", {
    className: "btn btn-primary btn-sm",
    text: "Update API Key",
    onClick: () => {
      const newKey = keyInput.value.trim() || null;
      apiClient.setApiKey(newKey);
      store.setState({ apiKey: newKey });
      dom.toast("API Key updated in session.", "success");
    },
  });

  const clearKeyBtn = dom.el("button", {
    className: "btn btn-outline btn-sm",
    text: "Clear Key",
    onClick: () => {
      keyInput.value = "";
      apiClient.setApiKey(null);
      store.setState({ apiKey: null });
      dom.toast("API Key removed from session.", "info");
    },
  });

  keyCard.appendChild(dom.el("div", { className: "form-group" },
    dom.el("label", { className: "form-label", text: "Active X-API-Key" }),
    keyInput
  ));
  keyCard.appendChild(dom.el("div", { style: { display: "flex", gap: "0.5rem" } }, saveKeyBtn, clearKeyBtn));
  settingsGrid.appendChild(keyCard);

  // Backend Host Configuration Card
  const hostCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Backend Host Target" })
    ),
    dom.el("p", {
      style: { fontSize: "0.85rem", marginBottom: "1rem" },
      text: "Configure the FastAPI origin URL. Default: http://127.0.0.1:8000.",
    })
  );

  const hostInput = dom.el("input", {
    type: "text",
    className: "form-control",
    value: getApiBaseUrl(),
  });

  const saveHostBtn = dom.el("button", {
    className: "btn btn-primary btn-sm",
    text: "Save & Reconnect",
    onClick: async () => {
      const newHost = hostInput.value.trim();
      if (!newHost) return;
      setApiBaseUrl(newHost);
      apiClient.baseUrl = newHost.replace(/\/+$/, "");
      dom.toast(`Backend host set to ${newHost}`, "info");
      renderSystem(container);
    },
  });

  hostCard.appendChild(dom.el("div", { className: "form-group" },
    dom.el("label", { className: "form-label", text: "Base URL" }),
    hostInput
  ));
  hostCard.appendChild(saveHostBtn);
  settingsGrid.appendChild(hostCard);

  contentArea.appendChild(settingsGrid);

  // 3. Security & Operational Audit Card
  const auditCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Security Hardening Audit" })
    ),
    dom.el("div", { className: "grid-3" },
      dom.el("div", { style: { padding: "0.75rem", backgroundColor: "var(--bg-subtle)", borderRadius: "6px" } },
        dom.el("strong", { style: { color: "var(--color-navy)", fontSize: "0.88rem" }, text: "Security Headers" }),
        dom.el("p", { style: { fontSize: "0.8rem", marginTop: "4px" }, text: "X-Content-Type-Options: nosniff\nX-Frame-Options: DENY\nCache-Control: no-store" })
      ),
      dom.el("div", { style: { padding: "0.75rem", backgroundColor: "var(--bg-subtle)", borderRadius: "6px" } },
        dom.el("strong", { style: { color: "var(--color-navy)", fontSize: "0.88rem" }, text: "Upload Safeguards" }),
        dom.el("p", { style: { fontSize: "0.8rem", marginTop: "4px" }, text: "Strict 10MB chunked streaming; path traversal sanitization; binary null byte rejection." })
      ),
      dom.el("div", { style: { padding: "0.75rem", backgroundColor: "var(--bg-subtle)", borderRadius: "6px" } },
        dom.el("strong", { style: { color: "var(--color-navy)", fontSize: "0.88rem" }, text: "Rate Limiting" }),
        dom.el("p", { style: { fontSize: "0.8rem", marginTop: "4px" }, text: "SlowAPI rate limiter active across API routes with standard 429 Retry-After response headers." })
      )
    )
  );

  // Last successful request audit
  if (apiClient.lastSuccessfulRequest) {
    const last = apiClient.lastSuccessfulRequest;
    auditCard.appendChild(dom.el("div", {
      style: {
        marginTop: "1rem",
        padding: "0.75rem 1rem",
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border-color)",
        borderRadius: "6px",
        fontSize: "0.82rem",
        color: "var(--text-secondary)",
      },
    },
      dom.el("strong", { style: { color: "var(--color-navy)" }, text: "Last Successful API Request: " }),
      dom.el("span", { text: `${last.method} ${last.endpoint} -> HTTP ${last.status} (${last.elapsedMs}ms) at ${format.timeOnly(last.timestamp)}` })
    ));
  }

  contentArea.appendChild(auditCard);
}
