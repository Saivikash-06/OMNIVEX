/**
 * OMNIVEX Authentication & Session Guard
 */

import { store } from "./store.js";
import { apiClient } from "../api/client.js";
import { setApiBaseUrl } from "../api/config.js";

export const auth = {
  isAuthenticated() {
    const state = store.getState();
    return Boolean(state.user);
  },

  getCurrentUser() {
    return store.getState().user;
  },

  async login(username, apiKey = null, baseUrl = null) {
    if (!username || !username.trim()) {
      return { ok: false, error: "Please enter your operator or researcher name." };
    }

    if (baseUrl && baseUrl.trim()) {
      setApiBaseUrl(baseUrl.trim());
      apiClient.baseUrl = baseUrl.trim().replace(/\/+$/, "");
    }

    const cleanKey = apiKey && apiKey.trim() ? apiKey.trim() : null;
    apiClient.setApiKey(cleanKey);

    // Verify connectivity with backend
    const healthResult = await apiClient.health();
    if (!healthResult.ok) {
      return {
        ok: false,
        error: `Could not connect to backend at ${apiClient.baseUrl}: ${healthResult.error.message}`,
        details: healthResult.error.details,
      };
    }

    // Save session in store & storage
    store.setState({
      user: username.trim(),
      apiKey: cleanKey,
      backendStatus: "online",
      backendVersion: healthResult.data?.version || "2.0.0",
      backendLatencyMs: healthResult.elapsedMs,
      lastCheckTime: new Date().toISOString(),
    });

    return { ok: true, data: healthResult.data };
  },

  logout() {
    store.clearSession();
    apiClient.setApiKey(null);
    if (typeof window !== "undefined") {
      window.location.href = "index.html";
    }
  },

  requireAuth() {
    if (!this.isAuthenticated()) {
      if (typeof window !== "undefined") {
        window.location.replace("index.html");
      }
      return false;
    }
    // Synchronize client with stored API key
    const currentKey = store.getState().apiKey;
    if (currentKey) {
      apiClient.setApiKey(currentKey);
    }
    return true;
  },

  redirectIfAuth() {
    if (this.isAuthenticated()) {
      if (typeof window !== "undefined") {
        window.location.replace("app.html#/overview");
      }
      return true;
    }
    return false;
  },
};
