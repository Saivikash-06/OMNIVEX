/**
 * OMNIVEX DOM Builder
 * Safe element creation utility.
 * SECURITY: Prevents XSS by strictly using textContent and attributes, avoiding innerHTML with API data.
 */

export const dom = {
  /**
   * Create an element safely with attributes and children.
   */
  el(tag, props = {}, ...children) {
    const element = document.createElement(tag);

    for (const [key, value] of Object.entries(props)) {
      if (value === null || value === undefined || value === false) {
        continue;
      }

      if (key === "className" || key === "class") {
        element.className = value;
      } else if (key === "style" && typeof value === "object") {
        Object.assign(element.style, value);
      } else if (key.startsWith("on") && typeof value === "function") {
        const eventName = key.slice(2).toLowerCase();
        element.addEventListener(eventName, value);
      } else if (key === "textContent" || key === "text") {
        element.textContent = String(value);
      } else if (key === "disabled" || key === "checked" || key === "required" || key === "readOnly") {
        if (value) element.setAttribute(key, "");
      } else {
        element.setAttribute(key, String(value));
      }
    }

    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false) {
        continue;
      }
      if (typeof child === "string" || typeof child === "number") {
        element.appendChild(document.createTextNode(String(child)));
      } else if (child instanceof Node) {
        element.appendChild(child);
      }
    }

    return element;
  },

  text(content) {
    return document.createTextNode(content === null || content === undefined ? "" : String(content));
  },

  clear(element) {
    if (!element) return;
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  },

  append(parent, ...children) {
    if (!parent) return;
    for (const child of children.flat(Infinity)) {
      if (child instanceof Node) {
        parent.appendChild(child);
      } else if (typeof child === "string" || typeof child === "number") {
        parent.appendChild(document.createTextNode(String(child)));
      }
    }
  },

  toast(message, type = "info", durationMs = 4000) {
    let container = document.getElementById("omnivex-toast-container");
    if (!container) {
      container = dom.el("div", { id: "omnivex-toast-container", className: "toast-container" });
      document.body.appendChild(container);
    }

    const toastEl = dom.el("div", { className: `toast ${type}` },
      dom.el("span", { className: "toast-msg", text: message })
    );

    container.appendChild(toastEl);

    setTimeout(() => {
      toastEl.style.opacity = "0";
      toastEl.style.transform = "translateY(20px)";
      toastEl.style.transition = "all 0.3s ease";
      setTimeout(() => {
        if (toastEl.parentNode) toastEl.parentNode.removeChild(toastEl);
      }, 300);
    }, durationMs);
  },
};
