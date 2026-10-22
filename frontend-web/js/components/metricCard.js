/**
 * OMNIVEX Metric Card Component
 */

import { dom } from "../core/dom.js";

export function renderMetricCard({
  label,
  value,
  subtext = null,
  theme = "healthy", // "healthy" (teal), "warning" (amber), "critical" (coral), "navy" (navy)
  id = null,
}) {
  const cardProps = {
    className: `metric-card ${theme}`,
  };
  if (id) cardProps.id = id;

  const children = [
    dom.el("div", { className: "metric-label", text: label }),
    dom.el("div", { className: "metric-value", text: value !== null && value !== undefined ? String(value) : "—" }),
  ];

  if (subtext) {
    children.push(dom.el("div", { className: "metric-sub", text: subtext }));
  }

  return dom.el("div", cardProps, ...children);
}
