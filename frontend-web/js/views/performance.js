/**
 * OMNIVEX Performance View
 * Empirical model evaluation and degradation confirmation when ground-truth labels arrive.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";
import { apiClient } from "../api/client.js";
import { renderMetricCard } from "../components/metricCard.js";
import { renderMetricComparison, renderConfusionMatrix } from "../components/charts.js";
import { renderLoading, renderError } from "../components/states.js";

export async function renderPerformance(container) {
  dom.clear(container);

  const intro = dom.el("div", { className: "view-intro" },
    dom.el("h2", { text: "Model Performance & Degradation Tracking" },
      dom.el("span", {
        style: { fontSize: "0.85rem", fontWeight: "normal", color: "var(--text-muted)", marginLeft: "0.75rem" },
        text: "Empirical verification when delayed labels arrive"
      })
    ),
    dom.el("p", { text: "Computes balanced accuracy, macro F1, and bootstrap confidence intervals to confirm whether real-world performance has degraded against baseline tolerances." })
  );
  container.appendChild(intro);

  // 1. Setup Card
  const formCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Performance Evaluation Parameters" })
    ),
    dom.el("div", { id: "perf-form-slot" })
  );
  container.appendChild(formCard);

  // 2. Results Container
  const resultsContainer = dom.el("div", { id: "perf-results-slot" });
  container.appendChild(resultsContainer);

  async function loadPerfForm() {
    const formSlot = formCard.querySelector("#perf-form-slot");
    dom.clear(formSlot);
    formSlot.appendChild(renderLoading("Fetching models and datasets..."));

    const [modelsRes, datasetsRes] = await Promise.all([
      apiClient.listModels({ limit: 50 }),
      apiClient.listDatasets({ limit: 100 }),
    ]);
    dom.clear(formSlot);

    if (!modelsRes.ok || !datasetsRes.ok) {
      formSlot.appendChild(renderError({
        message: "Failed to load models or datasets.",
        onRetry: () => loadPerfForm(),
      }));
      return;
    }

    const models = modelsRes.data.items || [];
    const datasets = datasetsRes.data.items || [];

    if (models.length === 0) {
      formSlot.appendChild(dom.el("p", {
        style: { color: "var(--text-muted)", fontSize: "0.88rem" },
        text: "Please train at least one baseline model before running performance evaluations.",
      }));
      formSlot.appendChild(dom.el("div", { style: { marginTop: "0.5rem" } },
        dom.el("a", { className: "btn btn-outline btn-sm", href: "#/models", text: "Go to Models & Train Baseline" })
      ));
      return;
    }

    const modelSelect = dom.el("select", { className: "form-select" },
      ...models.map((m) => dom.el("option", { value: m.id, text: `${m.name} (${m.algorithm})` }))
    );

    const datasetSelect = dom.el("select", { className: "form-select" },
      ...datasets.map((d) => dom.el("option", { value: d.id, text: `${d.name} (${d.role.toUpperCase()} • ${d.row_count} rows)` }))
    );

    const labelInput = dom.el("input", {
      type: "text",
      className: "form-control",
      placeholder: "e.g., loan_default",
      value: "loan_default",
    });

    const f1Select = dom.el("select", { className: "form-select" },
      dom.el("option", { value: "macro", text: "Macro Averaging (Unweighted mean across classes)" }),
      dom.el("option", { value: "weighted", text: "Weighted Averaging (Support-weighted)" }),
      dom.el("option", { value: "binary", text: "Binary Classification" })
    );

    const toleranceInput = dom.el("input", {
      type: "number",
      className: "form-control",
      value: "0.05",
      step: "0.01",
      min: "0.01",
      max: "0.5",
    });

    const evalBtn = dom.el("button", {
      className: "btn btn-primary",
      style: { marginTop: "1rem" },
      text: "Evaluate Dataset Performance",
      onClick: async () => {
        evalBtn.disabled = true;
        evalBtn.textContent = "Computing Predictions & Bootstrap CIs...";
        dom.clear(resultsContainer);
        resultsContainer.appendChild(renderLoading("Evaluating model predictions against ground truth labels..."));

        const modelId = modelSelect.value;
        const selectedModel = models.find((m) => m.id === modelId);

        const res = await apiClient.runPerformance({
          model_id: modelId,
          dataset_id: datasetSelect.value,
          label_column: labelInput.value.trim() || undefined,
          f1_average: f1Select.value,
          min_samples: 30,
          performance_drop_tolerance: parseFloat(toleranceInput.value) || 0.05,
          bootstrap_resamples: 500,
          random_seed: 42,
        });

        evalBtn.disabled = false;
        evalBtn.textContent = "Evaluate Dataset Performance";
        dom.clear(resultsContainer);

        if (!res.ok) {
          resultsContainer.appendChild(renderError({
            title: "Performance Evaluation Error",
            message: res.error.message,
            details: res.error.details,
          }));
          return;
        }

        renderPerformanceResults(resultsContainer, res.data, selectedModel);
      },
    });

    const formGrid = dom.el("div", { className: "grid-2" },
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Select Trained AI Model" }),
        modelSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Monitored Dataset (Incoming Stream)" }),
        datasetSelect
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Ground-Truth Label Column" }),
        labelInput,
        dom.el("span", { className: "form-hint", text: "If labels are absent/delayed, status will indicate LABELS_UNAVAILABLE." })
      ),
      dom.el("div", { className: "form-group" },
        dom.el("label", { className: "form-label", text: "Allowed Drop Tolerance (e.g. 0.05 = 5%)" }),
        toleranceInput
      )
    );

    formSlot.appendChild(formGrid);
    formSlot.appendChild(evalBtn);
  }

  function renderPerformanceResults(target, metrics, model) {
    const isDegraded = metrics.degradation_flagged;
    const isEvaluated = metrics.status === "evaluated";

    // 1. Status Banner Card
    let bannerTheme = "healthy";
    let bannerTitle = "Model Performance Healthy";
    let bannerText = "Empirical accuracy and F1 scores remain within baseline tolerance limits.";

    if (metrics.status === "labels_unavailable") {
      bannerTheme = "navy";
      bannerTitle = "Ground-Truth Labels Unavailable";
      bannerText = "Predictions generated successfully, but performance cannot be computed without verified labels.";
    } else if (metrics.status === "insufficient_data") {
      bannerTheme = "warning";
      bannerTitle = "Insufficient Data Samples";
      bannerText = metrics.note || "Sample count is below the minimum required threshold for statistical reliability.";
    } else if (isDegraded) {
      bannerTheme = "critical";
      bannerTitle = "✖ Performance Degradation Confirmed";
      bannerText = `Metric dropped by more than the tolerance threshold (Absolute F1 diff: ${format.percent(metrics.abs_diff_f1)}).`;
    }

    const bannerCard = dom.el("div", {
      className: `card`,
      style: { borderTop: `4px solid var(--color-${bannerTheme === "critical" ? "coral" : (bannerTheme === "warning" ? "amber" : "teal")})` },
    },
      dom.el("div", { className: "card-header" },
        dom.el("div", { className: "card-title", text: bannerTitle }),
        dom.el("span", {
          className: `status-badge ${isDegraded ? "status-PERFORMANCE_DEGRADATION" : "status-NORMAL"}`,
          text: metrics.status.toUpperCase(),
        })
      ),
      dom.el("p", { style: { fontSize: "0.95rem" }, text: bannerText })
    );
    target.appendChild(bannerCard);

    if (!isEvaluated) return;

    // 2. Metrics Cards
    const accCI = metrics.accuracy_ci ? ` [${format.percent(metrics.accuracy_ci.lower)} - ${format.percent(metrics.accuracy_ci.upper)}]` : "";
    const f1CI = metrics.f1_ci ? ` [${format.percent(metrics.f1_ci.lower)} - ${format.percent(metrics.f1_ci.upper)}]` : "";

    const grid = dom.el("div", { className: "grid-4", style: { marginBottom: "1.5rem" } },
      renderMetricCard({
        label: "Evaluated Accuracy",
        value: format.percent(metrics.accuracy),
        subtext: `95% CI: ${accCI || "computed via bootstrap"}`,
        theme: isDegraded ? "critical" : "healthy",
      }),
      renderMetricCard({
        label: "Evaluated Macro F1",
        value: format.percent(metrics.f1),
        subtext: `95% CI: ${f1CI || "computed via bootstrap"}`,
        theme: isDegraded ? "critical" : "healthy",
      }),
      renderMetricCard({
        label: "Precision",
        value: format.percent(metrics.precision),
        subtext: "Evaluated on incoming stream",
        theme: "healthy",
      }),
      renderMetricCard({
        label: "Recall",
        value: format.percent(metrics.recall),
        subtext: "Evaluated on incoming stream",
        theme: "healthy",
      })
    );
    target.appendChild(grid);

    // 3. Comparison & Confusion Matrix Split
    const splitGrid = dom.el("div", { className: "grid-2" });

    // Comparison Chart Card
    const compCard = dom.el("div", { className: "card" },
      dom.el("div", { className: "card-header" },
        dom.el("div", { className: "card-title", text: "Baseline vs. Monitored Comparison" })
      ),
      dom.el("div", { id: "perf-comp-chart", className: "chart-box" })
    );
    splitGrid.appendChild(compCard);

    // Confusion Matrix Card
    const cmCard = dom.el("div", { className: "card" },
      dom.el("div", { className: "card-header" },
        dom.el("div", { className: "card-title", text: "Evaluated Confusion Matrix" })
      ),
      dom.el("div", { id: "perf-cm-chart", style: { padding: "1rem" } })
    );
    splitGrid.appendChild(cmCard);

    target.appendChild(splitGrid);

    // Render charts
    const baseM = model?.baseline_metrics || {};
    renderMetricComparison(compCard.querySelector("#perf-comp-chart"), baseM, metrics);
    renderConfusionMatrix(cmCard.querySelector("#perf-cm-chart"), metrics.confusion_matrix, metrics.class_labels || ["0", "1"]);
  }

  // Initial load
  loadPerfForm();
}
