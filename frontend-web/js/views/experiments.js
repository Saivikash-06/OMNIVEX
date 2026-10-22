/**
 * OMNIVEX Experiments View
 * Repeatable research simulation harness, stress testing, and empirical export.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";
import { apiClient } from "../api/client.js";
import { renderTable } from "../components/tables.js";
import { renderReliabilityBadge } from "../components/statusBadge.js";
import { renderMetricCard } from "../components/metricCard.js";
import { renderLoading, renderEmpty, renderError } from "../components/states.js";

export async function renderExperiments(container) {
  dom.clear(container);

  const intro = dom.el("div", { className: "view-intro" },
    dom.el("h2", { text: "Simulated Reliability Experiments" },
      dom.el("span", {
        style: { fontSize: "0.85rem", fontWeight: "normal", color: "var(--text-muted)", marginLeft: "0.75rem" },
        text: "Controlled stress testing under simulated shift dynamics"
      })
    ),
    dom.el("p", { text: "Run repeatable end-to-end monitoring runs across baseline, unlabelled, and macroeconomic shock scenarios. Exports audit-ready CSV/JSON artifacts." })
  );
  container.appendChild(intro);

  // 1. Runner Form Card
  const formCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Configure & Execute Research Experiment" })
    ),
    dom.el("div", { id: "exp-form-slot" })
  );
  container.appendChild(formCard);

  // 2. Results Container
  const resultsContainer = dom.el("div", { id: "exp-results-slot" });
  container.appendChild(resultsContainer);

  // 3. Historical Runs Table Card
  const historyCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Historical Experiment Runs" }),
      dom.el("button", { className: "btn btn-outline btn-sm", text: "Refresh", onClick: () => loadHistoryList() })
    ),
    dom.el("div", { id: "exp-history-slot" })
  );
  container.appendChild(historyCard);

  // Detail Modal Slot
  const modalSlot = dom.el("div", { id: "exp-modal-slot" });
  container.appendChild(modalSlot);

  async function loadExpForm() {
    const formSlot = formCard.querySelector("#exp-form-slot");
    dom.clear(formSlot);
    formSlot.appendChild(renderLoading("Fetching models and datasets..."));

    const [datasetsRes, modelsRes] = await Promise.all([
      apiClient.listDatasets({ limit: 100 }),
      apiClient.listModels({ limit: 100 }),
    ]);
    dom.clear(formSlot);

    if (!datasetsRes.ok || !modelsRes.ok) {
      formSlot.appendChild(renderError({
        message: "Failed to load dependencies.",
        onRetry: () => loadExpForm(),
      }));
      return;
    }

    const datasets = datasetsRes.data.items || [];
    const models = modelsRes.data.items || [];
    const refDatasets = datasets.filter((d) => d.role === "reference");
    const incDatasets = datasets.filter((d) => d.role === "incoming");

    if (refDatasets.length === 0 || incDatasets.length === 0) {
      formSlot.appendChild(dom.el("p", {
        style: { color: "var(--text-muted)", fontSize: "0.88rem" },
        text: "Please ensure at least one 'Reference' and one 'Incoming' dataset exist.",
      }));
      return;
    }

    const nameInput = dom.el("input", {
      type: "text",
      className: "form-control",
      value: "Experiment-EconomicShock-Simulation",
    });

    const scenarioInput = dom.el("input", {
      type: "text",
      className: "form-control",
      value: "economic_shock",
    });

    const refSelect = dom.el("select", { className: "form-select" },
      ...refDatasets.map((d) => dom.el("option", { value: d.id, text: `${d.name} (${d.row_count} rows)` }))
    );

    const incSelect = dom.el("select", { className: "form-select" },
      ...incDatasets.map((d) => dom.el("option", { value: d.id, text: `${d.name} (${d.row_count} rows)` }))
    );

    const modelSelect = dom.el("select", { className: "form-select" },
      dom.el("option", { value: "", text: "None (Drift Only — No Model Evaluation)" }),
      ...models.map((m) => dom.el("option", { value: m.id, text: `${m.name} (${m.algorithm})` }))
    );

    const labelInput = dom.el("input", {
      type: "text",
      className: "form-control",
      value: "loan_default",
    });

    const simTypeSelect = dom.el("select", { className: "form-select" },
      dom.el("option", { value: "none", text: "None (Natural Observed Data)" }),
      dom.el("option", { value: "mean_shift", text: "Mean Shift (Shift numerical feature central tendency)" }),
      dom.el("option", { value: "variance_scale", text: "Variance Scale (Amplify volatility / spread)" }),
      dom.el("option", { value: "categorical_shift", text: "Categorical Shift (Perturb class distribution)" }),
      dom.el("option", { value: "missing_values", text: "Missing Values (Simulate sensor / pipeline outages)" })
    );

    const magInput = dom.el("input", {
      type: "number",
      className: "form-control",
      value: "1.0",
      step: "0.5",
      min: "0.0",
      max: "10.0",
    });

    const runBtn = dom.el("button", {
      className: "btn btn-primary",
      style: { marginTop: "1rem" },
      text: "Execute Full Monitoring Experiment",
      onClick: async () => {
        runBtn.disabled = true;
        runBtn.textContent = "Executing Full Reliability Pipeline...";
        dom.clear(resultsContainer);
        resultsContainer.appendChild(renderLoading("Running schema validation -> drift testing -> inference -> reliability evaluation..."));

        const payload = {
          name: nameInput.value.trim() || "Experiment-Run",
          scenario: scenarioInput.value.trim() || "baseline",
          reference_dataset_id: refSelect.value,
          incoming_dataset_id: incSelect.value,
          model_id: modelSelect.value || null,
          label_column: labelInput.value.trim() || null,
          simulation: {
            simulation_type: simTypeSelect.value,
            magnitude: parseFloat(magInput.value) || 1.0,
            seed: 42,
          },
          ks_alpha: 0.05,
          ks_min_effect: 0.10,
          multiple_testing_method: "benjamini_hochberg",
          drift_ratio_threshold: 0.30,
          performance_drop_tolerance: 0.05,
          random_seed: 42,
        };

        const res = await apiClient.createExperiment(payload);
        runBtn.disabled = false;
        runBtn.textContent = "Execute Full Monitoring Experiment";
        dom.clear(resultsContainer);

        if (!res.ok) {
          resultsContainer.appendChild(renderError({
            title: "Experiment Execution Error",
            message: res.error.message,
            details: res.error.details,
          }));
          return;
        }

        renderExperimentResult(resultsContainer, res.data);
        loadHistoryList();
      },
    });

    const formGrid = dom.el("div", { className: "grid-3" },
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Experiment Name" }),
        nameInput
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Scenario Tag" }),
        scenarioInput
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Ground-Truth Label Column" }),
        labelInput
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Reference Dataset (Baseline)" }),
        refSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Incoming Dataset (Stream)" }),
        incSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "AI Model (Optional)" }),
        modelSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Synthetic Shift Simulation" }),
        simTypeSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Simulation Magnitude" }),
        magInput
      )
    );

    formSlot.appendChild(formGrid);
    formSlot.appendChild(runBtn);
  }

  function renderExperimentResult(target, exp) {
    const rel = exp.reliability;
    const meta = format.reliabilityState(rel.reliability_state);

    const resultCard = dom.el("div", {
      className: "card",
      style: { borderTop: `4px solid ${meta.color}` },
    },
      dom.el("div", { className: "card-header" },
        dom.el("div", {},
          dom.el("div", { className: "card-title", text: `Experiment Result: ${exp.name}` }),
          dom.el("div", { className: "card-subtitle", text: `Scenario: ${exp.scenario} • Run ID: ${exp.run_id}` })
        ),
        renderReliabilityBadge(rel.reliability_state)
      ),
      dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "1rem" } },
        dom.el("p", { style: { fontSize: "1rem", fontWeight: "600", color: "var(--color-navy)" }, text: meta.description }),
        rel.reasons && rel.reasons.length > 0 ? dom.el("div", {
          style: {
            backgroundColor: "var(--bg-subtle)",
            padding: "0.75rem 1rem",
            borderRadius: "6px",
            fontSize: "0.85rem",
          },
        },
          dom.el("strong", { text: "Evaluation Reasons: " }),
          dom.el("span", { text: rel.reasons.join(" | ") })
        ) : null,
        dom.el("div", { className: "grid-4" },
          renderMetricCard({
            label: "Drift Detected",
            value: rel.drift_detected ? "YES" : "NO",
            theme: rel.drift_detected ? "warning" : "healthy",
          }),
          renderMetricCard({
            label: "Performance Degradation",
            value: rel.performance_degradation_confirmed ? "CONFIRMED" : "NONE",
            theme: rel.performance_degradation_confirmed ? "critical" : "healthy",
          }),
          renderMetricCard({
            label: "Triggered Alerts",
            value: exp.alerts?.length || 0,
            theme: (exp.alerts?.length || 0) > 0 ? "critical" : "healthy",
          }),
          renderMetricCard({
            label: "Execution Latency",
            value: `${exp.execution_time_ms.toFixed(1)} ms`,
            theme: "navy",
          })
        ),
        dom.el("div", { style: { display: "flex", gap: "0.75rem", marginTop: "0.5rem" } },
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "Download Findings (CSV)",
            onClick: () => downloadExport(exp.experiment_id, "csv"),
          }),
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "Download Findings (JSON)",
            onClick: () => downloadExport(exp.experiment_id, "json"),
          })
        )
      )
    );

    target.appendChild(resultCard);
  }

  async function loadHistoryList() {
    const historySlot = historyCard.querySelector("#exp-history-slot");
    dom.clear(historySlot);
    historySlot.appendChild(renderLoading("Fetching past experiments..."));

    const res = await apiClient.listExperiments({ limit: 100 });
    dom.clear(historySlot);

    if (!res.ok) {
      historySlot.appendChild(renderError({
        message: res.error.message,
        onRetry: () => loadHistoryList(),
      }));
      return;
    }

    const items = res.data.items || [];
    if (items.length === 0) {
      historySlot.appendChild(renderEmpty({
        title: "No experiment records found",
        description: "Run your first simulation above to log experiment audits.",
      }));
      return;
    }

    const columns = [
      { key: "name", label: "Experiment Name", sortable: true },
      { key: "scenario", label: "Scenario", sortable: true },
      {
        key: "is_simulation",
        label: "Synthetic Simulation",
        sortable: true,
        render: (row) => dom.el("span", {
          className: `status-badge ${row.is_simulation ? "status-DRIFT_DETECTED" : "status-NORMAL"}`,
          text: row.is_simulation ? "SIMULATED" : "NATURAL",
        }),
      },
      {
        key: "status",
        label: "Status",
        sortable: true,
        render: (row) => dom.el("span", { className: "status-badge status-NORMAL", text: row.status.toUpperCase() }),
      },
      {
        key: "created_at",
        label: "Executed",
        sortable: true,
        render: (row) => format.date(row.created_at),
      },
      {
        key: "actions",
        label: "Actions",
        render: (row) => dom.el("div", { style: { display: "flex", gap: "0.4rem" } },
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "Inspect",
            onClick: () => showExperimentModal(row.id),
          }),
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "CSV",
            onClick: () => downloadExport(row.id, "csv"),
          })
        ),
      },
    ];

    historySlot.appendChild(renderTable({
      columns,
      rows: items,
    }));
  }

  async function showExperimentModal(expId) {
    const modalSlot = container.querySelector("#exp-modal-slot");
    dom.clear(modalSlot);

    const loadingModal = dom.el("div", { className: "modal-backdrop" },
      dom.el("div", { className: "modal-content", style: { padding: "2rem" } },
        renderLoading("Fetching experiment record...")
      )
    );
    modalSlot.appendChild(loadingModal);

    const res = await apiClient.getExperiment(expId);
    dom.clear(modalSlot);

    if (!res.ok) {
      dom.toast(`Could not load experiment: ${res.error.message}`, "error");
      return;
    }

    const data = res.data;
    const exp = data.experiment;
    const run = data.run;

    const modal = dom.el("div", { className: "modal-backdrop" },
      dom.el("div", { className: "modal-content", style: { maxWidth: "700px" } },
        dom.el("div", { className: "modal-header" },
          dom.el("div", {},
            dom.el("h3", { className: "modal-title", text: exp.name }),
            dom.el("span", { style: { fontSize: "0.8rem", color: "var(--text-muted)" }, text: `Scenario: ${exp.scenario} • ID: ${exp.id}` })
          ),
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "✕",
            onClick: () => dom.clear(modalSlot),
          })
        ),
        dom.el("div", { className: "modal-body", style: { display: "flex", flexDirection: "column", gap: "1rem" } },
          dom.el("div", { style: { display: "flex", alignItems: "center", gap: "0.75rem" } },
            dom.el("strong", { text: "Reliability State: " }),
            renderReliabilityBadge(run?.reliability_state || "UNKNOWN")
          ),
          run?.reasons && run.reasons.length > 0 ? dom.el("div", {
            style: { backgroundColor: "var(--bg-subtle)", padding: "0.75rem", borderRadius: "6px", fontSize: "0.85rem" },
          },
            dom.el("strong", { text: "Reasons: " }),
            dom.el("span", { text: run.reasons.join(" | ") })
          ) : null,
          dom.el("div", { style: { fontSize: "0.85rem", color: "var(--text-secondary)" } },
            dom.el("div", {}, `Drift Detected: ${run?.drift_detected ? "Yes" : "No"}`),
            dom.el("div", {}, `Performance Status: ${run?.performance_status || "N/A"}`),
            dom.el("div", {}, `Random Seed: ${exp.random_seed}`),
            dom.el("div", {}, `Executed At: ${format.date(exp.created_at)}`)
          )
        ),
        dom.el("div", { className: "modal-footer" },
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "Download CSV",
            onClick: () => downloadExport(exp.id, "csv"),
          }),
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

  function downloadExport(expId, format) {
    const url = `${apiClient.baseUrl}/api/experiments/${expId}/export?format=${format}`;
    window.open(url, "_blank");
  }

  // Initial load
  loadExpForm();
  loadHistoryList();
}
