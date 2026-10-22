/**
 * OMNIVEX Format Helpers
 * Single source of truth for display formatting, status badges, metrics, and dates.
 */

export const RELIABILITY_STATE_META = {
  NORMAL: {
    label: "Normal / Healthy",
    icon: "●",
    className: "status-NORMAL",
    color: "#1F9E9E",
    description: "Model performance and feature distributions operate within baseline tolerances.",
  },
  DRIFT_DETECTED: {
    label: "Drift Detected",
    icon: "▲",
    className: "status-DRIFT_DETECTED",
    color: "#F2A93B",
    description: "Input distribution has shifted, but labels are pending or performance remains intact.",
  },
  PERFORMANCE_DEGRADATION: {
    label: "Performance Degradation",
    icon: "✖",
    className: "status-PERFORMANCE_DEGRADATION",
    color: "#E4572E",
    description: "Metric drop confirmed against baseline without detectable covariate drift (concept drift).",
  },
  DRIFT_AND_PERFORMANCE_DEGRADATION: {
    label: "Drift & Degradation",
    icon: "✖",
    className: "status-DRIFT_AND_PERFORMANCE_DEGRADATION",
    color: "#E4572E",
    description: "Critical risk: both covariate drift and verified performance degradation confirmed.",
  },
  INSUFFICIENT_DATA: {
    label: "Insufficient Data",
    icon: "◼",
    className: "status-INSUFFICIENT_DATA",
    color: "#1B2A41",
    description: "Batch size below statistical threshold (<30 samples) or schema mismatch detected.",
  },
  MONITORING_ERROR: {
    label: "Monitoring Error",
    icon: "✖",
    className: "status-MONITORING_ERROR",
    color: "#E4572E",
    description: "A monitoring calculation encountered an unhandled exception; reliability uncertain.",
  },
};

export const ALERT_SEVERITY_META = {
  critical: {
    label: "Critical",
    icon: "✖",
    className: "severity-critical",
    color: "#E4572E",
  },
  warning: {
    label: "Warning",
    icon: "▲",
    className: "severity-warning",
    color: "#F2A93B",
  },
  info: {
    label: "Info",
    icon: "●",
    className: "severity-info",
    color: "#1F9E9E",
  },
};

export const format = {
  reliabilityState(stateKey) {
    return RELIABILITY_STATE_META[stateKey] || {
      label: stateKey || "Unknown",
      icon: "○",
      className: "status-INSUFFICIENT_DATA",
      color: "#64748B",
      description: "State unknown",
    };
  },

  alertSeverity(severityKey) {
    const key = (severityKey || "info").toLowerCase();
    return ALERT_SEVERITY_META[key] || {
      label: severityKey,
      icon: "●",
      className: "severity-info",
      color: "#1F9E9E",
    };
  },

  percent(val, digits = 1) {
    if (val === null || val === undefined || isNaN(val)) return "—";
    return `${(Number(val) * 100).toFixed(digits)}%`;
  },

  decimal(val, digits = 3) {
    if (val === null || val === undefined || isNaN(val)) return "—";
    return Number(val).toFixed(digits);
  },

  pValue(val) {
    if (val === null || val === undefined || isNaN(val)) return "—";
    const num = Number(val);
    if (num < 0.0001) return "< 0.0001";
    if (num < 0.001) return "< 0.001";
    return num.toFixed(4);
  },

  bytes(bytes) {
    if (bytes === null || bytes === undefined || isNaN(bytes)) return "—";
    const num = Number(bytes);
    if (num < 1024) return `${num} B`;
    if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)} KB`;
    return `${(num / (1024 * 1024)).toFixed(2)} MB`;
  },

  date(isoString) {
    if (!isoString) return "—";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return String(isoString);
    }
  },

  timeOnly(isoString) {
    if (!isoString) return "—";
    try {
      return new Date(isoString).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return String(isoString);
    }
  },

  truncate(str, maxLen = 40) {
    if (!str) return "";
    return str.length > maxLen ? `${str.slice(0, maxLen - 3)}...` : str;
  },

  badgeClass(status) {
    return status ? `badge-${status.toLowerCase()}` : "badge-neutral";
  },
};
