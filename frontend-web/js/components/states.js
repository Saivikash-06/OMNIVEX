/**
 * OMNIVEX State Renderers
 * Consistent loading, empty, error, and offline state presentations.
 */

import { dom } from "../core/dom.js";

export function renderLoading(message = "Loading data from backend...") {
  return dom.el("div", { className: "state-box" },
    dom.el("div", { className: "spinner" }),
    dom.el("div", { className: "state-title", text: message })
  );
}

export function renderEmpty({
  title = "No items found",
  description = "No data is currently available for this section.",
  actionText = null,
  onAction = null,
} = {}) {
  const children = [
    dom.el("div", { className: "state-icon", text: "📭" }),
    dom.el("div", { className: "state-title", text: title }),
    dom.el("div", { className: "state-description", text: description }),
  ];

  if (actionText && typeof onAction === "function") {
    children.push(
      dom.el("button", {
        className: "btn btn-primary btn-sm",
        style: { marginTop: "0.5rem" },
        text: actionText,
        onClick: onAction,
      })
    );
  }

  return dom.el("div", { className: "state-box" }, ...children);
}

export function renderError({
  title = "Unable to load data",
  message = "An error occurred while fetching data from the backend.",
  details = [],
  retryText = "Retry Request",
  onRetry = null,
} = {}) {
  const children = [
    dom.el("div", { className: "state-icon", text: "⚠️" }),
    dom.el("div", { className: "state-title", text: title }),
    dom.el("div", { className: "state-description", text: message }),
  ];

  if (details && details.length > 0) {
    const list = dom.el("ul", {
      style: {
        textAlign: "left",
        fontSize: "0.82rem",
        color: "var(--color-coral)",
        marginTop: "0.5rem",
        paddingLeft: "1.25rem",
      },
    });
    for (const d of details) {
      list.appendChild(dom.el("li", { text: d }));
    }
    children.push(list);
  }

  if (retryText && typeof onRetry === "function") {
    children.push(
      dom.el("button", {
        className: "btn btn-outline btn-sm",
        style: { marginTop: "0.75rem" },
        text: retryText,
        onClick: onRetry,
      })
    );
  }

  return dom.el("div", { className: "state-box error" }, ...children);
}

export function renderOffline({
  message = "OMNIVEX FastAPI backend is offline or unreachable at http://127.0.0.1:8000.",
  onRetry = null,
} = {}) {
  return renderError({
    title: "Backend Offline",
    message,
    details: [
      "Ensure the uvicorn server is running: python -m uvicorn backend.app.main:app --port 8000",
      "Check network connectivity or CORS origin settings.",
    ],
    retryText: "Check Backend Health",
    onRetry,
  });
}
