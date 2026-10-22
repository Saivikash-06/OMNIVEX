/**
 * OMNIVEX Overview View
 * Mission-control dashboard displaying systemic reliability state, active alerts, and metrics.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";
import { apiClient } from "../api/client.js";
import { renderReliabilityBadge, renderAlertSeverityBadge } from "../components/statusBadge.js";
import { renderMetricCard } from "../components/metricCard.js";
import { renderLoading, renderError, renderOffline } from "../components/states.js";

export async function renderOverview(container) {
  dom.clear(container);

  const intro = dom.el("div", { className: "view-intro" },
    dom.el("h2", { text: "AI Reliability Overview" },
      dom.el("span", {
        style: { fontSize: "0.85rem", fontWeight: "normal", color: "var(--text-muted)", marginLeft: "0.75rem" },
        text: "Real-time model health and distribution monitoring"
      })
    ),
    dom.el("p", { text: "High-level summary of latest monitoring cycles, active reliability states, and operational alerts." })
  );
  container.appendChild(intro);

  const contentArea = dom.el("div", { id: "overview-content" });
  contentArea.appendChild(renderLoading("Fetching system metrics and reliability status..."));
  container.appendChild(contentArea);

  // Fetch summary, datasets, models, and alerts in parallel
  const [summaryRes, datasetsRes, modelsRes, alertsRes] = await Promise.all([
    apiClient.getMonitoringSummary(),
    apiClient.listDatasets({ limit: 100 }),
    apiClient.listModels({ limit: 100 }),
    apiClient.listAlerts({ acknowledged: false, limit: 10 }),
  ]);

  dom.clear(contentArea);

  // If connection completely failed
  if (summaryRes.status === 0 && datasetsRes.status === 0) {
    contentArea.appendChild(renderOffline({
      onRetry: () => renderOverview(container),
    }));
    return;
  }

  // 1. Hero Reliability Status Card
  const heroCard = dom.el("div", { className: "card", style: { borderTop: "4px solid var(--color-teal)" } });
  const heroHeader = dom.el("div", { className: "card-header" },
    dom.el("div", {},
      dom.el("div", { className: "card-title", text: "Latest Reliability State" }),
      dom.el("div", { className: "card-subtitle", text: "Systemic evaluation determined by the 6-state decision hierarchy" })
    ),
    dom.el("div", { id: "hero-badge-slot" })
  );
  heroCard.appendChild(heroHeader);

  const heroBody = dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "0.75rem" } });

  if (summaryRes.ok && summaryRes.data) {
    const s = summaryRes.data;
    heroHeader.querySelector("#hero-badge-slot").appendChild(renderReliabilityBadge(s.reliability_state));

    const meta = format.reliabilityState(s.reliability_state);
    heroCard.style.borderTopColor = meta.color;

    heroBody.appendChild(dom.el("p", {
      style: { fontSize: "1.05rem", color: "var(--color-navy)", fontWeight: "500" },
      text: meta.description,
    }));

    if (s.reasons && s.reasons.length > 0) {
      const reasonBox = dom.el("div", {
        style: {
          backgroundColor: "var(--bg-subtle)",
          padding: "0.75rem 1rem",
          borderRadius: "6px",
          border: "1px solid var(--border-color)",
          fontSize: "0.85rem",
        },
      },
        dom.el("strong", { text: "Evaluation Reasons: " }),
        dom.el("span", { text: s.reasons.join(" | ") })
      );
      heroBody.appendChild(reasonBox);
    }

    const infoRow = dom.el("div", {
      style: { display: "flex", gap: "1.5rem", flexWrap: "wrap", fontSize: "0.82rem", color: "var(--text-muted)", marginTop: "0.25rem" },
    },
      dom.el("span", { text: `Run ID: ${s.run_id}` }),
      dom.el("span", { text: `Drift Detected: ${s.drift_detected ? "Yes" : "No"}` }),
      dom.el("span", { text: `Performance Status: ${s.performance_status}` }),
      dom.el("span", { text: `Timestamp: ${format.date(s.created_at)}` }),
      dom.el("span", { text: `Execution Time: ${s.execution_time_ms} ms` })
    );
    heroBody.appendChild(infoRow);
  } else {
    // No monitoring run executed yet
    heroHeader.querySelector("#hero-badge-slot").appendChild(renderReliabilityBadge("NORMAL"));
    heroBody.appendChild(dom.el("p", {
      text: "No monitoring runs have been executed yet in the database. Run an experiment or monitoring cycle to record system health.",
    }));
    heroBody.appendChild(dom.el("div", { style: { marginTop: "0.5rem" } },
      dom.el("a", { className: "btn btn-primary btn-sm", href: "#/experiments", text: "Go to Experiments & Run Baseline" })
    ));
  }
  heroCard.appendChild(heroBody);
  contentArea.appendChild(heroCard);

  // 2. Metrics Grid
  const totalDatasets = datasetsRes.ok ? datasetsRes.data.total : 0;
  const totalModels = modelsRes.ok ? modelsRes.data.total : 0;
  const activeAlerts = alertsRes.ok ? alertsRes.data.total : 0;

  const metricsGrid = dom.el("div", { className: "grid-4", style: { marginBottom: "1.5rem" } },
    renderMetricCard({
      label: "Registered Datasets",
      value: totalDatasets,
      subtext: "Reference & Incoming streams",
      theme: "navy",
    }),
    renderMetricCard({
      label: "Trained Models",
      value: totalModels,
      subtext: "Baseline classifiers with artifacts",
      theme: "healthy",
    }),
    renderMetricCard({
      label: "Active Alerts",
      value: activeAlerts,
      subtext: activeAlerts > 0 ? "Requires operator attention" : "All clear",
      theme: activeAlerts > 0 ? "critical" : "healthy",
    }),
    renderMetricCard({
      label: "Backend Latency",
      value: `${summaryRes.elapsedMs || datasetsRes.elapsedMs || 0} ms`,
      subtext: "FastAPI REST API",
      theme: "healthy",
    })
  );
  contentArea.appendChild(metricsGrid);

  // 3. Active Alerts and Quick Actions split
  const splitGrid = dom.el("div", { className: "grid-2" });

  // Recent Unacknowledged Alerts
  const alertsCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Active Reliability Alerts" }),
      dom.el("a", { href: "#/alerts", className: "btn btn-outline btn-sm", text: "View All Alerts" })
    )
  );

  if (alertsRes.ok && alertsRes.data.items && alertsRes.data.items.length > 0) {
    const alertsList = dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "0.75rem" } });
    for (const alert of alertsRes.data.items.slice(0, 4)) {
      alertsList.appendChild(dom.el("div", {
        style: {
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          padding: "0.75rem",
          borderRadius: "6px",
          border: "1px solid var(--border-color)",
          backgroundColor: "var(--bg-surface)",
          gap: "0.75rem",
        },
      },
        dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "0.25rem" } },
          dom.el("div", { style: { display: "flex", alignItems: "center", gap: "0.5rem" } },
            renderAlertSeverityBadge(alert.severity),
            dom.el("strong", { style: { fontSize: "0.85rem", color: "var(--color-navy)" }, text: alert.affected_feature_or_metric })
          ),
          dom.el("p", { style: { fontSize: "0.82rem", margin: 0 }, text: alert.explanation })
        ),
        dom.el("button", {
          className: "btn btn-outline btn-sm",
          text: "Ack",
          onClick: async (e) => {
            e.target.disabled = true;
            await apiClient.acknowledgeAlert(alert.alert_id);
            dom.toast("Alert marked as acknowledged.", "success");
            renderOverview(container);
          },
        })
      ));
    }
    alertsCard.appendChild(alertsList);
  } else {
    alertsCard.appendChild(dom.el("div", {
      style: { padding: "1.5rem", textAlign: "center", color: "var(--text-muted)" },
      text: "No active unacknowledged alerts. System is running cleanly.",
    }));
  }
  splitGrid.appendChild(alertsCard);

  // Quick Actions Card
  const actionsCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Quick Operator Actions" })
    ),
    dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "0.75rem" } },
      dom.el("a", {
        href: "#/datasets",
        className: "btn btn-outline",
        style: { justifyContent: "flex-start" },
      }, "📁 Upload Reference or Incoming Dataset"),
      dom.el("a", {
        href: "#/drift",
        className: "btn btn-outline",
        style: { justifyContent: "flex-start" },
      }, "📊 Run Statistical Drift Analysis (KS / Chi² / TVD)"),
      dom.el("a", {
        href: "#/performance",
        className: "btn btn-outline",
        style: { justifyContent: "flex-start" },
      }, "🎯 Evaluate Empirical Performance & Degradation"),
      dom.el("a", {
        href: "#/experiments",
        className: "btn btn-primary",
        style: { justifyContent: "flex-start" },
      }, "🔬 Run Simulated Research Experiment Scenario")
    )
  );
  splitGrid.appendChild(actionsCard);

  contentArea.appendChild(splitGrid);
}
