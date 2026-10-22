/**
 * OMNIVEX Models View
 * Training, baseline metric registration, and artifact integrity inspection.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";
import { apiClient } from "../api/client.js";
import { renderTable } from "../components/tables.js";
import { renderConfusionMatrix } from "../components/charts.js";
import { renderLoading, renderEmpty, renderError } from "../components/states.js";

export async function renderModels(container) {
  dom.clear(container);

  const intro = dom.el("div", { className: "view-intro" },
    dom.el("h2", { text: "AI Baseline Models" },
      dom.el("span", {
        style: { fontSize: "0.85rem", fontWeight: "normal", color: "var(--text-muted)", marginLeft: "0.75rem" },
        text: "Train estimators and establish baseline benchmark metrics"
      })
    ),
    dom.el("p", { text: "Train classification models on reference datasets. Pipelines bundle preprocessing and estimators; artifacts are protected by SHA-256 integrity checks." })
  );
  container.appendChild(intro);

  const grid = dom.el("div", { className: "grid-2" });

  // 1. Train Model Form Card
  const trainCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Train New Baseline Model" })
    ),
    dom.el("div", { id: "train-form-slot" })
  );
  grid.appendChild(trainCard);

  // 2. Training Guide / Artifact Integrity Card
  const infoCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Integrity & Preprocessing Rules" })
    ),
    dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.88rem", color: "var(--text-secondary)" } },
      dom.el("p", { text: "• Leakage Prevention: Scalers, encoders, and imputers are strictly fit on reference training splits." }),
      dom.el("p", { text: "• Artifact Verification: Before running inference or performance audits, the SHA-256 hash of the serialized joblib artifact is verified against the database record." }),
      dom.el("p", { text: "• Target Column Check: Target labels are strictly isolated from the feature matrix to eliminate target leakage." })
    )
  );
  grid.appendChild(infoCard);
  container.appendChild(grid);

  // 3. Registered Models Table Card
  const tableCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Registered AI Models" }),
      dom.el("button", { className: "btn btn-outline btn-sm", text: "Refresh", onClick: () => loadModelsList() })
    ),
    dom.el("div", { id: "models-table-slot" })
  );
  container.appendChild(tableCard);

  // Modal slot
  const modalSlot = dom.el("div", { id: "model-modal-slot" });
  container.appendChild(modalSlot);

  // Load datasets to populate training dropdown
  async function loadTrainForm() {
    const formSlot = trainCard.querySelector("#train-form-slot");
    dom.clear(formSlot);
    formSlot.appendChild(renderLoading("Fetching reference datasets..."));

    const refRes = await apiClient.listDatasets({ role: "reference", limit: 50 });
    dom.clear(formSlot);

    if (!refRes.ok || !refRes.data.items || refRes.data.items.length === 0) {
      formSlot.appendChild(dom.el("p", {
        style: { fontSize: "0.88rem", color: "var(--text-muted)" },
        text: "Please upload at least one 'Reference' dataset before training a model.",
      }));
      formSlot.appendChild(dom.el("div", { style: { marginTop: "0.5rem" } },
        dom.el("a", { className: "btn btn-outline btn-sm", href: "#/datasets", text: "Upload Reference Dataset" })
      ));
      return;
    }

    const datasets = refRes.data.items;

    const nameInput = dom.el("input", {
      type: "text",
      className: "form-control",
      placeholder: "e.g., CreditRisk-Logistic-v1",
      value: "CreditRisk-Baseline-LR",
    });

    const datasetSelect = dom.el("select", { className: "form-select" },
      ...datasets.map((d) => dom.el("option", { value: d.id, text: `${d.name} (${d.row_count} rows)` }))
    );

    const targetInput = dom.el("input", {
      type: "text",
      className: "form-control",
      placeholder: "e.g., loan_default",
      value: "loan_default",
    });

    const algoSelect = dom.el("select", { className: "form-select" },
      dom.el("option", { value: "logistic_regression", text: "Logistic Regression (Interpretable linear baseline)" }),
      dom.el("option", { value: "random_forest", text: "Random Forest (Ensemble trees)" }),
      dom.el("option", { value: "gradient_boosting", text: "HistGradientBoosting (Non-linear boosting)" }),
      dom.el("option", { value: "decision_tree", text: "Decision Tree (Single tree)" })
    );

    const submitBtn = dom.el("button", {
      className: "btn btn-primary",
      style: { width: "100%", marginTop: "1rem" },
      text: "Train Baseline Model",
      onClick: async () => {
        const name = nameInput.value.trim();
        const target = targetInput.value.trim();
        const datasetId = datasetSelect.value;
        const algorithm = algoSelect.value;

        if (!name || !target) {
          dom.toast("Please specify both a model name and target column.", "warning");
          return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = "Training & Serializing Artifact...";

        const trainRes = await apiClient.trainModel({
          name,
          dataset_id: datasetId,
          target_column: target,
          algorithm,
          test_size: 0.2,
          random_seed: 42,
        });

        submitBtn.disabled = false;
        submitBtn.textContent = "Train Baseline Model";

        if (trainRes.ok) {
          dom.toast(`Model "${trainRes.data.name}" trained successfully!`, "success");
          loadModelsList();
        } else {
          dom.toast(`Training failed: ${trainRes.error.message}`, "error");
        }
      },
    });

    formSlot.appendChild(dom.el("div", { className: "form-group" },
      dom.el("label", { className: "form-label", text: "Model Name" }),
      nameInput
    ));
    formSlot.appendChild(dom.el("div", { className: "form-group" },
      dom.el("label", { className: "form-label", text: "Training Reference Dataset" }),
      datasetSelect
    ));
    formSlot.appendChild(dom.el("div", { className: "form-group" },
      dom.el("label", { className: "form-label", text: "Target Label Column" }),
      targetInput
    ));
    formSlot.appendChild(dom.el("div", { className: "form-group" },
      dom.el("label", { className: "form-label", text: "Algorithm" }),
      algoSelect
    ));
    formSlot.appendChild(submitBtn);
  }

  // Loader function for models list
  async function loadModelsList() {
    const tableSlot = tableCard.querySelector("#models-table-slot");
    dom.clear(tableSlot);
    tableSlot.appendChild(renderLoading("Loading models..."));

    const res = await apiClient.listModels({ limit: 100 });
    dom.clear(tableSlot);

    if (!res.ok) {
      tableSlot.appendChild(renderError({
        message: res.error.message,
        onRetry: () => loadModelsList(),
      }));
      return;
    }

    const models = res.data.items || [];
    if (models.length === 0) {
      tableSlot.appendChild(renderEmpty({
        title: "No trained models registered",
        description: "Train a model using a reference dataset above to establish an AI performance baseline.",
      }));
      return;
    }

    const columns = [
      { key: "name", label: "Model Name", sortable: true },
      {
        key: "algorithm",
        label: "Algorithm",
        sortable: true,
        render: (row) => dom.el("span", {
          className: "status-badge status-INSUFFICIENT_DATA",
          text: row.algorithm,
        }),
      },
      { key: "target_column", label: "Target Column", sortable: true },
      {
        key: "accuracy",
        label: "Base Accuracy",
        sortable: true,
        render: (row) => format.percent(row.baseline_metrics?.accuracy),
      },
      {
        key: "f1",
        label: "Base Macro F1",
        sortable: true,
        render: (row) => format.percent(row.baseline_metrics?.f1),
      },
      {
        key: "sample_size",
        label: "Test Samples",
        render: (row) => row.baseline_metrics?.sample_size || "—",
      },
      {
        key: "created_at",
        label: "Registered",
        sortable: true,
        render: (row) => format.date(row.created_at),
      },
      {
        key: "actions",
        label: "Action",
        render: (row) => dom.el("button", {
          className: "btn btn-outline btn-sm",
          text: "Inspect Model",
          onClick: () => showModelModal(row),
        }),
      },
    ];

    tableSlot.appendChild(renderTable({
      columns,
      rows: models,
    }));
  }

  function showModelModal(model) {
    const modalSlot = container.querySelector("#model-modal-slot");
    dom.clear(modalSlot);

    const m = model.baseline_metrics;
    const detailsBody = dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "1rem" } });

    // Metrics row
    const metricsRow = dom.el("div", { className: "grid-4" },
      dom.el("div", { className: "metric-card healthy" },
        dom.el("div", { className: "metric-label", text: "Accuracy" }),
        dom.el("div", { className: "metric-value", text: format.percent(m?.accuracy) })
      ),
      dom.el("div", { className: "metric-card healthy" },
        dom.el("div", { className: "metric-label", text: "Macro F1" }),
        dom.el("div", { className: "metric-value", text: format.percent(m?.f1) })
      ),
      dom.el("div", { className: "metric-card healthy" },
        dom.el("div", { className: "metric-label", text: "Precision" }),
        dom.el("div", { className: "metric-value", text: format.percent(m?.precision) })
      ),
      dom.el("div", { className: "metric-card healthy" },
        dom.el("div", { className: "metric-label", text: "Recall" }),
        dom.el("div", { className: "metric-value", text: format.percent(m?.recall) })
      )
    );
    detailsBody.appendChild(metricsRow);

    // Confusion Matrix preview
    if (m?.confusion_matrix) {
      const cmBox = dom.el("div", { style: { border: "1px solid var(--border-color)", padding: "1rem", borderRadius: "8px" } },
        dom.el("div", { style: { fontWeight: "700", marginBottom: "0.5rem", color: "var(--color-navy)" }, text: "Baseline Confusion Matrix" })
      );
      renderConfusionMatrix(cmBox, m.confusion_matrix, model.class_labels || ["0", "1"]);
      detailsBody.appendChild(cmBox);
    }

    // Feature names & details
    const featuresList = dom.el("div", { style: { fontSize: "0.85rem", color: "var(--text-secondary)" } },
      dom.el("strong", { text: "Engineered Features: " }),
      dom.el("span", { text: (model.feature_names || []).join(", ") })
    );
    detailsBody.appendChild(featuresList);

    // Artifact SHA-256
    const hashInfo = dom.el("div", {
      style: {
        backgroundColor: "var(--bg-subtle)",
        padding: "0.75rem",
        borderRadius: "6px",
        fontSize: "0.8rem",
        wordBreak: "break-all",
      },
    },
      dom.el("div", {}, dom.el("strong", { text: "Artifact Filename: " }), dom.el("span", { text: model.artifact_filename })),
      dom.el("div", {}, dom.el("strong", { text: "SHA-256 Integrity Hash: " }), dom.el("code", { text: model.artifact_sha256 }))
    );
    detailsBody.appendChild(hashInfo);

    const modal = dom.el("div", { className: "modal-backdrop" },
      dom.el("div", { className: "modal-content", style: { maxWidth: "750px" } },
        dom.el("div", { className: "modal-header" },
          dom.el("div", {},
            dom.el("h3", { className: "modal-title", text: `Model: ${model.name}` }),
            dom.el("span", { style: { fontSize: "0.8rem", color: "var(--text-muted)" }, text: `Algorithm: ${model.algorithm} • Target: ${model.target_column}` })
          ),
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "✕",
            onClick: () => dom.clear(modalSlot),
          })
        ),
        dom.el("div", { className: "modal-body" }, detailsBody),
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

  // Initial loads
  loadTrainForm();
  loadModelsList();
}
