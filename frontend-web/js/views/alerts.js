/**
 * OMNIVEX Alerts View
 * Reliability alerts lifecycle management, severity filtering, and acknowledgement audit log.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";
import { apiClient } from "../api/client.js";
import { renderTable } from "../components/tables.js";
import { renderAlertSeverityBadge } from "../components/statusBadge.js";
import { renderLoading, renderEmpty, renderError } from "../components/states.js";

export async function renderAlerts(container) {
  dom.clear(container);

  const intro = dom.el("div", { className: "view-intro" },
    dom.el("h2", { text: "Operational Reliability Alerts" },
      dom.el("span", {
        style: { fontSize: "0.85rem", fontWeight: "normal", color: "var(--text-muted)", marginLeft: "0.75rem" },
        text: "Lifecycle-managed notifications for drift and performance drops"
      })
    ),
    dom.el("p", { text: "Alerts are automatically triggered during monitoring cycles. They feature deduplication, priority capping, and operator acknowledgement audit trails." })
  );
  container.appendChild(intro);

  // 1. Filter Bar Card
  const filterCard = dom.el("div", { className: "card", style: { padding: "1rem 1.25rem" } });
  const filterRow = dom.el("div", {
    style: { display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" },
  });

  const severitySelect = dom.el("select", { className: "form-select", style: { width: "auto" } },
    dom.el("option", { value: "", text: "All Severities" }),
    dom.el("option", { value: "critical", text: "Critical Only" }),
    dom.el("option", { value: "warning", text: "Warning Only" }),
    dom.el("option", { value: "info", text: "Info Only" })
  );

  const statusSelect = dom.el("select", { className: "form-select", style: { width: "auto" } },
    dom.el("option", { value: "false", text: "Active / Unacknowledged" }),
    dom.el("option", { value: "true", text: "Acknowledged Only" }),
    dom.el("option", { value: "", text: "All Statuses" })
  );

  const filterBtn = dom.el("button", {
    className: "btn btn-outline btn-sm",
    text: "Filter Alerts",
    onClick: () => loadAlertsList(),
  });

  filterRow.appendChild(dom.el("span", { style: { fontWeight: "600", fontSize: "0.88rem", color: "var(--color-navy)" }, text: "Filters:" }));
  filterRow.appendChild(severitySelect);
  filterRow.appendChild(statusSelect);
  filterRow.appendChild(filterBtn);
  filterCard.appendChild(filterRow);
  container.appendChild(filterCard);

  // 2. Alerts Table Card
  const tableCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Alert Audit Log" }),
      dom.el("button", { className: "btn btn-outline btn-sm", text: "Refresh", onClick: () => loadAlertsList() })
    ),
    dom.el("div", { id: "alerts-table-slot" })
  );
  container.appendChild(tableCard);

  // Modal Slot
  const modalSlot = dom.el("div", { id: "alert-modal-slot" });
  container.appendChild(modalSlot);

  async function loadAlertsList() {
    const tableSlot = tableCard.querySelector("#alerts-table-slot");
    dom.clear(tableSlot);
    tableSlot.appendChild(renderLoading("Fetching alerts..."));

    const severityVal = severitySelect.value || null;
    const statusVal = statusSelect.value === "" ? null : (statusSelect.value === "true");

    const res = await apiClient.listAlerts({
      severity: severityVal,
      acknowledged: statusVal,
      limit: 100,
    });
    dom.clear(tableSlot);

    if (!res.ok) {
      tableSlot.appendChild(renderError({
        message: res.error.message,
        onRetry: () => loadAlertsList(),
      }));
      return;
    }

    const alerts = res.data.items || [];
    if (alerts.length === 0) {
      tableSlot.appendChild(renderEmpty({
        title: "No alerts match criteria",
        description: "No reliability alerts found under the current filter settings.",
      }));
      return;
    }

    const columns = [
      {
        key: "severity",
        label: "Severity",
        sortable: true,
        render: (row) => renderAlertSeverityBadge(row.severity),
      },
      {
        key: "affected_feature_or_metric",
        label: "Affected Feature / Metric",
        sortable: true,
        render: (row) => dom.el("strong", { style: { color: "var(--color-navy)" }, text: row.affected_feature_or_metric }),
      },
      {
        key: "alert_type",
        label: "Type",
        sortable: true,
        render: (row) => dom.el("span", {
          style: { fontSize: "0.8rem", color: "var(--text-muted)" },
          text: row.alert_type.replace(/_/g, " "),
        }),
      },
      {
        key: "explanation",
        label: "Explanation",
        render: (row) => dom.el("div", { style: { maxWidth: "340px", fontSize: "0.85rem" }, text: row.explanation }),
      },
      {
        key: "timestamp",
        label: "Timestamp",
        sortable: true,
        render: (row) => format.date(row.timestamp),
      },
      {
        key: "acknowledged",
        label: "Status",
        sortable: true,
        render: (row) => {
          if (row.acknowledged) {
            return dom.el("span", {
              className: "status-badge status-NORMAL",
              title: `Ack by ${row.acknowledged_by || "operator"} at ${format.date(row.acknowledged_at)}`,
              text: `ACKNOWLEDGED`,
            });
          }
          return dom.el("span", { className: "status-badge status-DRIFT_DETECTED", text: "ACTIVE" });
        },
      },
      {
        key: "actions",
        label: "Actions",
        render: (row) => {
          const actionGroup = dom.el("div", { style: { display: "flex", gap: "0.4rem" } });

          if (!row.acknowledged) {
            actionGroup.appendChild(dom.el("button", {
              className: "btn btn-primary btn-sm",
              text: "Acknowledge",
              onClick: async (e) => {
                e.target.disabled = true;
                const ackRes = await apiClient.acknowledgeAlert(row.alert_id);
                if (ackRes.ok) {
                  dom.toast("Alert acknowledged.", "success");
                  loadAlertsList();
                } else {
                  dom.toast(`Failed: ${ackRes.error.message}`, "error");
                }
              },
            }));
          }

          actionGroup.appendChild(dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "Details",
            onClick: () => showAlertModal(row),
          }));

          return actionGroup;
        },
      },
    ];

    tableSlot.appendChild(renderTable({
      columns,
      rows: alerts,
    }));
  }

  function showAlertModal(alert) {
    const modalSlot = container.querySelector("#alert-modal-slot");
    dom.clear(modalSlot);

    const body = dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "1rem" } });

    // Explanation
    body.appendChild(dom.el("div", {},
      dom.el("strong", { text: "Explanation: " }),
      dom.el("p", { style: { marginTop: "0.25rem" }, text: alert.explanation })
    ));

    // Suggested steps
    if (alert.suggested_steps && alert.suggested_steps.length > 0) {
      const stepsList = dom.el("ul", { style: { paddingLeft: "1.25rem", fontSize: "0.88rem", color: "var(--text-secondary)" } });
      for (const step of alert.suggested_steps) {
        stepsList.appendChild(dom.el("li", { text: step }));
      }
      body.appendChild(dom.el("div", {},
        dom.el("strong", { text: "Recommended Operator Steps: " }),
        stepsList
      ));
    }

    // Evidence JSON
    if (alert.evidence) {
      body.appendChild(dom.el("div", {},
        dom.el("strong", { text: "Diagnostic Evidence: " }),
        dom.el("pre", {
          style: {
            backgroundColor: "var(--bg-subtle)",
            padding: "0.75rem",
            borderRadius: "6px",
            maxHeight: "180px",
            overflow: "auto",
            marginTop: "0.25rem",
            fontSize: "0.8rem",
          },
          text: JSON.stringify(alert.evidence, null, 2),
        })
      ));
    }

    const modal = dom.el("div", { className: "modal-backdrop" },
      dom.el("div", { className: "modal-content", style: { maxWidth: "600px" } },
        dom.el("div", { className: "modal-header" },
          dom.el("div", { style: { display: "flex", alignItems: "center", gap: "0.75rem" } },
            renderAlertSeverityBadge(alert.severity),
            dom.el("h3", { className: "modal-title", text: alert.affected_feature_or_metric })
          ),
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "✕",
            onClick: () => dom.clear(modalSlot),
          })
        ),
        dom.el("div", { className: "modal-body" }, body),
        dom.el("div", { className: "modal-footer" },
          dom.el("button", {
            className: "btn btn-secondary btn-sm",
            text: "Close",
            onClick: () => dom.clear(modalSlot),
          })
        )
      )
    );

    modalSlot.appendChild(modal);
  }

  // Initial load
  loadAlertsList();
}
