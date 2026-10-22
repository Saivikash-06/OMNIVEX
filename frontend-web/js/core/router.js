/**
 * OMNIVEX Client-Side Hash Router
 * Manages view routing, session guarding, and active navigation states.
 */

import { auth } from "./auth.js";
import { store } from "./store.js";
import { apiClient } from "../api/client.js";
import { renderOverview } from "../views/overview.js";
import { renderDatasets } from "../views/datasets.js";
import { renderModels } from "../views/models.js";
import { renderDrift } from "../views/drift.js";
import { renderPerformance } from "../views/performance.js";
import { renderAlerts } from "../views/alerts.js";
import { renderExperiments } from "../views/experiments.js";
import { renderSystem } from "../views/system.js";

const ROUTES = {
  "#/overview": { view: renderOverview, title: "Mission Control Overview", subtitle: "Real-time AI reliability and health monitoring" },
  "#/datasets": { view: renderDatasets, title: "Dataset Ingestion & Inspection", subtitle: "Reference training baselines and incoming stream batches" },
  "#/models": { view: renderModels, title: "Baseline AI Models", subtitle: "Train classification models and establish benchmark metrics" },
  "#/drift": { view: renderDrift, title: "Statistical Data Drift Detection", subtitle: "Two-sample testing (KS, Chi², TVD) with FDR correction" },
  "#/performance": { view: renderPerformance, title: "Empirical Performance & Degradation", subtitle: "Accuracy, F1-Score, and bootstrap confidence intervals" },
  "#/alerts": { view: renderAlerts, title: "Operational Reliability Alerts", subtitle: "Active, acknowledged, and resolved alert lifecycle" },
  "#/experiments": { view: renderExperiments, title: "Simulated Reliability Experiments", subtitle: "Stress testing under simulated drift & macroeconomic shocks" },
  "#/system": { view: renderSystem, title: "System Status & Configuration", subtitle: "Backend server connectivity, latency, and API keys" },
};

export class Router {
  constructor() {
    this.container = null;
    this.titleEl = null;
    this.subTitleEl = null;
    this.statusPillEl = null;
    this.healthIntervalId = null;
  }

  init({ containerId = "app-view-container", titleId = "page-title", subTitleId = "page-subtitle", statusPillId = "backend-status-pill" } = {}) {
    // 1. Session Guard: must be authenticated to enter app.html
    if (!auth.requireAuth()) {
      return;
    }

    this.container = document.getElementById(containerId);
    this.titleEl = document.getElementById(titleId);
    this.subTitleEl = document.getElementById(subTitleId);
    this.statusPillEl = document.getElementById(statusPillId);

    // 2. Setup hash change listener
    window.addEventListener("hashchange", () => this.handleRoute());

    // 3. User display in sidebar
    const userDisplay = document.getElementById("current-user-display");
    if (userDisplay) {
      userDisplay.textContent = auth.getCurrentUser() || "researcher";
    }

    // 4. Logout button listener
    const logoutBtn = document.getElementById("logout-button");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => auth.logout());
    }

    // 5. Mobile menu toggle
    const mobileMenuBtn = document.getElementById("mobile-menu-toggle");
    const sidebar = document.getElementById("app-sidebar");
    if (mobileMenuBtn && sidebar) {
      mobileMenuBtn.addEventListener("click", () => {
        sidebar.classList.toggle("open");
      });
    }

    // 6. Start background health monitor
    this.checkHealth();
    this.healthIntervalId = setInterval(() => this.checkHealth(), 15000);

    // 7. Initial route
    if (!window.location.hash || !ROUTES[window.location.hash]) {
      window.location.hash = "#/overview";
    } else {
      this.handleRoute();
    }
  }

  async checkHealth() {
    const res = await apiClient.health();
    const isOnline = res.ok && res.data?.status === "ok";

    store.setState({
      backendStatus: isOnline ? "online" : "offline",
      backendLatencyMs: res.elapsedMs,
      backendVersion: res.data?.version || "2.0.0",
    });

    if (this.statusPillEl) {
      this.statusPillEl.className = `backend-status-pill ${isOnline ? "online" : "offline"}`;
      const textSpan = this.statusPillEl.querySelector(".status-text");
      if (textSpan) {
        textSpan.textContent = isOnline ? `Backend Online (${res.elapsedMs}ms)` : "Backend Offline";
      }
    }
  }

  handleRoute() {
    const hash = window.location.hash || "#/overview";
    const route = ROUTES[hash] || ROUTES["#/overview"];

    // Update nav links active styling
    const navLinks = document.querySelectorAll(".nav-link");
    for (const link of navLinks) {
      const href = link.getAttribute("href");
      if (href === hash) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    }

    // Close mobile sidebar on nav
    const sidebar = document.getElementById("app-sidebar");
    if (sidebar && sidebar.classList.contains("open")) {
      sidebar.classList.remove("open");
    }

    // Update Header titles
    if (this.titleEl) this.titleEl.textContent = route.title;
    if (this.subTitleEl) this.subTitleEl.textContent = route.subtitle;

    // Render View
    if (this.container && typeof route.view === "function") {
      route.view(this.container);
    }
  }
}

export const router = new Router();
