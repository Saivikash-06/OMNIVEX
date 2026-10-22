/**
 * OMNIVEX Table Builder Component
 * Generates interactive, sortable, accessible tables.
 */

import { dom } from "../core/dom.js";

export function renderTable({
  columns = [],
  rows = [],
  emptyText = "No records to display",
  sortKey = null,
  sortDirection = "asc", // "asc" | "desc"
  onSort = null,
  page = 1,
  pageSize = 50,
  totalItems = null,
  onPageChange = null,
} = {}) {
  const container = dom.el("div", { className: "table-container" });

  if (!rows || rows.length === 0) {
    container.appendChild(
      dom.el("div", {
        style: { padding: "2rem", textAlign: "center", color: "var(--text-muted)" },
        text: emptyText,
      })
    );
    return container;
  }

  const table = dom.el("table", { className: "table" });
  const thead = dom.el("thead");
  const headerRow = dom.el("tr");

  for (const col of columns) {
    const isSorted = sortKey === col.key;
    const thProps = {
      className: col.sortable ? "sortable" : "",
    };

    if (col.sortable && typeof onSort === "function") {
      thProps.onClick = () => {
        const nextDir = isSorted && sortDirection === "asc" ? "desc" : "asc";
        onSort(col.key, nextDir);
      };
    }

    const sortIndicator = isSorted ? (sortDirection === "asc" ? " ▲" : " ▼") : "";
    const th = dom.el("th", thProps, col.label + sortIndicator);
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = dom.el("tbody");
  for (const row of rows) {
    const tr = dom.el("tr");
    for (const col of columns) {
      const td = dom.el("td");
      if (typeof col.render === "function") {
        const rendered = col.render(row);
        if (rendered instanceof Node) {
          td.appendChild(rendered);
        } else if (rendered !== null && rendered !== undefined) {
          td.textContent = String(rendered);
        }
      } else {
        const val = row[col.key];
        td.textContent = val !== null && val !== undefined ? String(val) : "—";
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);

  // Pagination bar if requested
  if (totalItems !== null && totalItems > pageSize && typeof onPageChange === "function") {
    const totalPages = Math.ceil(totalItems / pageSize);
    const paginationBar = dom.el("div", {
      style: {
        padding: "0.75rem 1rem",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderTop: "1px solid var(--border-color)",
        fontSize: "0.82rem",
        color: "var(--text-muted)",
      },
    },
      dom.el("span", {
        text: `Showing ${(page - 1) * pageSize + 1} - ${Math.min(page * pageSize, totalItems)} of ${totalItems}`,
      }),
      dom.el("div", { style: { display: "flex", gap: "0.5rem" } },
        dom.el("button", {
          className: "btn btn-outline btn-sm",
          disabled: page <= 1,
          text: "Previous",
          onClick: () => onPageChange(page - 1),
        }),
        dom.el("span", { style: { padding: "0.25rem 0.5rem" }, text: `Page ${page} / ${totalPages}` }),
        dom.el("button", {
          className: "btn btn-outline btn-sm",
          disabled: page >= totalPages,
          text: "Next",
          onClick: () => onPageChange(page + 1),
        })
      )
    );
    container.appendChild(paginationBar);
  }

  return container;
}
