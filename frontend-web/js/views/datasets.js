/**
 * OMNIVEX Datasets View
 * Ingestion, validation, and schema inspection for reference and incoming datasets.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";
import { apiClient } from "../api/client.js";
import { renderTable } from "../components/tables.js";
import { renderLoading, renderEmpty, renderError } from "../components/states.js";

export async function renderDatasets(container) {
  dom.clear(container);

  const intro = dom.el("div", { className: "view-intro" },
    dom.el("h2", { text: "Dataset Management" },
      dom.el("span", {
        style: { fontSize: "0.85rem", fontWeight: "normal", color: "var(--text-muted)", marginLeft: "0.75rem" },
        text: "Upload, inspect schema, and validate compatibility"
      })
    ),
    dom.el("p", { text: "Manage baseline reference datasets and incoming real-world data streams. Preprocessing pipelines fit solely on reference data to avoid leakage." })
  );
  container.appendChild(intro);

  const grid = dom.el("div", { className: "grid-2" });

  // 1. Upload Card
  const uploadCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Upload New CSV Dataset" })
    )
  );

  let selectedFile = null;

  const dropzone = dom.el("div", { className: "upload-dropzone" },
    dom.el("div", { className: "upload-icon", text: "📁" }),
    dom.el("div", { style: { fontWeight: "600", color: "var(--color-navy)" }, text: "Click to select or drag & drop a CSV file" }),
    dom.el("div", { style: { fontSize: "0.8rem", color: "var(--text-muted)" }, text: "Strict 10MB limit; headers and data types will be automatically inferred." }),
    dom.el("div", { id: "selected-filename", style: { fontWeight: "700", color: "var(--color-teal)", display: "none" } })
  );

  const fileInput = dom.el("input", {
    type: "file",
    accept: ".csv,text/csv",
    style: { display: "none" },
    onChange: (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileSelect(e.target.files[0]);
      }
    },
  });

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  });

  function handleFileSelect(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      dom.toast("Only .csv files are supported.", "error");
      return;
    }
    selectedFile = file;
    const nameEl = dropzone.querySelector("#selected-filename");
    nameEl.textContent = `Selected: ${file.name} (${format.bytes(file.size)})`;
    nameEl.style.display = "block";
  }

  const roleSelect = dom.el("select", { className: "form-select", id: "dataset-role-select" },
    dom.el("option", { value: "reference", text: "Reference (Baseline Training Data)" }),
    dom.el("option", { value: "incoming", text: "Incoming (Monitored Stream Data)" })
  );

  const uploadBtn = dom.el("button", {
    className: "btn btn-primary",
    style: { marginTop: "1rem", width: "100%" },
    text: "Upload & Ingest Dataset",
    onClick: async () => {
      if (!selectedFile) {
        dom.toast("Please select a CSV file first.", "warning");
        return;
      }
      uploadBtn.disabled = true;
      uploadBtn.textContent = "Uploading & Computing Schema...";
      const role = roleSelect.value;

      const res = await apiClient.uploadDataset(selectedFile, role);
      uploadBtn.disabled = false;
      uploadBtn.textContent = "Upload & Ingest Dataset";

      if (res.ok) {
        dom.toast(`Dataset "${res.data.name}" uploaded successfully!`, "success");
        selectedFile = null;
        dropzone.querySelector("#selected-filename").style.display = "none";
        loadDatasetsList();
      } else {
        dom.toast(`Upload failed: ${res.error.message}`, "error");
      }
    },
  });

  uploadCard.appendChild(fileInput);
  uploadCard.appendChild(dropzone);
  uploadCard.appendChild(dom.el("div", { className: "form-group", style: { marginTop: "1rem" } },
    dom.el("label", { className: "form-label", text: "Dataset Role" }),
    roleSelect,
    dom.el("span", { className: "form-hint", text: "Reference datasets serve as the baseline ground truth; incoming datasets represent real-world monitored stream batches." })
  ));
  uploadCard.appendChild(uploadBtn);
  grid.appendChild(uploadCard);

  // 2. Schema Validation Tool Card
  const validateCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Schema Compatibility Validator" }),
      dom.el("div", { className: "card-subtitle", text: "Pre-flight check between Reference and Incoming datasets" })
    ),
    dom.el("div", { id: "validation-tool-body", style: { display: "flex", flexDirection: "column", gap: "0.75rem" } })
  );
  grid.appendChild(validateCard);

  container.appendChild(grid);

  // 3. Registered Datasets Table Card
  const tableCard = dom.el("div", { className: "card" },
    dom.el("div", { className: "card-header" },
      dom.el("div", { className: "card-title", text: "Registered Datasets" }),
      dom.el("button", { className: "btn btn-outline btn-sm", text: "Refresh", onClick: () => loadDatasetsList() })
    ),
    dom.el("div", { id: "datasets-table-slot" })
  );
  container.appendChild(tableCard);

  // Modal slot for schema inspection
  const modalSlot = dom.el("div", { id: "dataset-modal-slot" });
  container.appendChild(modalSlot);

  // Loader function for datasets list & validator dropdowns
  async function loadDatasetsList() {
    const tableSlot = tableCard.querySelector("#datasets-table-slot");
    dom.clear(tableSlot);
    tableSlot.appendChild(renderLoading("Loading datasets..."));

    const res = await apiClient.listDatasets({ limit: 100 });
    dom.clear(tableSlot);

    if (!res.ok) {
      tableSlot.appendChild(renderError({
        message: res.error.message,
        onRetry: () => loadDatasetsList(),
      }));
      return;
    }

    const datasets = res.data.items || [];
    renderValidationForm(datasets);

    if (datasets.length === 0) {
      tableSlot.appendChild(renderEmpty({
        title: "No datasets registered",
        description: "Upload your first CSV dataset above to begin AI reliability monitoring.",
      }));
      return;
    }

    const columns = [
      { key: "name", label: "Dataset Name", sortable: true },
      {
        key: "role",
        label: "Role",
        sortable: true,
        render: (row) => dom.el("span", {
          className: `status-badge ${row.role === "reference" ? "status-INSUFFICIENT_DATA" : "status-NORMAL"}`,
          text: row.role.toUpperCase(),
        }),
      },
      { key: "row_count", label: "Rows", sortable: true },
      { key: "column_count", label: "Columns", sortable: true },
      {
        key: "size_bytes",
        label: "Size",
        sortable: true,
        render: (row) => format.bytes(row.size_bytes),
      },
      {
        key: "sha256",
        label: "SHA-256 Hash",
        render: (row) => dom.el("code", {
          style: { fontSize: "0.78rem", color: "var(--text-muted)" },
          title: row.sha256,
          text: `${row.sha256.slice(0, 10)}...`,
        }),
      },
      {
        key: "created_at",
        label: "Uploaded",
        sortable: true,
        render: (row) => format.date(row.created_at),
      },
      {
        key: "actions",
        label: "Action",
        render: (row) => dom.el("button", {
          className: "btn btn-outline btn-sm",
          text: "Inspect Schema",
          onClick: () => showSchemaModal(row),
        }),
      },
    ];

    tableSlot.appendChild(renderTable({
      columns,
      rows: datasets,
    }));
  }

  function renderValidationForm(datasets) {
    const valBody = validateCard.querySelector("#validation-tool-body");
    dom.clear(valBody);

    const refDatasets = datasets.filter((d) => d.role === "reference");
    const incDatasets = datasets.filter((d) => d.role === "incoming");

    if (refDatasets.length === 0 || incDatasets.length === 0) {
      valBody.appendChild(dom.el("p", {
        style: { fontSize: "0.88rem", color: "var(--text-muted)" },
        text: "Requires at least one 'Reference' dataset and one 'Incoming' dataset to validate schema compatibility.",
      }));
      return;
    }

    const refSelect = dom.el("select", { className: "form-select" },
      ...refDatasets.map((d) => dom.el("option", { value: d.id, text: `${d.name} (${d.row_count} rows)` }))
    );

    const incSelect = dom.el("select", { className: "form-select" },
      ...incDatasets.map((d) => dom.el("option", { value: d.id, text: `${d.name} (${d.row_count} rows)` }))
    );

    const resultBox = dom.el("div", { id: "validation-result-box" });

    const valBtn = dom.el("button", {
      className: "btn btn-primary btn-sm",
      text: "Run Schema Validation Check",
      onClick: async () => {
        valBtn.disabled = true;
        valBtn.textContent = "Checking...";
        dom.clear(resultBox);

        const vRes = await apiClient.validateIncomingDataset(refSelect.value, incSelect.value);
        valBtn.disabled = false;
        valBtn.textContent = "Run Schema Validation Check";

        if (!vRes.ok) {
          resultBox.appendChild(dom.el("div", {
            style: { padding: "0.75rem", backgroundColor: "var(--color-coral-subtle)", borderRadius: "6px", color: "var(--color-coral-dark)", fontSize: "0.85rem" },
            text: `Validation error: ${vRes.error.message}`,
          }));
          return;
        }

        const data = vRes.data;
        const statusBox = dom.el("div", {
          style: {
            padding: "0.85rem",
            borderRadius: "6px",
            backgroundColor: data.is_valid ? "var(--color-teal-subtle)" : "var(--color-coral-subtle)",
            border: `1px solid ${data.is_valid ? "var(--color-teal-border)" : "var(--color-coral-border)"}`,
            color: data.is_valid ? "var(--color-teal-dark)" : "var(--color-coral-dark)",
            fontSize: "0.88rem",
          },
        },
          dom.el("strong", { text: data.is_valid ? "✓ Schema Compatible: " : "✖ Schema Mismatches Detected: " }),
          dom.el("span", {
            text: data.is_valid
              ? "All reference columns and compatible data types matched in the incoming dataset."
              : `Found ${data.issues.length} issue(s) that may trigger INSUFFICIENT_DATA or monitoring errors.`,
          })
        );
        resultBox.appendChild(statusBox);

        if (data.quality_summary) {
          resultBox.appendChild(dom.el("div", {
            style: { marginTop: "0.5rem", fontSize: "0.82rem", color: "var(--color-navy)" },
            text: `Overall Quality Score: ${(data.quality_summary.overall_quality_score * 100).toFixed(1)}%`,
          }));
        }
      },
    });

    valBody.appendChild(dom.el("div", { className: "form-group" },
      dom.el("label", { className: "form-label", text: "Select Reference Baseline" }),
      refSelect
    ));
    valBody.appendChild(dom.el("div", { className: "form-group" },
      dom.el("label", { className: "form-label", text: "Select Incoming Dataset" }),
      incSelect
    ));
    valBody.appendChild(valBtn);
    valBody.appendChild(resultBox);
  }

  function showSchemaModal(dataset) {
    const modalSlot = container.querySelector("#dataset-modal-slot");
    dom.clear(modalSlot);

    const cols = dataset.schema_info?.columns || [];

    const schemaTable = renderTable({
      columns: [
        { key: "name", label: "Column Name", sortable: true },
        { key: "dtype_class", label: "Class", sortable: true },
        { key: "pandas_dtype", label: "Pandas DType", sortable: true },
        {
          key: "null_percentage",
          label: "Nulls",
          render: (row) => format.percent(row.null_percentage / 100),
        },
        { key: "unique_count", label: "Unique", sortable: true },
        {
          key: "range",
          label: "Range / Categories",
          render: (row) => {
            if (row.min_value !== null && row.max_value !== null) {
              return `[${format.decimal(row.min_value, 2)} to ${format.decimal(row.max_value, 2)}]`;
            }
            if (row.categories && row.categories.length > 0) {
              return format.truncate(row.categories.join(", "), 30);
            }
            return "—";
          },
        },
      ],
      rows: cols,
    });

    const modal = dom.el("div", { className: "modal-backdrop" },
      dom.el("div", { className: "modal-content", style: { maxWidth: "800px" } },
        dom.el("div", { className: "modal-header" },
          dom.el("div", {},
            dom.el("h3", { className: "modal-title", text: `Inferred Schema: ${dataset.name}` }),
            dom.el("span", { style: { fontSize: "0.8rem", color: "var(--text-muted)" }, text: `${dataset.row_count} rows, ${dataset.column_count} columns • Role: ${dataset.role.toUpperCase()}` })
          ),
          dom.el("button", {
            className: "btn btn-outline btn-sm",
            text: "✕",
            onClick: () => dom.clear(modalSlot),
          })
        ),
        dom.el("div", { className: "modal-body" }, schemaTable),
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
  loadDatasetsList();
}
