/**
 * OMNIVEX Charts Component
 * Uses Plotly if available from CDN, with high-quality SVG fallback for completely offline usage.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";

function hasPlotly() {
  return typeof window !== "undefined" && typeof window.Plotly !== "undefined";
}

export function renderDriftBarChart(container, perFeatureResults = []) {
  if (!container) return;
  dom.clear(container);

  if (!perFeatureResults || perFeatureResults.length === 0) {
    container.appendChild(dom.el("div", {
      style: { padding: "2rem", textAlign: "center", color: "var(--text-muted)" },
      text: "No feature drift data available to chart.",
    }));
    return;
  }

  const features = perFeatureResults.map((r) => r.feature);
  const statistics = perFeatureResults.map((r) => r.statistic);
  const colors = perFeatureResults.map((r) => {
    if (r.status === "drift") return "#E4572E"; // Coral
    if (r.status === "significant_low_effect") return "#F2A93B"; // Amber
    return "#1F9E9E"; // Teal
  });

  if (hasPlotly()) {
    const data = [{
      x: features,
      y: statistics,
      type: "bar",
      marker: { color: colors },
      text: perFeatureResults.map((r) => `Test: ${r.test_name}<br>p-val: ${format.pValue(r.p_value)}<br>Status: ${r.status}`),
      hoverinfo: "text+x+y",
    }];

    const layout = {
      title: { text: "Distribution Shift Magnitude by Feature", font: { color: "#1B2A41", size: 14 } },
      margin: { t: 40, r: 20, l: 50, b: 60 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      xaxis: { title: "Feature Name", tickangle: -25, color: "#475569" },
      yaxis: { title: "Test Statistic (KS / Chi² / TVD)", color: "#475569", rangemode: "tozero" },
    };

    window.Plotly.newPlot(container, data, layout, { responsive: true, displayModeBar: false });
    return;
  }

  // Pure SVG Fallback
  const svg = dom.el("svg", {
    viewBox: `0 0 ${Math.max(600, features.length * 60)} 260`,
    style: { width: "100%", height: "260px" },
  });

  const maxVal = Math.max(...statistics, 0.1);
  const barWidth = 32;
  const chartHeight = 180;
  const startX = 60;
  const startY = 20;

  // Grid line
  svg.appendChild(dom.el("line", {
    x1: startX - 10, y1: startY + chartHeight,
    x2: startX + features.length * 55, y2: startY + chartHeight,
    stroke: "#CBD5E1", "stroke-width": "1",
  }));

  features.forEach((feat, idx) => {
    const val = statistics[idx];
    const barHeight = (val / maxVal) * (chartHeight - 20);
    const x = startX + idx * 55;
    const y = startY + chartHeight - barHeight;

    // Bar rect
    svg.appendChild(dom.el("rect", {
      x, y, width: barWidth, height: barHeight,
      fill: colors[idx], rx: "3",
    }));

    // Value text
    svg.appendChild(dom.el("text", {
      x: x + barWidth / 2, y: y - 5,
      "text-anchor": "middle", "font-size": "10", fill: "#1B2A41",
    }, format.decimal(val, 2)));

    // Label text
    svg.appendChild(dom.el("text", {
      x: x + barWidth / 2, y: startY + chartHeight + 18,
      "text-anchor": "middle", "font-size": "10", fill: "#475569",
    }, format.truncate(feat, 8)));
  });

  container.appendChild(svg);
}

export function renderConfusionMatrix(container, matrix, classLabels = ["Class 0", "Class 1"]) {
  if (!container) return;
  dom.clear(container);

  if (!matrix || !Array.isArray(matrix) || matrix.length === 0) {
    container.appendChild(dom.el("div", {
      style: { padding: "1.5rem", textAlign: "center", color: "var(--text-muted)" },
      text: "No confusion matrix data available.",
    }));
    return;
  }

  const table = dom.el("table", {
    style: {
      margin: "0 auto",
      borderCollapse: "separate",
      borderSpacing: "6px",
      textAlign: "center",
      fontSize: "0.9rem",
    },
  });

  // Header row
  const headerRow = dom.el("tr");
  headerRow.appendChild(dom.el("th", { style: { padding: "8px", color: "var(--text-muted)" } }, "Actual \\ Pred"));
  for (const label of classLabels) {
    headerRow.appendChild(dom.el("th", {
      style: { padding: "8px", color: "var(--color-navy)", fontWeight: "600" },
      text: `Pred ${label}`,
    }));
  }
  table.appendChild(headerRow);

  // Rows
  const maxVal = Math.max(...matrix.flat(), 1);
  for (let r = 0; r < matrix.length; r++) {
    const rowEl = dom.el("tr");
    rowEl.appendChild(dom.el("td", {
      style: { padding: "8px", fontWeight: "600", color: "var(--color-navy)", textAlign: "right" },
      text: `True ${classLabels[r] || r}`,
    }));

    for (let c = 0; c < matrix[r].length; c++) {
      const val = matrix[r][c];
      const isCorrect = r === c;
      const intensity = Math.min(1, val / maxVal);
      const bgColor = isCorrect
        ? `rgba(31, 158, 158, ${0.15 + intensity * 0.5})`
        : `rgba(228, 87, 46, ${0.15 + intensity * 0.5})`;
      const textColor = intensity > 0.6 ? (isCorrect ? "#111B2B" : "#FFFFFF") : "var(--color-navy)";

      rowEl.appendChild(dom.el("td", {
        style: {
          padding: "16px 22px",
          backgroundColor: bgColor,
          color: textColor,
          fontWeight: "700",
          borderRadius: "6px",
          minWidth: "60px",
        },
        text: String(val),
      }));
    }
    table.appendChild(rowEl);
  }

  container.appendChild(table);
}

export function renderMetricComparison(container, baselineMetrics = {}, evaluatedMetrics = {}) {
  if (!container) return;
  dom.clear(container);

  const metricKeys = [
    { key: "accuracy", label: "Accuracy" },
    { key: "f1", label: "Macro F1" },
    { key: "precision", label: "Precision" },
    { key: "recall", label: "Recall" },
  ];

  const categories = [];
  const baseVals = [];
  const evalVals = [];

  for (const item of metricKeys) {
    const bVal = baselineMetrics[item.key];
    const eVal = evaluatedMetrics[item.key];
    if (bVal !== undefined || eVal !== undefined) {
      categories.push(item.label);
      baseVals.push(bVal !== undefined && bVal !== null ? Number(bVal) : 0);
      evalVals.push(eVal !== undefined && eVal !== null ? Number(eVal) : 0);
    }
  }

  if (categories.length === 0) {
    container.appendChild(dom.el("div", {
      style: { padding: "1.5rem", textAlign: "center", color: "var(--text-muted)" },
      text: "No comparative metric data available.",
    }));
    return;
  }

  if (hasPlotly()) {
    const traceBase = {
      x: categories,
      y: baseVals,
      name: "Baseline Reference",
      type: "bar",
      marker: { color: "#1B2A41" }, // Navy
    };

    const traceEval = {
      x: categories,
      y: evalVals,
      name: "Incoming Stream",
      type: "bar",
      marker: { color: "#1F9E9E" }, // Teal
    };

    const layout = {
      barmode: "group",
      title: { text: "Baseline vs. Incoming Performance Comparison", font: { color: "#1B2A41", size: 14 } },
      margin: { t: 40, r: 20, l: 40, b: 40 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      yaxis: { range: [0, 1.05], tickformat: ",.0%" },
    };

    window.Plotly.newPlot(container, [traceBase, traceEval], layout, { responsive: true, displayModeBar: false });
    return;
  }

  // Fallback Comparison Table/Bar
  const wrapper = dom.el("div", { style: { display: "flex", flexDirection: "column", gap: "0.75rem" } });
  for (let i = 0; i < categories.length; i++) {
    const cat = categories[i];
    const b = baseVals[i];
    const e = evalVals[i];
    const diff = e - b;
    const diffText = `${diff >= 0 ? "+" : ""}${(diff * 100).toFixed(1)}%`;
    const diffColor = diff < -0.05 ? "var(--color-coral)" : "var(--color-teal)";

    wrapper.appendChild(dom.el("div", {
      style: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.5rem 0.75rem",
        border: "1px solid var(--border-color)",
        borderRadius: "6px",
        backgroundColor: "var(--bg-surface)",
      },
    },
      dom.el("span", { style: { fontWeight: "600", width: "120px" }, text: cat }),
      dom.el("div", { style: { display: "flex", gap: "1.5rem", alignItems: "center" } },
        dom.el("span", { style: { color: "var(--color-navy)", fontSize: "0.88rem" }, text: `Baseline: ${format.percent(b)}` }),
        dom.el("span", { style: { color: "var(--color-teal)", fontWeight: "600", fontSize: "0.88rem" }, text: `Incoming: ${format.percent(e)}` }),
        dom.el("span", { style: { color: diffColor, fontWeight: "700", fontSize: "0.85rem", width: "60px", textAlign: "right" }, text: diffText })
      )
    ));
  }
  container.appendChild(wrapper);
}
