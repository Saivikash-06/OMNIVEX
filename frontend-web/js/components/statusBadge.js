/**
 * OMNIVEX Status Badge Component
 * Renders badges for the 6 reliability states and alert severities.
 */

import { dom } from "../core/dom.js";
import { format } from "../core/format.js";

export function renderReliabilityBadge(stateKey) {
  const meta = format.reliabilityState(stateKey);
  return dom.el("span", {
    className: `status-badge ${meta.className}`,
    title: meta.description,
  },
    dom.el("span", { className: "badge-icon", text: meta.icon }),
    dom.el("span", { className: "badge-text", text: meta.label })
  );
}

export function renderAlertSeverityBadge(severityKey) {
  const meta = format.alertSeverity(severityKey);
  return dom.el("span", {
    className: `status-badge ${meta.className}`,
  },
    dom.el("span", { className: "badge-icon", text: meta.icon }),
    dom.el("span", { className: "badge-text", text: meta.label })
  );
}

export function renderStatusPill(status, label) {
  const isOk = status === "normal" || status === "active" || status === "evaluated" || status === "ok";
  const pillClass = isOk ? "status-NORMAL" : "status-DRIFT_DETECTED";
  return dom.el("span", {
    className: `status-badge ${pillClass}`,
  }, label || status);
}
