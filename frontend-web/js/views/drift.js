/**
 * OMNIVEX Drift View
 * Statistical covariate drift detection: KS test, Chi-Square, TVD, Wasserstein with FDR correction.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";
import { apiClient } from "../api/client.js";
import { renderTable } from "../components/tables.js";
import { renderDriftBarChart } from "../components/charts.js";
import { renderLoading, renderError } from "../components/states.js";

export async function renderDrift(container) {
  dom.clear(container);

  const intro = dom.el("div", { className: "view-intro" },
    dom.el("h2", { text: "Statistical Data Drift Detection" },
      dom.el("span", {
        style: { fontSize: "0.85rem", fontWeight: "normal", color: "var(--text-muted)", marginLeft: "0.75rem" },
        text: "Two-sample testing with False Discovery Rate correction"
      })
    ),
    dom.el("p", { text: "Detects feature distribution shifts between baseline reference data and incoming production streams using Kolmogorov-Smirnov, Chi-Square, and Wasserstein distances." })
  );
  container.appendChild(intro);

  // 1. Controls Card
  const formCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Drift Analysis Parameters" })
    ),
    dom.el("div", { id: "drift-form-slot" })
  );
  container.appendChild(formCard);

  // 2. Results Container
  const resultsContainer = dom.el("div", { id: "drift-results-slot" });
  container.appendChild(resultsContainer);

  // Load datasets to populate dropdowns
  async function loadDriftForm() {
    const formSlot = formCard.querySelector("#drift-form-slot");
    dom.clear(formSlot);
    formSlot.appendChild(renderLoading("Fetching datasets..."));

    const res = await apiClient.listDatasets({ limit: 100 });
    dom.clear(formSlot);

    if (!res.ok) {
      formSlot.appendChild(renderError({
        message: res.error.message,
        onRetry: () => loadDriftForm(),
      }));
      return;
    }

    const datasets = res.data.items || [];
    const refDatasets = datasets.filter((d) => d.role === "reference");
    const incDatasets = datasets.filter((d) => d.role === "incoming");

    if (refDatasets.length === 0 || incDatasets.length === 0) {
      formSlot.appendChild(dom.el("p", {
        style: { color: "var(--text-muted)", fontSize: "0.88rem" },
        text: "Requires at least one 'Reference' dataset and one 'Incoming' dataset to run drift analysis.",
      }));
      formSlot.appendChild(dom.el("div", { style: { marginTop: "0.5rem" } },
        dom.el("a", { className: "btn btn-outline btn-sm", href: "#/datasets", text: "Go to Datasets" })
      ));
      return;
    }

    const refSelect = dom.el("select", { className: "form-select" },
      ...refDatasets.map((d) => dom.el("option", { value: d.id, text: `${d.name} (${d.row_count} rows)` }))
    );

    const incSelect = dom.el("select", { className: "form-select" },
      ...incDatasets.map((d) => dom.el("option", { value: d.id, text: `${d.name} (${d.row_count} rows)` }))
    );

    const fdrSelect = dom.el("select", { className: "form-select" },
      dom.el("option", { value: "benjamini_hochberg", text: "Benjamini-Hochberg FDR (Recommended for multi-feature controls)" }),
      dom.el("option", { value: "bonferroni", text: "Bonferroni (Strict family-wise error rate)" }),
      dom.el("option", { value: "none", text: "None (Uncorrected p-values)" })
    );

    const alphaInput = dom.el("input", {
      type: "number",
      className: "form-control",
      value: "0.05",
      step: "0.01",
      min: "0.001",
      max: "0.5",
    });

    const runBtn = dom.el("button", {
      className: "btn btn-primary",
      style: { marginTop: "1rem" },
      text: "Run Statistical Drift Analysis",
      onClick: async () => {
        runBtn.disabled = true;
        runBtn.textContent = "Computing Two-Sample Tests...";
        dom.clear(resultsContainer);
        resultsContainer.appendChild(renderLoading("Calculating KS, Chi², and FDR corrections across features..."));

        const res = await apiClient.runDrift({
          reference_dataset_id: refSelect.value,
          incoming_dataset_id: incSelect.value,
          ks_alpha: parseFloat(alphaInput.value) || 0.05,
          ks_min_effect: 0.10,
          psi_moderate: 0.10,
          psi_major: 0.25,
          min_samples: 30,
          multiple_testing_method: fdrSelect.value,
          drift_ratio_threshold: 0.30,
          use_chi_square_for_categorical: true,
        });

        runBtn.disabled = false;
        runBtn.textContent = "Run Statistical Drift Analysis";
        dom.clear(resultsContainer);

        if (!res.ok) {
          resultsContainer.appendChild(renderError({
            title: "Drift Computation Error",
            message: res.error.message,
            details: res.error.details,
          }));
          return;
        }

        renderDriftResults(resultsContainer, res.data);
      },
    });

    const formGrid = dom.el("div", { className: "grid-2" },
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Reference Dataset (Baseline)" }),
        refSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Incoming Dataset (Monitored Stream)" }),
        incSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Multiple Testing Correction Method" }),
        fdrSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Significance Threshold (Alpha)" }),
        alphaInput
      )
    );

    formSlot.appendChild(formGrid);
    formSlot.appendChild(runBtn);
  }

  function renderDriftResults(target, data) {
    const s = data.summary;
    const isDrifted = s.overall_drift_detected;

    // 1. Summary Card
    const summaryCard = dom.el("div", {
      className: "card",
      style: { borderTop: `4px solid ${isDrifted ? "var(--color-amber)" : "var(--color-teal)"}` },
    },
      dom.el("div", { className: "card-header" },
        dom.el("div", {},
          dom.el("div", { className: "card-title", text: "Statistical Drift Summary" }),
          dom.el("div", { className: "card-subtitle", text: s.methodology_note })
        ),
        dom.el("span", {
          className: `status-badge ${isDrifted ? "status-DRIFT_DETECTED" : "status-NORMAL"}`,
          text: isDrifted ? "▲ DRIFT DETECTED" : "● STABLE DISTRIBUTION",
        })
      ),
      dom.el("div", { className: "grid-4" },
        dom.el("div", { className: "metric-card navy" },
          dom.el("div", { className: "metric-label", text: "Features Tested" }),
          dom.el("div", { className: "metric-value", text: s.features_tested })
        ),
        dom.el("div", { className: `metric-card ${s.features_drifted > 0 ? "warning" : "healthy"}` },
          dom.el("div", { className: "metric-label", text: "Drifted Features" }),
          dom.el("div", { className: "metric-value", text: s.features_drifted })
        ),
        dom.el("div", { className: `metric-card ${isDrifted ? "warning" : "healthy"}` },
          dom.el("div", { className: "metric-label", text: "Drift Ratio" }),
          dom.el("div", { className: "metric-value", text: format.percent(s.drift_ratio) })
        ),
        dom.el("div", { className: "metric-card healthy" },
          dom.el("div", { className: "metric-label", text: "Correction Method" }),
          dom.el("div", { style: { fontSize: "1.1rem", fontWeight: "700", color: "var(--color-navy)", marginTop: "4px" }, text: s.multiple_testing_method })
        )
      )
    );
    target.appendChild(summaryCard);

    // 2. Bar Chart Card
    const chartCard = dom.el("div", { className: "card" },
      dom.el("div", { className: "card-header" },
        dom.el("div", { className: "card-title", text: "Distribution Shift Magnitude" })
      ),
      dom.el("div", { id: "drift-chart-container", className: "chart-box" })
    );
    target.appendChild(chartCard);
    renderDriftBarChart(chartCard.querySelector("#drift-chart-container"), data.per_feature_results);

    // 3. Per-Feature Table Card
    const tableCard = dom.el("div", { className: "card" },
      dom.el("div", { className: "card-header" },
        dom.el("div", { className: "card-title", text: "Per-Feature Statistical Breakdown" })
      ),
      dom.el("div", { id: "drift-table-slot" })
    );

    const featureColumns = [
      { key: "feature", label: "Feature Name", sortable: true },
      { key: "feature_type", label: "Type", sortable: true },
      { key: "test_name", label: "Test Applied", sortable: true },
      {
        key: "statistic",
        label: "Statistic",
        sortable: true,
        render: (row) => format.decimal(row.statistic, 4),
      },
      {
        key: "p_value",
        label: "p-value (Raw)",
        sortable: true,
        render: (row) => format.pValue(row.p_value),
      },
      {
        key: "adjusted_p_value",
        label: "p-adj (FDR)",
        sortable: true,
        render: (row) => format.pValue(row.adjusted_p_value),
      },
      {
        key: "status",
        label: "Status",
        sortable: true,
        render: (row) => {
          let badgeClass = "status-NORMAL";
          if (row.status === "drift") badgeClass = "status-DRIFT_DETECTED";
          else if (row.status === "significant_low_effect") badgeClass = "status-DRIFT_DETECTED";
          else if (row.status.startsWith("skipped")) badgeClass = "status-INSUFFICIENT_DATA";
          return dom.el("span", { className: `status-badge ${badgeClass}`, text: row.status.toUpperCase() });
        },
      },
      {
        key: "samples",
        label: "Sample Sizes",
        render: (row) => `Ref: ${row.reference_n} / Inc: ${row.incoming_n}`,
      },
      { key: "note", label: "Diagnostic Note" },
    ];

    tableCard.querySelector("#drift-table-slot").appendChild(renderTable({
      columns: featureColumns,
      rows: data.per_feature_results,
    }));
    target.appendChild(tableCard);
  }

  // Initial load
  loadDriftForm();
}
